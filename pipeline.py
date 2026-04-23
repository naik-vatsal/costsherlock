"""CostSherlock Pipeline — orchestrates all 4 agents end-to-end."""

from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path

from agents import Anomaly, InvestigationReport, RuledOutEvent
from agents.analyst import Analyst
from agents.detective import Detective
from agents.narrator import Narrator
from agents.sentinel import Sentinel

logger = logging.getLogger(__name__)

# Maximum anomalies to investigate per run (by z-score descending).
MAX_ANOMALIES = 5

# Extract remediation steps from the Narrator's markdown under "## Remediation".
import re as _re

_REMEDIATION_RE = _re.compile(
    r"## Remediation\s*\n(.*?)(?=\n## |\Z)", _re.DOTALL
)
_NUMBERED_STEP_RE = _re.compile(r"^\s*\d+\.\s+(.+)", _re.MULTILINE)


def _extract_remediation(report_markdown: str) -> list[str]:
    """Pull numbered steps from the Remediation section of the report.

    Args:
        report_markdown: Full report markdown string.

    Returns:
        List of plain-text remediation step strings (without the leading
        number).  Empty list if the section is absent or has no steps.
    """
    match = _REMEDIATION_RE.search(report_markdown)
    if not match:
        return []
    return _NUMBERED_STEP_RE.findall(match.group(1))


def _safe_filename(service: str, date: str) -> str:
    """Build a safe filename stem from service name and date."""
    slug = _re.sub(r"[^a-z0-9]+", "_", service.lower()).strip("_")
    return f"{date}_{slug}"


