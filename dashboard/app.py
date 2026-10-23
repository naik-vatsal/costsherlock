# Dashboard module — Priti Ghosh
"""CostSherlock Streamlit Dashboard — main application."""

from __future__ import annotations

import json
import logging
import re
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

import anthropic
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

# ── Path setup ────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_ROOT))

# Load .env with override=True so the project key always wins over any stale
# value already present in the OS / shell environment.
load_dotenv(dotenv_path=_ROOT / ".env", override=True)

from agents import Anomaly, InvestigationReport, RuledOutEvent  # noqa: E402
from agents.detective import Detective  # noqa: E402
from agents.sentinel import Sentinel  # noqa: E402
from dashboard import jobs, theme  # noqa: E402

# ── Constants ─────────────────────────────────────────────────────────────────
DEMO_COST_PATH = str(_ROOT / "data" / "synthetic" / "demo_cost.json")
DEMO_CLOUDTRAIL_DIR = str(_ROOT / "data" / "synthetic" / "demo_cloudtrail")
MODEL_NAME = "claude-sonnet-5-5"

# API protection
API_CALL_LIMIT = 30
MAX_ANOMALIES_DISPLAYED = 10
# Streamlit's default upload limit
STREAMLIT_MAX_UPLOAD_MB = 200

NAVY = "#14161F"
BLUE = "#3B5BFF"
GREEN = "#1FA971"
RED = "#E5484D"
ORANGE = "#F08A24"
AMBER = "#F08A24"
VIEWS = ["Timeline", "Investigation", "Evidence", "Compare", "Feedback"]

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CostSherlock",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="auto",
)

# ── Visual system ─────────────────────────────────────────────────────────────
theme.inject_css()
theme.inject_motion()

