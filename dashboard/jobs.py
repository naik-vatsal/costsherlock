"""Background investigation runner.

Streamlit re-executes the whole script on every click. The old dashboard ran the
LLM pipeline *inside* that script, so any navigation click cancelled the run and
"Run All" could not show live progress.

Here the pipeline runs on a small thread pool instead. Workers only touch a
plain-Python :class:`JobBoard` (never ``st.session_state``), so a rerun, a tab
switch or a closed sidebar cannot interrupt them. The UI polls the board and
merges finished reports into session state on the main thread.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import anthropic

from agents import Anomaly, InvestigationReport
from agents.analyst import Analyst
from agents.detective import Detective
from agents.narrator import Narrator
from pipeline import _extract_remediation

logger = logging.getLogger(__name__)

MAX_WORKERS = 3          # investigations that may run in parallel
CALLS_PER_JOB = 2        # Analyst + Narrator

# Rough cost model (display only).
_INPUT_COST_PER_TOKEN = 3.00 / 1_000_000
_OUTPUT_COST_PER_TOKEN = 15.00 / 1_000_000
_CHARS_PER_TOKEN = 4.0

_executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="cs-job")
_agent_lock = threading.Lock()
_agents: dict[str, object] = {}
_warm_started = False


def estimate_cost(input_text: str, output_text: str) -> float:
    """Very rough USD estimate from character counts."""
    in_tok = len(input_text) / _CHARS_PER_TOKEN
    out_tok = len(output_text) / _CHARS_PER_TOKEN
    return in_tok * _INPUT_COST_PER_TOKEN + out_tok * _OUTPUT_COST_PER_TOKEN


# ── Agent singletons (built once, shared by all workers) ──────────────────────

def get_analyst() -> Analyst:
    with _agent_lock:
        if "analyst" not in _agents:
            _agents["analyst"] = Analyst()
        return _agents["analyst"]  # type: ignore[return-value]


def get_narrator() -> Narrator:
    with _agent_lock:
        if "narrator" not in _agents:
            _agents["narrator"] = Narrator()
        return _agents["narrator"]  # type: ignore[return-value]


def warm_up() -> None:
    """Load the embedding model and Chroma collection in the background.

    The first investigation otherwise pays several seconds of model load. Safe to
    call on every rerun; it only starts one thread per process.
    """
    global _warm_started
    if _warm_started:
        return
    _warm_started = True

    def _run() -> None:
        try:
            get_analyst()
            get_narrator()
            logger.info("Agents warmed up")
        except Exception as exc:  # no API key yet, etc. - surfaced on first real job
            logger.info("Warm-up skipped: %s", exc)

    threading.Thread(target=_run, name="cs-warmup", daemon=True).start()


# ── Job model ─────────────────────────────────────────────────────────────────

@dataclass
class Job:
    anomaly: Anomaly
    has_ct: bool
    state: str = "queued"            # queued | running | done | failed
    step: str = "sentinel"           # sentinel | detective | analyst | narrator
    skipped: set[str] = field(default_factory=set)
    log: list[str] = field(default_factory=list)
    result: InvestigationReport | None = None
    error: str = ""
    api_calls: int = 0
    cost_estimate: float = 0.0
    submitted_at: float = field(default_factory=time.monotonic)
    started_at: float = 0.0
    finished_at: float = 0.0
    merged: bool = False

    @property
    def key(self) -> tuple[str, str]:
        return (self.anomaly.service, self.anomaly.date)

    @property
    def active(self) -> bool:
        return self.state in ("queued", "running")

    @property
    def elapsed(self) -> float:
        if not self.started_at:
            return 0.0
        return (self.finished_at or time.monotonic()) - self.started_at

    def say(self, line: str) -> None:
        self.log.append(f"{time.strftime('%H:%M:%S')}  {line}")


class JobBoard:
    """Thread-safe registry of investigation jobs for one browser session."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.jobs: dict[tuple[str, str], Job] = {}

    # -- queries ---------------------------------------------------------------
    def get(self, key: tuple[str, str]) -> Job | None:
        with self._lock:
            return self.jobs.get(key)

    def active_jobs(self) -> list[Job]:
        with self._lock:
            return [j for j in self.jobs.values() if j.active]

    def has_active(self) -> bool:
        return bool(self.active_jobs())

    def reserved_calls(self) -> int:
        """API calls that active jobs may still consume (for the session limit)."""
        with self._lock:
            return sum(CALLS_PER_JOB - j.api_calls for j in self.jobs.values() if j.active)

    def batch_progress(self) -> tuple[int, int]:
        """(finished, total) over all jobs submitted in this session."""
        with self._lock:
            total = len(self.jobs)
            done = sum(1 for j in self.jobs.values() if j.state in ("done", "failed"))
            return done, total

    # -- mutations -------------------------------------------------------------
    def submit(self, anomaly: Anomaly, ct_events: list[dict], has_ct: bool) -> Job:
        """Queue one investigation (no-op if it is already queued or running)."""
        key = (anomaly.service, anomaly.date)
        with self._lock:
            existing = self.jobs.get(key)
            if existing and existing.active:
                return existing
            job = Job(anomaly=anomaly, has_ct=has_ct)
            self.jobs[key] = job
        _executor.submit(_run_job, job, ct_events)
        return job

    def drain(self) -> tuple[list[Job], int, float]:
        """Return newly finished jobs plus the API calls / cost they consumed.

        Marks them merged so each result is handed to the UI exactly once.
        """
        fresh: list[Job] = []
        calls = 0
        cost = 0.0
        with self._lock:
            for job in self.jobs.values():
                if job.state in ("done", "failed") and not job.merged:
                    job.merged = True
                    fresh.append(job)
                    calls += job.api_calls
                    cost += job.cost_estimate
        return fresh, calls, cost

    def clear_finished(self) -> None:
        with self._lock:
            self.jobs = {k: j for k, j in self.jobs.items() if j.active}