class CostSherlockPipeline:
    """Orchestrates Sentinel → Detective → Analyst → Narrator for a dataset.

    Usage::

        pipeline = CostSherlockPipeline()
        reports = pipeline.investigate(
            cost_data_path="data/synthetic/demo_cost.json",
            cloudtrail_dir="data/synthetic/demo_cloudtrail",
        )
    """

    def __init__(self, output_dir: str = "reports") -> None:
        """Initialise the pipeline and all four agents.

        Args:
            output_dir: Root directory where markdown reports are saved.
                Created automatically if it does not exist.
        """
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Initialising agents…")
        self._sentinel = Sentinel()
        self._detective = Detective()
        self._analyst = Analyst()
        self._narrator = Narrator()

        # Lightweight token-usage tracking (input + output tokens per call).
        self._api_calls: int = 0
        self._input_tokens: int = 0
        self._output_tokens: int = 0

        logger.info("All agents ready.")

    # ── Public interface ──────────────────────────────────────────────────────

    def investigate(
        self,
        cost_data_path: str,
        cloudtrail_dir: str,
        output_subdir: str = "",
    ) -> list[InvestigationReport]:
        """Run the full investigation pipeline on a dataset.

        Steps:
            1. Sentinel detects anomalies from the cost export.
            2. Detective loads CloudTrail logs (once, reused for all anomalies).
            3. For each anomaly (top-5 by z-score):
               a. Detective correlates CloudTrail events.
               b. Analyst generates ranked hypotheses via RAG + LLM.
               c. Narrator renders a cited markdown report.
               d. InvestigationReport is assembled with timing metadata.
            4. Each report is saved as a ``.md`` file under *output_dir*.

        Args:
            cost_data_path: Path to a Cost Explorer JSON export.
            cloudtrail_dir: Directory containing CloudTrail ``.json`` files.
            output_subdir: Optional sub-directory under *output_dir* for
                this run's reports (e.g. ``"demo"`` → ``reports/demo/``).

        Returns:
            List of :class:`~agents.InvestigationReport` objects, one per
            anomaly processed, sorted by z-score descending.
        """
        pipeline_start = time.monotonic()

        # ── Step 1: Sentinel ─────────────────────────────────────────────────
        logger.info("=== Stage 1/4: Sentinel — anomaly detection ===")
        stage_t = time.monotonic()
        df = Sentinel.load_from_json(cost_data_path)
        all_anomalies = Sentinel.detect_anomalies(df)
        anomalies = all_anomalies[:MAX_ANOMALIES]
        logger.info(
            "Sentinel: %d total anomalies detected, investigating top %d "
            "(%.2fs)",
            len(all_anomalies),
            len(anomalies),
            time.monotonic() - stage_t,
        )

        if not anomalies:
            logger.warning("No anomalies found — pipeline returning empty list.")
            return []

        # ── Step 2: Detective (load logs once) ───────────────────────────────
        logger.info("=== Stage 2/4: Detective — loading CloudTrail logs ===")
        stage_t = time.monotonic()
        ct_events = Detective.load_cloudtrail_logs(cloudtrail_dir)
        logger.info(
            "Detective: loaded %d CloudTrail events (%.2fs)",
            len(ct_events),
            time.monotonic() - stage_t,
        )

        # ── Step 3–4: per-anomaly investigation ──────────────────────────────
        save_dir = self._output_dir / output_subdir if output_subdir else self._output_dir
        save_dir.mkdir(parents=True, exist_ok=True)

        reports: list[InvestigationReport] = []

        for idx, anomaly in enumerate(anomalies, start=1):
            logger.info(
                "=== Anomaly %d/%d: %s on %s (z=%.2f, delta=$%.2f) ===",
                idx,
                len(anomalies),
                anomaly.service,
                anomaly.date,
                anomaly.z_score,
                anomaly.delta,
            )
            report = self._investigate_one(anomaly, ct_events, save_dir)
            reports.append(report)

        # ── Summary log ──────────────────────────────────────────────────────
        total_elapsed = time.monotonic() - pipeline_start
        logger.info(
            "=== Pipeline complete ===\n"
            "  Anomalies processed : %d\n"
            "  LLM API calls       : %d\n"
            "  Total elapsed       : %.1fs\n"
            "  Reports saved to    : %s",
            len(reports),
            self._api_calls,
            total_elapsed,
            save_dir,
        )

        return reports

    # ── Private helpers ───────────────────────────────────────────────────────

    def _investigate_one(
        self,
        anomaly: Anomaly,
        ct_events: list[dict],
        save_dir: Path,
    ) -> InvestigationReport:
        """Run the Analyst + Narrator stages for a single anomaly.

        Args:
            anomaly: The anomaly to investigate.
            ct_events: Pre-loaded flat list of CloudTrail events.
            save_dir: Directory to save the generated markdown report.

        Returns:
            Populated :class:`~agents.InvestigationReport`.
        """
        start = time.monotonic()

        # 3a. Detective — correlate
        suspects = Detective.get_events_in_window(ct_events, anomaly)
        logger.info("  Detective: %d suspect events", len(suspects))

        # 3b. Analyst — RAG + LLM reasoning
        logger.info("  Analyst: calling LLM…")
        t = time.monotonic()
        analysis = self._analyst.analyze(anomaly, suspects)
        self._api_calls += 1
        logger.info("  Analyst: done in %.1fs", time.monotonic() - t)

        # 3c. Narrator — report generation
        logger.info("  Narrator: calling LLM…")
        t = time.monotonic()
        report_md = self._narrator.generate_report(anomaly, analysis)
        self._api_calls += 1
        logger.info("  Narrator: done in %.1fs", time.monotonic() - t)

        # 3d. Assemble InvestigationReport
        hypotheses = analysis.get("hypotheses", [])
        ruled_out: list[RuledOutEvent] = analysis.get("ruled_out", [])
        overall_confidence = hypotheses[0].confidence if hypotheses else 0.0
        remediation = _extract_remediation(report_md)
        elapsed = round(time.monotonic() - start, 2)

        inv_report = InvestigationReport(
            anomaly=anomaly,
            hypotheses=hypotheses,
            ruled_out=ruled_out,
            remediation=remediation,
            overall_confidence=overall_confidence,
            report_markdown=report_md,
            elapsed_seconds=elapsed,
        )

        # Save markdown to disk
        filename = _safe_filename(anomaly.service, anomaly.date) + ".md"
        report_path = save_dir / filename
        report_path.write_text(report_md, encoding="utf-8")
        logger.info(
            "  Saved report → %s  (%.1fs total for this anomaly)",
            report_path,
            elapsed,
        )

        return inv_report


# ── CLI ───────────────────────────────────────────────────────────────────────

def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="CostSherlock — investigate AWS cost anomalies",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--cost",
        default="data/synthetic/demo_cost.json",
        metavar="FILE",
        help="Path to Cost Explorer JSON export",
    )
    p.add_argument(
        "--logs",
        default="data/synthetic/demo_cloudtrail",
        metavar="DIR",
        help="Directory containing CloudTrail JSON files",
    )
    p.add_argument(
        "--output",
        default="reports",
        metavar="DIR",
        help="Directory to write markdown reports",
    )
    p.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable DEBUG logging",
    )
    return p


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    args = _build_arg_parser().parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    pipeline = CostSherlockPipeline(output_dir=args.output)
    reports = pipeline.investigate(
        cost_data_path=args.cost,
        cloudtrail_dir=args.logs,
    )

    print(f"\n{'='*60}")
    print(f"  CostSherlock — {len(reports)} report(s) generated")
    print(f"{'='*60}")
    for r in reports:
        conf_pct = int(r.overall_confidence * 100)
        root = r.hypotheses[0].root_cause[:70] if r.hypotheses else "INSUFFICIENT_EVIDENCE"
        print(
            f"  {r.anomaly.service:<22} {r.anomaly.date}  "
            f"δ=${r.anomaly.delta:>8.2f}  "
            f"conf={conf_pct:>3}%  {r.elapsed_seconds:.1f}s"
        )
        print(f"    {root}")
    print(f"{'='*60}\n")