# ── Session state initialisation ──────────────────────────────────────────────
_DEFAULTS: dict = {
    "data_loaded": False,
    "cost_df": None,
    "anomalies": [],
    "selected_anomaly": None,
    "investigations": [],
    "current_investigation": None,
    "cloudtrail_logs": [],
    "cloudtrail_source": "none",   # "none" | "demo" | "upload"
    "api_calls": 0,
    "total_cost_estimate": 0.0,
    "current_view": "Timeline",
    "z_threshold_slider": 2.5,
    "_pending_toast": "",
    "_auto_run": False,
    "_last_timeline_click": None,  # (curve_number, point_number) of last processed chart click
    "job_errors": {},              # (service, date) -> error message for failed background jobs
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v
if "_board" not in st.session_state:
    st.session_state._board = jobs.JobBoard()  # background investigation jobs (this session)

# ── Cached resources ──────────────────────────────────────────────────────────

@st.cache_resource
def _ensure_knowledge_base() -> bool:
    """Build the RAG knowledge base if it doesn't already exist.

    Runs exactly once per deployment (cached by st.cache_resource).
    On Streamlit Cloud, chroma_db/ is not in the repo, so this builds
    it from the markdown documents in rag/documents/ on first startup.
    """
    import chromadb

    db_path = str(_ROOT / "chroma_db")
    client = chromadb.PersistentClient(path=db_path)
    try:
        col = client.get_collection("costsherlock_docs")
        logging.getLogger(__name__).info(
            "Knowledge base ready: %d chunks in collection", col.count()
        )
        return True
    except Exception:
        logging.getLogger(__name__).info(
            "Knowledge base not found — building from rag/documents/…"
        )
        from rag.ingest import build_knowledge_base

        docs_dir = str(_ROOT / "rag" / "documents")
        build_knowledge_base(docs_dir=docs_dir, db_path=db_path)
        return True


# ── Ensure knowledge base exists before any agent is constructed ──────────────
with st.spinner("Building knowledge base (first run only)…"):
    _ensure_knowledge_base()
jobs.warm_up()  # load the embedding model in the background while the user explores


@st.cache_data
def _load_cost_data(path: str) -> pd.DataFrame:
    return Sentinel.load_from_json(path)


@st.cache_data
def _load_cloudtrail(log_dir: str) -> list[dict]:
    return Detective.load_cloudtrail_logs(log_dir)


@st.cache_data
def _detect_anomalies_cached(path: str, z_threshold: float) -> list[dict]:
    df = _load_cost_data(path)
    return [a.model_dump() for a in Sentinel.detect_anomalies(df, z_threshold=z_threshold)]


# ── Helper utilities ──────────────────────────────────────────────────────────

_BADGE_COLORS: dict[str, str] = {
    "WRONG_MECHANISM": RED,
    "TEMPORAL_ONLY": ORANGE,
    "INSUFFICIENT_EVIDENCE": "#6B7280",
    "UNRELATED_SERVICE": "#8B5CF6",
}


def _category_badge(category: str) -> str:
    color = _BADGE_COLORS.get(category, "#6B7280")
    return (
        f'<span class="cat-badge" style="background:{color}">'
        f"{category}</span>"
    )


def _severity_badge(delta: float) -> str:
    if delta > 200:
        return '<span class="sev-badge sev-critical">Critical</span>'
    elif delta > 50:
        return '<span class="sev-badge sev-warning">Warning</span>'
    return '<span class="sev-badge sev-info">Info</span>'


def _confidence_color(conf: float) -> str:
    if conf >= 0.8:
        return GREEN
    if conf >= 0.55:
        return AMBER
    return RED


def _conf_class(conf: float) -> str:
    if conf >= 0.8:
        return "status-high"
    if conf >= 0.55:
        return "status-medium"
    return "status-low"


def _conf_label(conf: float) -> str:
    if conf >= 0.8:
        return f"HIGH CONFIDENCE ({conf:.0%})"
    if conf >= 0.55:
        return f"MEDIUM CONFIDENCE ({conf:.0%})"
    return f"LOW CONFIDENCE ({conf:.0%})"


# ── Markdown escaping ─────────────────────────────────────────────────────────

# A code fence or inline code span (kept verbatim), or a "$" / "~" not already escaped.
_MD_LITERAL_RE = re.compile(r"(```.*?```|~~~.*?~~~|`[^`\n]*`)|(?<!\\)([$~])", re.DOTALL)


def safe_md(text: str) -> str:
    """Escape ``$`` and ``~`` so Streamlit markdown shows them literally.

    Streamlit renders text between two ``$`` as math and between two ``~`` as
    strikethrough, so report prose like "~$125/day" turns into italic,
    monospace or struck-through runs. Only use this for text rendered as
    markdown; inside raw HTML blocks the backslash would show.

    Args:
        text: Agent or report text about to be rendered as markdown.

    Returns:
        The text with each unescaped ``$`` and ``~`` outside code spans
        backslash-escaped.
    """
    if not text:
        return text
    return _MD_LITERAL_RE.sub(lambda m: m.group(1) or "\\" + m.group(2), text)


# ── API limit helpers ─────────────────────────────────────────────────────────

def _api_remaining() -> int:
    return max(0, API_CALL_LIMIT - st.session_state.api_calls)


def _check_api_limit() -> bool:
    """Return True (proceed) or False (blocked, error already shown)."""
    if st.session_state.api_calls >= API_CALL_LIMIT:
        st.error(
            f"Session API limit reached ({API_CALL_LIMIT} calls). "
            "Restart the app or clone the repo to use your own API key."
        )
        return False
    return True


def _friendly_api_error(exc: Exception) -> str:
    """Convert Anthropic API exceptions into user-friendly messages."""
    if isinstance(exc, anthropic.RateLimitError):
        return (
            "Anthropic API rate limit hit. Please wait 30–60 seconds and retry. "
            "(Error: rate_limit_error)"
        )
    if isinstance(exc, anthropic.AuthenticationError):
        return (
            "API key is invalid or expired. Check your ANTHROPIC_API_KEY in the .env file. "
            "Do not share your API key."
        )
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return (
            "Network timeout reaching the Anthropic API. "
            "Check your internet connection and retry. (Error: connection_timeout)"
        )
    if isinstance(exc, anthropic.APIStatusError):
        return f"Anthropic API error (HTTP {exc.status_code}). Retry in a moment."
    return str(exc)


# ── CloudTrail state helpers ──────────────────────────────────────────────────

def _get_cloudtrail_state() -> tuple[list[dict], bool]:
    """Return (events, has_user_provided_logs)."""
    events = st.session_state.cloudtrail_logs
    has_logs = len(events) > 0 and st.session_state.cloudtrail_source != "none"
    return events, has_logs


def _load_cloudtrail_upload(uploaded_file) -> list[dict]:
    """Load CloudTrail events from an uploaded JSON or ZIP file.

    Args:
        uploaded_file: Streamlit UploadedFile object.

    Returns:
        Flat list of CloudTrail event dicts.

    Raises:
        ValueError: On unrecognised JSON structure.
        zipfile.BadZipFile: On corrupted ZIP.
    """
    name = uploaded_file.name.lower()
    if name.endswith(".zip"):
        tmp_dir = tempfile.mkdtemp(prefix="cs_ct_")
        with zipfile.ZipFile(uploaded_file) as zf:
            extracted = 0
            for member in zf.namelist():
                # skip macOS metadata and non-JSON files
                if member.startswith("__MACOSX") or not member.endswith(".json"):
                    continue
                zf.extract(member, tmp_dir)
                extracted += 1
        if extracted == 0:
            raise ValueError("ZIP archive contained no .json files.")
        return Detective.load_cloudtrail_logs(tmp_dir)
    else:
        raw = uploaded_file.read()
        content = json.loads(raw.decode("utf-8"))
        if isinstance(content, list):
            return content
        if isinstance(content, dict) and "Records" in content:
            return content["Records"]
        if isinstance(content, dict) and "eventName" in content:
            return [content]
        raise ValueError(
            "Unexpected JSON structure — expected a list of events or "
            "an object with a 'Records' key."
        )


# ── Cost JSON validation ──────────────────────────────────────────────────────

def _validate_cost_json(data: object) -> tuple[bool, str]:
    """Validate that data is a non-empty list with the required keys.

    Returns:
        (valid, error_message)
    """
    if not isinstance(data, list):
        return False, (
            "Expected a JSON array. Got a single object.\n\n"
            "Required format:\n"
            '```json\n[{"date": "2026-01-01", "service": "Amazon EC2", "cost": 10.5}, ...]\n```'
        )
    if len(data) == 0:
        return False, (
            "Cost data array is empty (`[]`). "
            "Please provide at least one record."
        )
    required = {"date", "service", "cost"}
    missing = required - set(data[0].keys())
    if missing:
        return False, (
            f"Missing required field(s): **{', '.join(sorted(missing))}**.\n\n"
            "Required format:\n"
            '```json\n[{"date": "2026-01-01", "service": "Amazon EC2", "cost": 10.5}]\n```'
        )
    return True, ""


# ── Persist investigation ─────────────────────────────────────────────────────

def _persist_investigation(inv: InvestigationReport) -> None:
    st.session_state.current_investigation = inv
    existing = {(r.anomaly.service, r.anomaly.date) for r in st.session_state.investigations}
    if (inv.anomaly.service, inv.anomaly.date) not in existing:
        st.session_state.investigations.append(inv)


# ── Background investigations ─────────────────────────────────────────────────
# The pipeline runs on worker threads (dashboard/jobs.py), so clicking around the
# app can no longer cancel it. The main thread only queues work and merges results.

def _board() -> jobs.JobBoard:
    return st.session_state._board


def _queue(anomalies: list[Anomaly]) -> int:
    """Queue anomalies for background investigation, respecting the API budget."""
    board = _board()
    ct_events, has_ct = _get_cloudtrail_state()
    done_keys = {(r.anomaly.service, r.anomaly.date) for r in st.session_state.investigations}
    budget = API_CALL_LIMIT - st.session_state.api_calls - board.reserved_calls()
    queued = over_budget = 0
    for a in anomalies:
        key = (a.service, a.date)
        job = board.get(key)
        if key in done_keys or (job is not None and job.active):
            continue
        if budget < jobs.CALLS_PER_JOB:
            over_budget += 1
            continue
        st.session_state.job_errors.pop(key, None)
        board.submit(a, ct_events, has_ct)
        budget -= jobs.CALLS_PER_JOB
        queued += 1
    if over_budget:
        st.warning(
            f"Session API limit ({API_CALL_LIMIT} calls) reached: "
            f"{over_budget} investigation(s) were not started."
        )
    return queued


def _sync_jobs() -> bool:
    """Merge finished background jobs into session state. True if anything changed."""
    fresh, calls, cost = _board().drain()
    if not fresh:
        return False
    st.session_state.api_calls += calls
    st.session_state.total_cost_estimate += cost
    selected = st.session_state.selected_anomaly
    ok = failed = 0
    for job in fresh:
        if job.state == "done" and job.result is not None:
            ok += 1
            existing = {(r.anomaly.service, r.anomaly.date) for r in st.session_state.investigations}
            if job.key not in existing:
                st.session_state.investigations.append(job.result)
            if selected is not None and (selected.service, selected.date) == job.key:
                st.session_state.current_investigation = job.result
            elif st.session_state.current_investigation is None:
                st.session_state.current_investigation = job.result
        else:
            failed += 1
            st.session_state.job_errors[job.key] = job.error or "Investigation failed."
    if len(fresh) == 1 and ok == 1:
        j = fresh[0]
        conf = f"{j.result.overall_confidence:.0%}" if j.result and j.result.hypotheses else "n/a"
        st.session_state._pending_toast = (
            f"Investigation done · {j.anomaly.service} · {j.anomaly.date} · "
            f"confidence {conf} · {j.elapsed:.1f}s"
        )
    elif ok or failed:
        st.session_state._pending_toast = (
            f"{ok} investigation(s) complete" + (f", {failed} failed" if failed else "")
        )
    return True


def _activity_body() -> None:
    """Global activity bar. Runs as a fragment that re-polls every ~1.5 s while jobs run."""
    if _sync_jobs():
        st.rerun()  # full rerun so the table, KPIs and sidebar pick up the new results
    active = _board().active_jobs()
    if not active:
        return
    done, total = _board().batch_progress()
    running = [j for j in active if j.state == "running"]
    lead = (running or active)[0]
    agent = {"sentinel": "Sentinel", "detective": "Detective", "analyst": "Analyst", "narrator": "Narrator"}.get(lead.step, "")
    more = f" +{len(active) - 1} more" if len(active) > 1 else ""
    st.markdown(
        f"""<div class="cs-activity">
            <div class="cs-spin"></div>
            <div style="flex:1;min-width:0">
              <div style="font-weight:700;color:var(--ink)">Investigating {lead.anomaly.service}{more}
                <span style="font-weight:500;color:var(--ink-3)"> · {agent} working · {done}/{total} complete</span></div>
              <div class="cs-bar"><span style="width:{(done / max(total, 1)) * 100:.0f}%"></span></div>
            </div>
            <div style="font-size:.78rem;color:var(--ink-3)">runs in the background · safe to switch tabs</div>
          </div>""",
        unsafe_allow_html=True,
    )


def _render_activity() -> None:
    every = 1.5 if _board().has_active() else None
    st.fragment(run_every=every)(_activity_body)()


def _job_panel_body(key: tuple[str, str]) -> None:
    """Live 4-agent stepper for one anomaly (fragment, re-polls while it runs)."""
    if _sync_jobs():
        st.rerun()
    job = _board().get(key)
    if job is None:
        return
    st.markdown(
        theme.stepper_html(job.step, job.state, job.skipped, job.log),
        unsafe_allow_html=True,
    )
    st.caption(f"Elapsed {job.elapsed:0.0f}s · the Analyst and Narrator calls usually take 40–90 s together")


def _render_job_panel(key: tuple[str, str]) -> None:
    job = _board().get(key)
    every = 1.0 if (job is not None and job.active) else None
    st.fragment(run_every=every)(_job_panel_body)(key)


# ── Investigation navigation callbacks ───────────────────────────────────────

def _nav_prev() -> None:
    invs_list = st.session_state.investigations
    inv = st.session_state.current_investigation
    if inv is None or not invs_list:
        return
    current_idx = next(
        (i for i, r in enumerate(invs_list)
         if r.anomaly.service == inv.anomaly.service and r.anomaly.date == inv.anomaly.date),
        0,
    )
    if current_idx > 0:
        target = invs_list[current_idx - 1]
        st.session_state.current_investigation = target
        st.session_state.selected_anomaly = target.anomaly
        inv_labels = [f"{r.anomaly.service}  —  {r.anomaly.date}" for r in invs_list]
        st.session_state.inv_nav_sel = inv_labels[current_idx - 1]


def _nav_next() -> None:
    invs_list = st.session_state.investigations
    inv = st.session_state.current_investigation
    if inv is None or not invs_list:
        return
    current_idx = next(
        (i for i, r in enumerate(invs_list)
         if r.anomaly.service == inv.anomaly.service and r.anomaly.date == inv.anomaly.date),
        0,
    )
    if current_idx < len(invs_list) - 1:
        target = invs_list[current_idx + 1]
        st.session_state.current_investigation = target
        st.session_state.selected_anomaly = target.anomaly
        inv_labels = [f"{r.anomaly.service}  —  {r.anomaly.date}" for r in invs_list]
        st.session_state.inv_nav_sel = inv_labels[current_idx + 1]


def _on_investigate(anomaly: Anomaly) -> None:
    st.session_state.selected_anomaly = anomaly
    st.session_state.current_view = "Investigation"
    cached = next(
        (r for r in st.session_state.investigations
         if r.anomaly.service == anomaly.service and r.anomaly.date == anomaly.date),
        None,
    )
    if cached:
        st.session_state.current_investigation = cached
        st.session_state._auto_run = False
    else:
        st.session_state._auto_run = True


def _nav_select() -> None:
    invs_list = st.session_state.investigations
    sel_label = st.session_state.get("inv_nav_sel", "")
    if not sel_label or not invs_list:
        return
    inv_labels = [f"{r.anomaly.service}  —  {r.anomaly.date}" for r in invs_list]
    if sel_label not in inv_labels:
        return
    target = invs_list[inv_labels.index(sel_label)]
    st.session_state.current_investigation = target
    st.session_state.selected_anomaly = target.anomaly


# ── Merge anything that finished in the background, then show pending toast ───
_sync_jobs()
if st.session_state._pending_toast:
    st.toast(st.session_state._pending_toast, icon="✅")
    st.session_state._pending_toast = ""

# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
<div class="sb-brand">
    <div class="sb-logo">🔍</div>
    <div>
        <div class="sb-brand-title">CostSherlock</div>
        <div class="sb-brand-sub">AWS FinOps · Anomaly Intelligence</div>
    </div>
</div>
""", unsafe_allow_html=True)

    # ── Investigation status pills ────────────────────────────────────────────
    anomalies_ss = st.session_state.anomalies
    inv_count = len(st.session_state.investigations)
    total_count = len(anomalies_ss)
    total_delta = sum(a.delta for a in anomalies_ss)
    status_icon = "✅" if (total_count > 0 and inv_count == total_count) else "⏳"
    if total_count > 0:
        st.markdown(f"""
    <div class="sb-stat">
        <span class="sb-stat-label">Investigations</span>
        <span class="sb-stat-value">{status_icon} {inv_count}/{total_count}</span>
    </div>
    <div class="sb-stat">
        <span class="sb-stat-label">Total Cost Impact</span>
        <span class="sb-stat-value" style="color:#FCA5A5 !important">+${total_delta:,.2f}</span>
    </div>
    """, unsafe_allow_html=True)
        st.markdown("")

    # ── API calls remaining ───────────────────────────────────────────────────
    remaining = _api_remaining()
    api_pct = remaining / API_CALL_LIMIT
    pill_class = "api-limit-ok" if api_pct > 0.3 else "api-limit-warn"
    st.markdown(
        f'<div class="{pill_class}">🔑 API calls: {remaining}/{API_CALL_LIMIT} remaining</div>',
        unsafe_allow_html=True,
    )
    st.markdown("")

    # ── Load Demo Data ────────────────────────────────────────────────────────
    if st.button("📥 Load Demo Data", width="stretch"):
        with st.spinner("Loading synthetic dataset…"):
            try:
                z = st.session_state.z_threshold_slider
                df = _load_cost_data(DEMO_COST_PATH)
                ct = _load_cloudtrail(DEMO_CLOUDTRAIL_DIR)
                anomaly_dicts = _detect_anomalies_cached(DEMO_COST_PATH, z)
                anomalies_loaded = [Anomaly(**a) for a in anomaly_dicts]

                # Cap at MAX_ANOMALIES_DISPLAYED (by z-score, already sorted)
                displayed = anomalies_loaded[:MAX_ANOMALIES_DISPLAYED]
                note = ""
                if len(anomalies_loaded) > MAX_ANOMALIES_DISPLAYED:
                    note = (
                        f" (showing top {MAX_ANOMALIES_DISPLAYED} "
                        f"of {len(anomalies_loaded)} detected)"
                    )

                st.session_state.update(
                    {
                        "data_loaded": True,
                        "cost_df": df,
                        "cloudtrail_logs": ct,
                        "cloudtrail_source": "demo",
                        "anomalies": displayed,
                    }
                )
                st.success(
                    f"✓ {len(displayed)} anomaly/anomalies across "
                    f"{df['service'].nunique()} services{note}"
                )
            except Exception as exc:
                st.error(f"Load failed: {exc}")

    # ── Custom cost JSON upload ───────────────────────────────────────────────
    uploaded_cost = st.file_uploader(
        "Upload Cost JSON",
        type=["json"],
        help="JSON array with date, service, cost fields.",
        key="cost_uploader",
    )
    if uploaded_cost is not None:
        # Guard against Streamlit's 200 MB limit exceeded (file object is empty/truncated)
        if uploaded_cost.size == 0:
            st.error(
                "Uploaded file appears to be empty. "
                "If it exceeds 200 MB, split it into smaller chunks."
            )
        elif uploaded_cost.size > STREAMLIT_MAX_UPLOAD_MB * 1024 * 1024:
            st.error(
                f"File is too large ({uploaded_cost.size / 1024 / 1024:.1f} MB). "
                f"Streamlit's limit is {STREAMLIT_MAX_UPLOAD_MB} MB. "
                "Split the file or filter to a shorter date range."
            )
        else:
            with st.spinner("Parsing uploaded file…"):
                try:
                    raw_bytes = uploaded_cost.read()
                    raw_data = json.loads(raw_bytes.decode("utf-8"))

                    valid, err_msg = _validate_cost_json(raw_data)
                    if not valid:
                        st.error(err_msg)
                    else:
                        # Write to temp file for Sentinel
                        with tempfile.NamedTemporaryFile(
                            suffix=".json", delete=False, mode="wb"
                        ) as tmp:
                            tmp.write(raw_bytes)
                            tmp_path = tmp.name

                        df = Sentinel.load_from_json(tmp_path)

                        # Edge case: only 1 day / too few rows for rolling window
                        n_days = df.groupby("service")["date"].nunique().min()
                        if n_days < 14:
                            st.warning(
                                f"Dataset has fewer than 14 days per service ({n_days} day(s) "
                                "found). The z-score detector needs at least 14 days to "
                                "establish a rolling baseline. Fewer anomalies may be detected."
                            )

                        z = st.session_state.z_threshold_slider
                        anomalies_up = Sentinel.detect_anomalies(df, z_threshold=z)

                        # Warn about suspicious data quality
                        neg_count = int((df["cost"] < 0).sum())
                        if neg_count > 0:
                            st.warning(
                                f"{neg_count} record(s) have negative cost values. "
                                "These may cause unexpected anomaly detections."
                            )

                        # Cap anomalies
                        displayed = anomalies_up[:MAX_ANOMALIES_DISPLAYED]
                        note = ""
                        if len(anomalies_up) > MAX_ANOMALIES_DISPLAYED:
                            note = (
                                f" (showing top {MAX_ANOMALIES_DISPLAYED} "
                                f"of {len(anomalies_up)})"
                            )

                        st.session_state.update(
                            {
                                "data_loaded": True,
                                "cost_df": df,
                                "anomalies": displayed,
                                # Don't reset cloudtrail_logs if already loaded
                            }
                        )
                        if len(displayed) == 0:
                            st.info(
                                "No anomalies detected at the current z-score threshold. "
                                "Try lowering the threshold in ⚙️ Settings."
                            )
                        else:
                            st.success(
                                f"✓ {len(displayed)} anomaly/anomalies detected{note}"
                            )

                except json.JSONDecodeError as exc:
                    st.error(
                        f"Invalid JSON — could not parse the file.\n\n"
                        f"Parser says: `{exc.msg}` at line {exc.lineno}.\n\n"
                        "Make sure the file is valid UTF-8 encoded JSON."
                    )
                except ValueError as exc:
                    st.error(f"Schema error: {exc}")
                except Exception as exc:
                    st.error(
                        f"Upload failed unexpectedly. "
                        f"(Internal: {type(exc).__name__}: {exc})"
                    )

    # ── CloudTrail logs upload ────────────────────────────────────────────────
    uploaded_ct = st.file_uploader(
        "Upload CloudTrail Logs",
        type=["json", "zip"],
        help=(
            "Single CloudTrail JSON file, or a ZIP archive of multiple JSON files. "
            "If omitted, analysis uses RAG knowledge base only."
        ),
        key="ct_uploader",
    )
    if uploaded_ct is not None:
        if uploaded_ct.size == 0:
            st.error("Uploaded CloudTrail file is empty.")
        elif uploaded_ct.size > STREAMLIT_MAX_UPLOAD_MB * 1024 * 1024:
            st.error(
                f"CloudTrail file is too large ({uploaded_ct.size / 1024 / 1024:.1f} MB). "
                f"Maximum is {STREAMLIT_MAX_UPLOAD_MB} MB."
            )
        else:
            with st.spinner("Loading CloudTrail events…"):
                try:
                    events = _load_cloudtrail_upload(uploaded_ct)

                    if len(events) == 0:
                        st.warning(
                            "CloudTrail file loaded but contained no events. "
                            "Investigations will use RAG only."
                        )
                        st.session_state.cloudtrail_source = "none"
                    else:
                        st.session_state.cloudtrail_logs = events
                        st.session_state.cloudtrail_source = "upload"
                        st.success(f"✓ {len(events)} CloudTrail event(s) loaded")

                except json.JSONDecodeError as exc:
                    st.error(
                        f"Invalid JSON in CloudTrail file. "
                        f"Parser: `{exc.msg}` at line {exc.lineno}."
                    )
                except zipfile.BadZipFile:
                    st.error(
                        "Corrupted or invalid ZIP file. "
                        "Re-export or try uploading the JSON files individually."
                    )
                except ValueError as exc:
                    st.error(f"CloudTrail format error: {exc}")
                except Exception as exc:
                    st.error(
                        f"CloudTrail upload failed. "
                        f"(Internal: {type(exc).__name__}: {exc})"
                    )

    # Show CloudTrail source indicator
    ct_source = st.session_state.cloudtrail_source
    if ct_source == "demo":
        st.caption("📂 CloudTrail: demo dataset")
    elif ct_source == "upload":
        n_ct = len(st.session_state.cloudtrail_logs)
        st.caption(f"📂 CloudTrail: {n_ct} uploaded events")
    else:
        st.caption("📂 CloudTrail: none (RAG-only mode)")

    st.divider()

    # ── Settings ──────────────────────────────────────────────────────────────
    with st.expander("⚙️ Settings"):
        st.slider(
            "Z-Score Threshold",
            min_value=1.5,
            max_value=4.0,
            step=0.1,
            key="z_threshold_slider",
            help="Anomalies are flagged when cost exceeds the rolling mean by this many σ.",
        )
        st.divider()
        st.caption("**Developer options**")
        if st.button(
            "🔄 Reset API Counter",
            help="For local development only — resets the session call counter to 0.",
            width="stretch",
        ):
            st.session_state.api_calls = 0
            st.success("API counter reset to 0.")

    st.divider()

    # ── Session stats ─────────────────────────────────────────────────────────
    st.caption(f"**Model:** `{MODEL_NAME}`")
    st.caption(f"**API calls:** {st.session_state.api_calls}/{API_CALL_LIMIT}")
    st.caption(f"**Est. API cost:** `${st.session_state.total_cost_estimate:.4f}`")
    st.caption(f"**Investigations:** {inv_count}")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT — dispatch on current_view
# ═════════════════════════════════════════════════════════════════════════════

# ── Hero (Timeline only), top navigation, live activity bar ───────────────────
if st.session_state.current_view == "Timeline":
    _hero_anoms = st.session_state.anomalies
    if _hero_anoms:
        _hero_bars = [a.delta for a in sorted(_hero_anoms, key=lambda a: -a.delta)]
        _hero_chips = [
            (str(len(_hero_anoms)), "anomalies"),
            (f"${sum(a.delta for a in _hero_anoms):,.0f}", "excess spend"),
            ("4", "agents"),
        ]
    else:
        _hero_bars = None
        _hero_chips = [("4", "agents"), ("RAG", "cited evidence"), ("RAGAS", "evaluated")]
    theme.render_hero(_hero_bars, _hero_chips)

st.radio("Navigation", VIEWS, key="current_view", horizontal=True, label_visibility="collapsed")
_render_activity()
view = st.session_state.current_view

# ─────────────────────────────────────────────────────────────────────────────
# VIEW 1 — ANOMALY TIMELINE
# ─────────────────────────────────────────────────────────────────────────────
if view == "Timeline":
    if not st.session_state.data_loaded:
        st.markdown(
            """<div class="cs-empty cs-rise">
                <div class="big">📊</div>
                <div style="font-family:var(--display);font-weight:800;font-size:1.35rem;color:var(--ink)">No data loaded yet</div>
                <p style="margin:8px 0 0">Open the sidebar and click <b>Load Demo Data</b> to see four agents
                investigate real-looking AWS cost spikes, or upload your own Cost Explorer JSON export.</p>
            </div>""",
            unsafe_allow_html=True,
        )
    else:
        df: pd.DataFrame = st.session_state.cost_df
        anomalies: list[Anomaly] = st.session_state.anomalies

        if df is None or df.empty:
            st.error("Loaded dataset is empty. Please reload or upload a different file.")
        elif len(df) > 0 and df["service"].nunique() == 0:
            st.error("No service data found in the dataset.")
        else:
            # ── Zero anomalies ────────────────────────────────────────────────
            if not anomalies:
                st.info(
                    "✅ No anomalies detected in this dataset. "
                    "All services appear within normal cost range at the current "
                    f"z-score threshold ({st.session_state.z_threshold_slider:.1f}). "
                    "Try lowering the threshold in ⚙️ Settings."
                )

            # ── Summary metric cards ──────────────────────────────────────────
            total_delta = sum(a.delta for a in anomalies)
            avg_z = sum(a.z_score for a in anomalies) / len(anomalies) if anomalies else 0
            inv_done = len(st.session_state.investigations)
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Total Anomalies", len(anomalies))
            m2.metric("Avg Z-Score", f"{avg_z:.2f}")
            m3.metric("Total Cost Impact", f"${total_delta:,.2f}")
            m4.metric("Investigated", f"{inv_done}/{len(anomalies)}")

            st.markdown("")

            # ── Plotly chart ──────────────────────────────────────────────────
            try:
                palette = theme.SERIES
                services = df["service"].unique().tolist()
                color_map = {s: palette[i % len(palette)] for i, s in enumerate(services)}

                fig = go.Figure()
                for service in services:
                    svc_df = df[df["service"] == service].sort_values("date")
                    fig.add_trace(
                        go.Scatter(
                            x=svc_df["date"],
                            y=svc_df["cost"],
                            mode="lines",
                            name=service,
                            line=dict(color=color_map[service], width=2.2, shape="spline", smoothing=0.55),
                            hovertemplate=(
                                f"<b>{service}</b><br>"
                                "Date: %{x|%Y-%m-%d}<br>"
                                "Cost: $%{y:.2f}<extra></extra>"
                            ),
                        )
                    )

                # anomaly_trace_idx: used below for click-event detection
                anomaly_trace_idx = len(services) + 1  # halo trace sits at len(services)

                if anomalies:
                    fig.add_trace(
                        go.Scatter(
                            x=[pd.Timestamp(a.date) for a in anomalies],
                            y=[a.cost for a in anomalies],
                            mode="markers",
                            hoverinfo="skip",
                            showlegend=False,
                            marker=dict(size=26, color="rgba(229,72,77,0.16)", line=dict(width=0)),
                        )
                    )
                    fig.add_trace(
                        go.Scatter(
                            x=[pd.Timestamp(a.date) for a in anomalies],
                            y=[a.cost for a in anomalies],
                            mode="markers",
                            name="Anomaly",
                            marker=dict(
                                symbol="circle",
                                size=12,
                                color=RED,
                                line=dict(width=3, color="#FFFFFF"),
                            ),
                            customdata=[
                                (
                                    f"<b>⚠ ANOMALY</b><br>"
                                    f"Service: {a.service}<br>"
                                    f"Cost: ${a.cost:.2f}<br>"
                                    f"Expected: ${a.expected_cost:.2f}<br>"
                                    f"Z-Score: {a.z_score:.2f}<br>"
                                    f"Delta: +${a.delta:.2f}"
                                )
                                for a in anomalies
                            ],
                            hovertemplate="%{customdata}<br><i>Click marker to investigate →</i><extra></extra>",
                        )
                    )

                theme.style_figure(fig, height=440)
                fig.update_layout(
                    yaxis_title="Daily cost ($)",
                    hovermode="closest",
                    clickmode="event+select",
                )
                timeline_event = st.plotly_chart(
                    fig,
                    width="stretch",
                    key="timeline_chart",
                    on_select="rerun",
                )

                # Handle clicks on anomaly markers (red diamonds)
                if (
                    anomalies
                    and timeline_event
                    and timeline_event.selection
                    and timeline_event.selection.points
                ):
                    for pt in timeline_event.selection.points:
                        curve_num = pt.get("curve_number", -1)
                        point_num = pt.get("point_number", pt.get("point_index", -1))
                        if curve_num == anomaly_trace_idx:
                            click_id = (curve_num, point_num)
                            if (
                                click_id != st.session_state._last_timeline_click
                                and 0 <= point_num < len(anomalies)
                            ):
                                st.session_state._last_timeline_click = click_id
                                _on_investigate(anomalies[point_num])
                                st.rerun()
                            break
            except Exception as exc:
                st.warning(f"Could not render cost chart: {exc}")

            # ── Anomaly table ─────────────────────────────────────────────────
            if anomalies:
                board = _board()
                done_keys = {
                    (r.anomaly.service, r.anomaly.date) for r in st.session_state.investigations
                }
                active_keys = {j.key for j in board.active_jobs()}
                pending = [
                    a for a in anomalies
                    if (a.service, a.date) not in done_keys and (a.service, a.date) not in active_keys
                ]

                col_left, col_right = st.columns([3, 1])
                with col_left:
                    st.subheader(f"Detected anomalies ({len(anomalies)})")
                    st.caption("Runs in the background, so you can keep exploring while the agents work.")
                with col_right:
                    if active_keys:
                        run_all_label = f"⏳ {len(active_keys)} running…"
                    elif pending:
                        run_all_label = f"⚡ Run All ({len(pending)} pending)"
                    else:
                        run_all_label = "✓ All investigated"
                    if st.button(
                        run_all_label,
                        disabled=(len(pending) == 0),
                        type="primary",
                        width="stretch",
                        key="run_all_btn",
                    ):
                        if _queue(pending):
                            st.rerun()

                sorted_anomalies = sorted(anomalies, key=lambda a: a.z_score, reverse=True)
                widths = [2.4, 1.7, 1.2, 1.3, 1.0, 1.3, 1.5, 1.6]

                hdr_cols = st.columns(widths)
                labels_hdr = ["Service", "Date", "Cost", "Expected", "Z-score", "Delta", "Status", ""]
                for idx_h, (col, lbl) in enumerate(zip(hdr_cols, labels_hdr)):
                    marker = '<span class="row-marker hdr"></span>' if idx_h == 0 else ""
                    col.markdown(f'{marker}<span class="col-h">{lbl}</span>', unsafe_allow_html=True)

                for i, a in enumerate(sorted_anomalies):
                    key = (a.service, a.date)
                    is_high = a.z_score > 3.0
                    is_investigated = key in done_keys
                    job = board.get(key)
                    err = st.session_state.job_errors.get(key)
                    row = st.columns(widths)
                    row[0].markdown(
                        f'<span class="row-marker{" hi" if is_high else ""}"></span>'
                        f'<span class="cell-svc">{a.service}</span>',
                        unsafe_allow_html=True,
                    )
                    row[1].markdown(f'<span class="cell-num">{a.date}</span>', unsafe_allow_html=True)
                    row[2].markdown(f'<span class="cell-num">${a.cost:,.2f}</span>', unsafe_allow_html=True)
                    row[3].markdown(f'<span class="cell-num">${a.expected_cost:,.2f}</span>', unsafe_allow_html=True)
                    z_cls = "z-hot" if is_high else "cell-num"
                    row[4].markdown(f'<span class="{z_cls}">{a.z_score:.2f}</span>', unsafe_allow_html=True)
                    row[5].markdown(f'<span class="cell-num">+${a.delta:,.2f}</span>', unsafe_allow_html=True)
                    if is_investigated:
                        row[6].markdown(theme.pill("done", "Done"), unsafe_allow_html=True)
                    elif job is not None and job.state == "running":
                        row[6].markdown(theme.pill("run", f"{job.step.title()}…"), unsafe_allow_html=True)
                    elif job is not None and job.state == "queued":
                        row[6].markdown(theme.pill("queued", "Queued"), unsafe_allow_html=True)
                    elif err:
                        row[6].markdown(theme.pill("fail", "Failed"), unsafe_allow_html=True)
                    else:
                        row[6].markdown(theme.pill("pending", "Pending"), unsafe_allow_html=True)

                    if is_investigated:
                        with row[7]:
                            st.markdown('<div class="btn-investigated">', unsafe_allow_html=True)
                            st.button(
                                "View report",
                                key=f"inv_{i}",
                                on_click=_on_investigate,
                                args=(a,),
                                width="stretch",
                            )
                            st.markdown('</div>', unsafe_allow_html=True)
                    elif job is not None and job.active:
                        row[7].button("Watch live", key=f"inv_{i}", on_click=_on_investigate, args=(a,), width="stretch")
                    else:
                        row[7].button(
                            "Retry" if err else "Investigate",
                            key=f"inv_{i}",
                            on_click=_on_investigate,
                            args=(a,),
                            width="stretch",
                        )

# ─────────────────────────────────────────────────────────────────────────────
# VIEW 2 — LIVE INVESTIGATION
# ─────────────────────────────────────────────────────────────────────────────
elif view == "Investigation":
    st.title("🕵️ Live Investigation")

    if not st.session_state.data_loaded:
        st.warning(
            "No data loaded. Go to the Timeline view and click **Load Demo Data** first."
        )
    elif st.session_state.selected_anomaly is None:
        st.warning("Select an anomaly from the **Timeline** view to begin an investigation.")
    else:
        anomaly: Anomaly = st.session_state.selected_anomaly

        # Guard: anomaly may be stale after page refresh
        current_anomaly_keys = {(a.service, a.date) for a in st.session_state.anomalies}
        if (anomaly.service, anomaly.date) not in current_anomaly_keys:
            st.warning(
                "The selected anomaly is no longer in the current dataset "
                "(the data may have been reloaded). Please select a new anomaly from Timeline."
            )
        else:
            st.markdown(
                f"""
                <div class="anomaly-callout">
                    <div style="font-size:1.15rem;font-weight:700;margin-bottom:6px">
                        {anomaly.service}
                        &nbsp;<span style="font-weight:400;opacity:0.65;font-size:0.95rem">
                        {anomaly.date}</span>
                    </div>
                    <span style="margin-right:18px">
                        💵 Cost <strong>${anomaly.cost:.2f}</strong>
                        &nbsp;<span style="opacity:0.55">vs expected ${anomaly.expected_cost:.2f}</span>
                    </span>
                    <span style="margin-right:18px">
                        📊 Z-Score <strong style="color:{RED}">{anomaly.z_score:.2f}</strong>
                    </span>
                    <span>
                        📈 Delta <strong style="color:{RED}">+${anomaly.delta:.2f}</strong>
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            inv: InvestigationReport | None = st.session_state.current_investigation

            # Sync from investigations list (handles batch-run results)
            if inv is None or inv.anomaly.service != anomaly.service or inv.anomaly.date != anomaly.date:
                cached = next(
                    (r for r in st.session_state.investigations
                     if r.anomaly.service == anomaly.service and r.anomaly.date == anomaly.date),
                    None,
                )
                if cached:
                    st.session_state.current_investigation = cached
                    inv = cached

            already_done = (
                inv is not None
                and inv.anomaly.service == anomaly.service
                and inv.anomaly.date == anomaly.date
            )

            if already_done:
                # ── Navigation bar ────────────────────────────────────────────
                invs_list = st.session_state.investigations
                if len(invs_list) > 1:
                    inv_labels = [f"{r.anomaly.service}  —  {r.anomaly.date}" for r in invs_list]
                    current_idx = next(
                        (i for i, r in enumerate(invs_list)
                         if r.anomaly.service == inv.anomaly.service and r.anomaly.date == inv.anomaly.date),
                        0,
                    )
                    nav_l, nav_c, nav_r = st.columns([1, 6, 1])
                    with nav_l:
                        st.button(
                            "← Prev",
                            disabled=(current_idx == 0),
                            width="stretch",
                            key="inv_prev",
                            on_click=_nav_prev,
                            help="Go to previous investigation",
                        )
                    with nav_c:
                        st.selectbox(
                            "Select investigation",
                            inv_labels,
                            index=current_idx,
                            key="inv_nav_sel",
                            label_visibility="collapsed",
                            on_change=_nav_select,
                        )
                    with nav_r:
                        st.button(
                            "Next →",
                            disabled=(current_idx == len(invs_list) - 1),
                            width="stretch",
                            key="inv_next",
                            on_click=_nav_next,
                            help="Go to next investigation",
                        )
                    st.markdown("")

                # ── Status banner ─────────────────────────────────────────────
                sev_html = _severity_badge(inv.anomaly.delta)
                st.markdown(
                    f"""
                    <div class="status-banner {_conf_class(inv.overall_confidence)}">
                        ● {_conf_label(inv.overall_confidence)}
                        &nbsp;&nbsp;{sev_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # ── Metrics strip ─────────────────────────────────────────────
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Elapsed", f"{inv.elapsed_seconds:.1f}s")
                m2.metric("Confidence", f"{inv.overall_confidence:.0%}")
                m3.metric("Hypotheses", len(inv.hypotheses))
                m4.metric("Ruled Out", len(inv.ruled_out))

                st.markdown("")

                # ── Mini event timeline ───────────────────────────────────────
                if inv.hypotheses:
                    try:
                        anomaly_ts = pd.Timestamp(inv.anomaly.date)
                        tl_fig = go.Figure()
                        tl_fig.add_trace(go.Scatter(
                            x=[anomaly_ts],
                            y=[1],
                            mode="markers+text",
                            marker=dict(symbol="circle", size=16, color=RED, line=dict(width=3, color="#FFFFFF")),
                            text=[f"⚠ {inv.anomaly.service}"],
                            textposition="top center",
                            name="Anomaly Spike",
                            hovertemplate=f"<b>Anomaly</b><br>{inv.anomaly.date}<br>Cost: ${inv.anomaly.cost:.2f}<extra></extra>",
                        ))
                        theme.style_figure(tl_fig, height=130, legend=False)
                        tl_fig.update_layout(
                            margin=dict(l=20, r=20, t=10, b=20),
                            xaxis=dict(showgrid=False, zeroline=False, title=""),
                            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, range=[0, 2], title=""),
                        )
                        st.plotly_chart(tl_fig, width="stretch")
                    except Exception:
                        pass  # Timeline is decorative; skip silently

                st.divider()

                # ── Report tabs ───────────────────────────────────────────────
                tab_sum, tab_ev, tab_ro, tab_rem = st.tabs(
                    ["📋 Summary", "🔗 Evidence Chain", "🚫 Ruled Out", "🔧 Remediation"]
                )

                with tab_sum:
                    if not inv.report_markdown or not inv.report_markdown.strip():
                        st.error(
                            "The report is empty — the Narrator agent may have returned no content. "
                            "Check your API key and retry."
                        )
                    else:
                        st.markdown(safe_md(inv.report_markdown))

                    dl_col, _ = st.columns([1, 3])
                    with dl_col:
                        st.download_button(
                            label="⬇️ Download Report (.md)",
                            data=inv.report_markdown or "",
                            file_name=(
                                f"{inv.anomaly.date}_"
                                f"{inv.anomaly.service.replace(' ', '_').replace('/', '_')}.md"
                            ),
                            mime="text/markdown",
                        )

                with tab_ev:
                    st.subheader(f"Hypotheses ({len(inv.hypotheses)})")
                    if not inv.hypotheses:
                        st.warning(
                            "No hypotheses were generated for this anomaly. "
                            "This can happen when the LLM cannot establish causal evidence. "
                            "Check the raw report in the Summary tab for details."
                        )
                    else:
                        for i_h in range(0, len(inv.hypotheses), 2):
                            ev_cols = st.columns(2 if len(inv.hypotheses) - i_h > 1 else 1)
                            for j_h, ev_col in enumerate(ev_cols):
                                idx_h = i_h + j_h
                                if idx_h >= len(inv.hypotheses):
                                    break
                                h = inv.hypotheses[idx_h]
                                conf_color = _confidence_color(h.confidence)
                                ev_count = len(h.evidence) if h.evidence else 0
                                with ev_col:
                                    with st.expander(
                                        f"#{h.rank}  {safe_md(h.root_cause[:70])}{'…' if len(h.root_cause) > 70 else ''}",
                                        expanded=(h.rank == 1),
                                    ):
                                        st.markdown(
                                            f'<div style="border-left:4px solid {conf_color};padding-left:10px">',
                                            unsafe_allow_html=True,
                                        )
                                        st.markdown(f"**Confidence:** {h.confidence:.0%}")
                                        st.progress(h.confidence)
                                        st.caption(f"📎 {ev_count} evidence item(s)")
                                        if h.evidence:
                                            for item in h.evidence:
                                                st.markdown(f"- {safe_md(item)}")
                                        if h.cost_calculation:
                                            st.markdown("**Cost Calculation:**")
                                            st.markdown(
                                                f'<div class="cost-box">{h.cost_calculation}</div>',
                                                unsafe_allow_html=True,
                                            )
                                        if h.causal_mechanism:
                                            st.info(safe_md(h.causal_mechanism))
                                        st.markdown('</div>', unsafe_allow_html=True)

                with tab_ro:
                    st.subheader(f"Ruled Out Events ({len(inv.ruled_out)})")
                    if not inv.ruled_out:
                        st.caption("No events were explicitly ruled out in this investigation.")
                    else:
                        hdr_ro = st.columns([2, 1.5, 3])
                        hdr_ro[0].markdown("**Event**")
                        hdr_ro[1].markdown("**Category**")
                        hdr_ro[2].markdown("**Reason**")
                        st.markdown(
                            "<hr style='margin:4px 0 8px 0;border:none;border-top:1px solid rgba(128,128,128,0.2)'>",
                            unsafe_allow_html=True,
                        )
                        for ro in inv.ruled_out:
                            date_str = ro.event_time[:10] if ro.event_time else "N/A"
                            row_cols = st.columns([2, 1.5, 3])
                            row_cols[0].write(f"{safe_md(ro.event_name)}\n\n_{date_str}_")
                            row_cols[1].markdown(_category_badge(ro.category), unsafe_allow_html=True)
                            row_cols[2].write(safe_md(ro.reason))
                            st.markdown(
                                "<hr style='margin:2px 0;border:none;border-top:1px solid rgba(128,128,128,0.1)'>",
                                unsafe_allow_html=True,
                            )

                with tab_rem:
                    if inv.remediation:
                        st.markdown(safe_md(
                            "\n".join(f"{n}. {step}" for n, step in enumerate(inv.remediation, start=1))
                        ))
                    else:
                        st.info("No remediation steps extracted.")
                    dl_rem_col, _ = st.columns([1, 3])
                    with dl_rem_col:
                        st.download_button(
                            label="⬇️ Download Report (.md)",
                            data=inv.report_markdown or "",
                            file_name=(
                                f"{inv.anomaly.date}_"
                                f"{inv.anomaly.service.replace(' ', '_').replace('/', '_')}_full.md"
                            ),
                            mime="text/markdown",
                            key="dl_rem",
                        )

            else:
                key = (anomaly.service, anomaly.date)
                job = _board().get(key)

                # Queue automatically when arriving from an "Investigate" click.
                if st.session_state._auto_run and not (job is not None and job.active):
                    st.session_state._auto_run = False
                    if _queue([anomaly]):
                        st.rerun()
                st.session_state._auto_run = False
                job = _board().get(key)

                if job is not None and job.active:
                    st.markdown("#### Pipeline running")
                    _render_job_panel(key)
                else:
                    err = st.session_state.job_errors.get(key)
                    if err:
                        st.error(err)
                        if job is not None and job.log:
                            st.markdown(theme.stepper_html(job.step, "failed", job.skipped, job.log), unsafe_allow_html=True)
                    _, has_ct = _get_cloudtrail_state()
                    if not has_ct:
                        st.warning(
                            "No CloudTrail logs loaded — the analysis will use the RAG knowledge base only. "
                            "Upload CloudTrail logs in the sidebar for full evidence-backed analysis."
                        )
                    st.info(
                        "Click **Run Investigation** to start the 4-agent pipeline. "
                        "It makes two LLM calls (Analyst + Narrator) and takes about 40–90 s. "
                        "It keeps running if you switch tabs."
                    )
                    if st.session_state.api_calls >= API_CALL_LIMIT:
                        st.error(
                            f"Session API limit reached ({API_CALL_LIMIT} calls). "
                            "Restart the app or use the Reset API Counter in ⚙️ Settings."
                        )
                    elif st.button("🚀 Run Investigation" if not err else "🔁 Retry Investigation", type="primary"):
                        if _queue([anomaly]):
                            st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# VIEW 3 — EVIDENCE EXPLORER
# ─────────────────────────────────────────────────────────────────────────────
elif view == "Evidence":
    st.title("🔬 Evidence Explorer")

    inv = st.session_state.current_investigation
    if not st.session_state.data_loaded:
        st.warning("Load data first using the sidebar.")
    elif inv is None:
        st.warning(
            "No investigation to display yet. "
            "Run one from the **Investigation** view."
        )
    else:
        conf_color_ev = _confidence_color(inv.overall_confidence)
        st.markdown(
            f"""
            <div class="info-card">
                <strong style="font-size:1.05rem">{inv.anomaly.service}</strong>
                &nbsp;&nbsp;<span style="opacity:0.65">{inv.anomaly.date}</span>
                &nbsp;&nbsp;·&nbsp;&nbsp;
                Overall confidence:
                <strong style="color:{conf_color_ev}">
                {inv.overall_confidence:.0%}
                </strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.subheader(f"Hypotheses ({len(inv.hypotheses)})")

        if not inv.hypotheses:
            st.warning(
                "No hypotheses were generated for this anomaly. "
                "This can happen when the LLM cannot establish causal evidence. "
                "Check the raw report in the **Investigation** view for details."
            )
        else:
            for i_h in range(0, len(inv.hypotheses), 2):
                ev_cols = st.columns(2 if len(inv.hypotheses) - i_h > 1 else 1)
                for j_h, ev_col in enumerate(ev_cols):
                    idx_h = i_h + j_h
                    if idx_h >= len(inv.hypotheses):
                        break
                    h = inv.hypotheses[idx_h]
                    conf_color = _confidence_color(h.confidence)
                    ev_count = len(h.evidence) if h.evidence else 0
                    with ev_col:
                        with st.expander(
                            f"#{h.rank}  {safe_md(h.root_cause[:70])}{'…' if len(h.root_cause) > 70 else ''}",
                            expanded=(h.rank == 1),
                        ):
                            st.markdown(
                                f'<div style="border-left:4px solid {conf_color};padding-left:10px">',
                                unsafe_allow_html=True,
                            )
                            st.markdown(f"**Confidence:** {h.confidence:.0%}")
                            st.progress(h.confidence)
                            st.caption(f"📎 {ev_count} evidence item(s)")
                            if h.evidence:
                                for item in h.evidence:
                                    st.markdown(f"- {safe_md(item)}")
                            if h.cost_calculation:
                                st.markdown("**Cost Calculation:**")
                                st.markdown(
                                    f'<div class="cost-box">{h.cost_calculation}</div>',
                                    unsafe_allow_html=True,
                                )
                            if h.causal_mechanism:
                                st.info(safe_md(h.causal_mechanism))
                            st.markdown('</div>', unsafe_allow_html=True)

        st.subheader(f"Ruled Out Events ({len(inv.ruled_out)})")

        if not inv.ruled_out:
            st.caption("No events were explicitly ruled out in this investigation.")
        else:
            hdr_ev = st.columns([2, 1.8, 3.5])
            hdr_ev[0].markdown("**Event**")
            hdr_ev[1].markdown("**Category**")
            hdr_ev[2].markdown("**Reason**")
            st.markdown(
                "<hr style='margin:4px 0 8px 0;border:none;border-top:1px solid rgba(128,128,128,0.2)'>",
                unsafe_allow_html=True,
            )
            for ro in inv.ruled_out:
                date_str = ro.event_time[:10] if ro.event_time else "N/A"
                row_cols = st.columns([2, 1.8, 3.5])
                row_cols[0].write(f"{safe_md(ro.event_name)}\n\n_{date_str}_")
                row_cols[1].markdown(_category_badge(ro.category), unsafe_allow_html=True)
                row_cols[2].write(safe_md(ro.reason))
                st.markdown(
                    "<hr style='margin:2px 0;border:none;border-top:1px solid rgba(128,128,128,0.1)'>",
                    unsafe_allow_html=True,
                )

# ─────────────────────────────────────────────────────────────────────────────
# VIEW 4 — COMPARE INVESTIGATIONS
# ─────────────────────────────────────────────────────────────────────────────
elif view == "Compare":
    st.title("⚖️ Compare Investigations")

    invs: list[InvestigationReport] = st.session_state.investigations

    if not st.session_state.data_loaded:
        st.warning("Load data and run at least 2 investigations first.")
    elif len(invs) == 0:
        st.info("No investigations completed yet. Run some from the **Timeline** view.")
    elif len(invs) == 1:
        st.info(
            "Only 1 investigation completed. "
            "Run at least one more to enable comparison."
        )
    else:
        labels = [f"{r.anomaly.service} — {r.anomaly.date}" for r in invs]

        sel_col_a, sel_col_b = st.columns(2)
        with sel_col_a:
            idx_a = st.selectbox(
                "Investigation A",
                range(len(labels)),
                format_func=lambda i: labels[i],
                key="cmp_sel_a",
            )
        with sel_col_b:
            default_b = 1 if len(labels) > 1 else 0
            idx_b = st.selectbox(
                "Investigation B",
                range(len(labels)),
                format_func=lambda i: labels[i],
                key="cmp_sel_b",
                index=default_b,
            )

        if idx_a == idx_b:
            st.warning("Both dropdowns point to the same investigation — select two different ones.")
        else:
            inv_a = invs[idx_a]
            inv_b = invs[idx_b]

            st.divider()

            col_a, col_b = st.columns(2)

            def _render_summary(inv: InvestigationReport, col) -> None:
                top = inv.hypotheses[0] if inv.hypotheses else None
                root_cause = (
                    (top.root_cause[:85] + "…")
                    if top and len(top.root_cause) > 85
                    else (top.root_cause if top else "—")
                )
                conf_color = _confidence_color(inv.overall_confidence)
                with col:
                    st.markdown(
                        f"""
                        <div class="info-card">
                            <div style="font-size:1.05rem;font-weight:700;margin-bottom:8px">
                                {inv.anomaly.service}
                            </div>
                            <p style="margin:2px 0"><b>Date:</b> {inv.anomaly.date}</p>
                            <p style="margin:2px 0">
                                <b>Cost:</b> ${inv.anomaly.cost:.2f}
                                <span style="opacity:0.55">
                                    (expected ${inv.anomaly.expected_cost:.2f})
                                </span>
                            </p>
                            <p style="margin:2px 0">
                                <b>Delta:</b>
                                <span style="color:{RED}">+${inv.anomaly.delta:.2f}</span>
                            </p>
                            <p style="margin:2px 0">
                                <b>Root Cause:</b> {root_cause}
                            </p>
                            <p style="margin:2px 0">
                                <b>Confidence:</b>
                                <span style="color:{conf_color};font-weight:700">
                                {inv.overall_confidence:.0%}
                                </span>
                            </p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

            _render_summary(inv_a, col_a)
            _render_summary(inv_b, col_b)

            st.subheader("Metrics Comparison")
            try:
                cmp_df = pd.DataFrame(
                    {
                        "Metric": [
                            "Overall Confidence",
                            "Evidence Items",
                            "Hypotheses",
                            "Ruled Out",
                            "Elapsed (s)",
                        ],
                        labels[idx_a]: [
                            f"{inv_a.overall_confidence:.0%}",
                            str(sum(len(h.evidence) for h in inv_a.hypotheses)),
                            str(len(inv_a.hypotheses)),
                            str(len(inv_a.ruled_out)),
                            f"{inv_a.elapsed_seconds:.1f}",
                        ],
                        labels[idx_b]: [
                            f"{inv_b.overall_confidence:.0%}",
                            str(sum(len(h.evidence) for h in inv_b.hypotheses)),
                            str(len(inv_b.hypotheses)),
                            str(len(inv_b.ruled_out)),
                            f"{inv_b.elapsed_seconds:.1f}",
                        ],
                    }
                )
                st.dataframe(cmp_df, hide_index=True, width="stretch")
            except Exception as exc:
                st.warning(f"Could not render comparison table: {exc}")

            st.subheader("Visual Comparison")
            try:
                ev_a = sum(len(h.evidence) for h in inv_a.hypotheses) if inv_a.hypotheses else 0
                ev_b = sum(len(h.evidence) for h in inv_b.hypotheses) if inv_b.hypotheses else 0

                bar_fig = go.Figure(data=[
                    go.Bar(
                        name=labels[idx_a][:30],
                        x=["Confidence", "Evidence Items", "Hypotheses", "Ruled Out"],
                        y=[inv_a.overall_confidence * 100, ev_a, len(inv_a.hypotheses), len(inv_a.ruled_out)],
                        marker_color=BLUE,
                        text=[f"{inv_a.overall_confidence:.0%}", ev_a, len(inv_a.hypotheses), len(inv_a.ruled_out)],
                        textposition="outside",
                    ),
                    go.Bar(
                        name=labels[idx_b][:30],
                        x=["Confidence", "Evidence Items", "Hypotheses", "Ruled Out"],
                        y=[inv_b.overall_confidence * 100, ev_b, len(inv_b.hypotheses), len(inv_b.ruled_out)],
                        marker_color=GREEN,
                        text=[f"{inv_b.overall_confidence:.0%}", ev_b, len(inv_b.hypotheses), len(inv_b.ruled_out)],
                        textposition="outside",
                    ),
                ])
                theme.style_figure(bar_fig, height=340)
                bar_fig.update_layout(barmode="group", bargap=0.35)
                bar_fig.update_traces(marker_line_width=0)
                st.plotly_chart(bar_fig, width="stretch")
            except Exception as exc:
                st.warning(f"Could not render comparison chart: {exc}")

            cats_a = {h.category for h in inv_a.hypotheses}
            cats_b = {h.category for h in inv_b.hypotheses}
            recurring = cats_a & cats_b
            if recurring:
                st.warning(
                    f"⚠️ **Recurring pattern:** category "
                    f"`{'`, `'.join(sorted(recurring))}` appears in both investigations. "
                    "This may indicate a systemic infrastructure issue."
                )

# ─────────────────────────────────────────────────────────────────────────────
# VIEW 5 — FEEDBACK
# ─────────────────────────────────────────────────────────────────────────────
elif view == "Feedback":
    st.title("💬 Feedback")

    inv = st.session_state.current_investigation
    if not st.session_state.data_loaded:
        st.warning("Load data and run an investigation first.")
    elif inv is None:
        st.warning("Run an investigation first, then come back here to rate it.")
    else:
        conf_color_fb = _confidence_color(inv.overall_confidence)
        st.markdown(
            f"""
            <div class="info-card">
                <strong>{inv.anomaly.service}</strong>
                &nbsp;·&nbsp; {inv.anomaly.date}
                &nbsp;·&nbsp; Confidence:
                <strong style="color:{conf_color_fb}">{inv.overall_confidence:.0%}</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

        feedback: dict = {
            "anomaly": {
                "service": inv.anomaly.service,
                "date": inv.anomaly.date,
                "z_score": inv.anomaly.z_score,
            },
            "hypotheses": [],
            "overall": "",
            "actual_root_cause": "",
            "timestamp": datetime.now().isoformat(),
        }

        if not inv.hypotheses:
            st.info(
                "This investigation produced no hypotheses to rate. "
                "You can still submit an overall verdict below."
            )
        else:
            st.subheader("Rate Each Hypothesis")
            for h in inv.hypotheses:
                st.markdown(
                    f"**Hypothesis {h.rank}** — "
                    f"{safe_md(h.root_cause[:110])}{'…' if len(h.root_cause) > 110 else ''}"
                )
                verdict = st.radio(
                    "Verdict",
                    ["Correct ✅", "Incorrect ❌", "Uncertain 🤔"],
                    key=f"fb_verdict_{h.rank}",
                    horizontal=True,
                )
                comment = st.text_input(
                    "Comment (optional)",
                    key=f"fb_comment_{h.rank}",
                    placeholder="e.g. 'Correct, but the instance type was actually m5.xlarge'",
                )
                feedback["hypotheses"].append(
                    {
                        "rank": h.rank,
                        "root_cause": h.root_cause,
                        "verdict": verdict,
                        "comment": comment,
                    }
                )
                st.divider()

        st.subheader("Overall Report Quality")
        overall = st.radio(
            "How would you rate this report?",
            ["Report is actionable", "Report needs corrections", "Report is wrong"],
            key="fb_overall",
        )
        actual_cause = st.text_area(
            "What was the actual root cause? (leave blank if report is correct)",
            key="fb_actual_cause",
            placeholder="Describe what you found when you investigated manually…",
        )

        feedback["overall"] = overall
        feedback["actual_root_cause"] = actual_cause

        if st.button("📤 Submit Feedback", type="primary"):
            try:
                feedback_dir = _ROOT / "data" / "feedback"
                feedback_dir.mkdir(parents=True, exist_ok=True)
                service_slug = (
                    inv.anomaly.service.lower()
                    .replace(" ", "_")
                    .replace("/", "_")
                )
                fname = feedback_dir / f"{inv.anomaly.date}_{service_slug}.json"
                fname.write_text(json.dumps(feedback, indent=2), encoding="utf-8")
                st.success(f"✅ Feedback saved → `{fname.relative_to(_ROOT)}`")
            except PermissionError:
                st.error("Permission denied writing to the feedback directory.")
            except Exception as exc:
                st.error(
                    f"Failed to save feedback. "
                    f"(Internal: {type(exc).__name__}: {exc})"
                )


# ─────────────────────────────────────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    "<div class='cs-footer'>"
    "CostSherlock v1.0 &nbsp;|&nbsp; Vatsal Naik &amp; Priti Ghosh "
    "&nbsp;|&nbsp; Northeastern University &nbsp;|&nbsp; "
    f"Model: <code>{MODEL_NAME}</code>"
    "</div>",
    unsafe_allow_html=True,
)