# ── Worker ────────────────────────────────────────────────────────────────────

def _friendly(exc: Exception) -> str:
    if isinstance(exc, anthropic.RateLimitError):
        return "Anthropic API rate limit hit. Wait 30-60 seconds and retry."
    if isinstance(exc, anthropic.AuthenticationError):
        return "API key is invalid or expired. Check ANTHROPIC_API_KEY."
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return "Network timeout reaching the Anthropic API. Check the connection and retry."
    if isinstance(exc, anthropic.APIStatusError):
        return f"Anthropic API error (HTTP {exc.status_code}). Retry in a moment."
    if isinstance(exc, ValueError):
        return str(exc)
    return f"Investigation failed unexpectedly ({type(exc).__name__})."


def _run_job(job: Job, ct_events: list[dict]) -> None:
    """Execute Sentinel -> Detective -> Analyst -> Narrator for one anomaly."""
    a = job.anomaly
    job.state = "running"
    job.started_at = time.monotonic()
    try:
        job.step = "sentinel"
        job.say(f"Sentinel confirmed {a.service} on {a.date}: z={a.z_score:.2f}, delta=+${a.delta:,.2f}")

        job.step = "detective"
        if job.has_ct:
            job.say("Detective correlating CloudTrail events...")
            suspects = Detective.get_events_in_window(ct_events, a)
            job.say(f"Detective found {len(suspects)} suspect event(s) in the +/-48h window")
        else:
            job.skipped.add("detective")
            job.say("Detective skipped: no CloudTrail logs provided (RAG-only mode)")
            suspects = []

        job.step = "analyst"
        job.say("Analyst querying the RAG knowledge base and reasoning...")
        analysis = get_analyst().analyze(a, suspects)
        job.api_calls += 1

        hypotheses = analysis.get("hypotheses", [])
        ruled_out = analysis.get("ruled_out", [])
        hypotheses = hypotheses if isinstance(hypotheses, list) else []
        ruled_out = ruled_out if isinstance(ruled_out, list) else []
        if hypotheses:
            job.say(f"Analyst produced {len(hypotheses)} hypothesis(es), {len(ruled_out)} ruled out")
        else:
            job.say("Analyst produced no hypotheses (INSUFFICIENT_EVIDENCE)")

        job.step = "narrator"
        job.say("Narrator drafting the cited report...")
        report_md = get_narrator().generate_report(a, analysis)
        job.api_calls += 1
        if not report_md or not report_md.strip():
            report_md = (
                "## Executive Summary\n"
                "No root cause could be determined with sufficient confidence.\n"
            )

        elapsed = round(time.monotonic() - job.started_at, 2)
        job.cost_estimate = estimate_cost(str(analysis) * 3, report_md)
        job.result = InvestigationReport(
            anomaly=a,
            hypotheses=hypotheses,
            ruled_out=ruled_out,
            remediation=_extract_remediation(report_md),
            overall_confidence=hypotheses[0].confidence if hypotheses else 0.0,
            report_markdown=report_md,
            elapsed_seconds=elapsed,
        )
        job.say(f"Report ready in {elapsed:.1f}s")
        job.state = "done"
    except Exception as exc:  # noqa: BLE001 - surfaced to the UI, never raised
        logger.exception("Investigation failed for %s", a.service)
        # A bad key / missing model should not poison later attempts.
        with _agent_lock:
            if isinstance(exc, (ValueError, anthropic.AuthenticationError)):
                _agents.clear()
        job.error = _friendly(exc)
        job.say(f"Failed: {job.error}")
        job.state = "failed"
    finally:
        job.finished_at = time.monotonic()
