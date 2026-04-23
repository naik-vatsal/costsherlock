"""CostSherlock Streamlit Dashboard — main application."""

from __future__ import annotations

import json
import logging
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.express as px
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
from agents.analyst import Analyst  # noqa: E402
from agents.detective import Detective  # noqa: E402
from agents.narrator import Narrator  # noqa: E402
from agents.sentinel import Sentinel  # noqa: E402
from pipeline import _extract_remediation  # noqa: E402

# ── Constants ─────────────────────────────────────────────────────────────────
DEMO_COST_PATH = str(_ROOT / "data" / "synthetic" / "demo_cost.json")
DEMO_CLOUDTRAIL_DIR = str(_ROOT / "data" / "synthetic" / "demo_cloudtrail")
MODEL_NAME = "claude-sonnet-4-20250514"
_INPUT_COST_PER_TOKEN = 3.00 / 1_000_000
_OUTPUT_COST_PER_TOKEN = 15.00 / 1_000_000
_CHARS_PER_TOKEN = 4.0

NAVY = "#1B2A4A"
BLUE = "#2563EB"
GREEN = "#059669"
RED = "#DC2626"
ORANGE = "#F97316"
VIEWS = ["Timeline", "Investigation", "Evidence", "Compare", "Feedback"]

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CostSherlock",
    page_icon="🔍",
    layout="wide",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <style>
        /* ── Header bar ───────────────────────────────────────────────────── */
        [data-testid="stHeader"] {{
            background-color: {NAVY};
            border-bottom: 2px solid #2563EB;
        }}
        /* Keep the Streamlit hamburger/deploy icons visible */
        [data-testid="stHeader"] button svg {{
            fill: #CBD5E1 !important;
        }}

        /* ── Main content area ────────────────────────────────────────────── */
        .main .block-container {{
            padding-top: 1.5rem;
            padding-bottom: 3rem;
        }}

        /* ── Sidebar ─────────────────────────────────────────────────────── */
        [data-testid="stSidebar"] {{
            background-color: {NAVY};
        }}
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] div {{
            color: #CBD5E1 !important;
        }}
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {{
            color: #FFFFFF !important;
        }}
        /* Brighten radio labels on hover */
        [data-testid="stSidebar"] [role="radio"]:hover label {{
            color: #FFFFFF !important;
        }}

        /* ── Anomaly callout card ─────────────────────────────────────────── */
        .anomaly-callout {{
            background: #FFFFFF;
            border-left: 5px solid {RED};
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(220, 38, 38, 0.12);
            padding: 16px 22px;
            margin-bottom: 18px;
        }}

        /* ── Generic info card (used in Compare, Evidence) ───────────────── */
        .info-card {{
            background: #FFFFFF;
            border-radius: 10px;
            box-shadow: 0 1px 6px rgba(0, 0, 0, 0.07);
            padding: 18px 22px;
            margin-bottom: 14px;
            border-top: 3px solid {BLUE};
        }}

        /* ── Anomaly table ────────────────────────────────────────────────── */
        .tbl-header {{
            background: {NAVY};
            border-radius: 8px 8px 0 0;
            padding: 8px 0 8px 0;
            margin-bottom: 2px;
        }}
        .tbl-header span {{
            color: #FFFFFF !important;
            font-weight: 700;
            font-size: 0.85rem;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }}
        .tbl-row {{
            border-bottom: 1px solid #F1F5F9;
            padding: 4px 0;
            transition: background 0.1s;
        }}
        .tbl-row-high {{
            background: #FEF2F2;
            border-bottom: 1px solid #FECACA;
        }}

        /* ── Cost calculation monospace box ──────────────────────────────── */
        .cost-box {{
            background: #F0FDF4;
            border: 1px solid {GREEN};
            border-radius: 8px;
            padding: 12px 16px;
            font-family: "Courier New", Courier, monospace;
            font-size: 0.87rem;
            white-space: pre-wrap;
            margin: 8px 0 12px 0;
        }}

        /* ── Category badge pill ─────────────────────────────────────────── */
        .cat-badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.73rem;
            font-weight: 700;
            color: #FFFFFF;
            letter-spacing: 0.04em;
            margin-bottom: 8px;
        }}

        /* ── Metric cards ────────────────────────────────────────────────── */
        /* Use Streamlit CSS variables so cards adapt to light AND dark theme */
        [data-testid="stMetric"] {{
            background: var(--secondary-background-color);
            border-radius: 10px;
            box-shadow: 0 1px 5px rgba(0, 0, 0, 0.07);
            padding: 14px 16px !important;
            border-left: 3px solid {BLUE};
        }}
        /* Label row — slightly muted but always readable */
        [data-testid="stMetric"] [data-testid="stMetricLabel"],
        [data-testid="stMetric"] [data-testid="stMetricLabel"] p,
        [data-testid="stMetric"] [data-testid="stMetricLabel"] span,
        [data-testid="stMetric"] [data-testid="stMetricLabel"] div {{
            color: var(--text-color) !important;
            opacity: 0.72;
            font-size: 0.8rem !important;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }}
        /* Value row — full weight, full contrast */
        [data-testid="stMetric"] [data-testid="stMetricValue"],
        [data-testid="stMetric"] [data-testid="stMetricValue"] * {{
            color: var(--text-color) !important;
            opacity: 1 !important;
            font-weight: 700 !important;
        }}
        /* Delta row (not used today but safe to pin) */
        [data-testid="stMetric"] [data-testid="stMetricDelta"] * {{
            opacity: 1 !important;
        }}

        /* ── Download button ─────────────────────────────────────────────── */
        [data-testid="stDownloadButton"] button {{
            border-color: {BLUE} !important;
            color: {BLUE} !important;
        }}

        /* ── Footer ──────────────────────────────────────────────────────── */
        .cs-footer {{
            text-align: center;
            color: #94A3B8;
            font-size: 0.78rem;
            padding: 24px 0 8px 0;
            border-top: 1px solid #E2E8F0;
            margin-top: 48px;
        }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state initialisation ──────────────────────────────────────────────
_DEFAULTS: dict = {
    "data_loaded": False,
    "cost_df": None,
    "anomalies": [],
    "selected_anomaly": None,
    "investigations": [],
    "current_investigation": None,
    "cloudtrail_logs": [],
    "api_calls": 0,
    "total_cost_estimate": 0.0,
    "current_view": "Timeline",
    "z_threshold_slider": 2.5,
    # deferred toast: set before st.rerun(), consumed once at next render
    "_pending_toast": "",
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Consume any pending toast immediately (must be before other UI) ────────────
if st.session_state._pending_toast:
    st.toast(st.session_state._pending_toast, icon="✅")
    st.session_state._pending_toast = ""

# ── Cached resources ──────────────────────────────────────────────────────────

@st.cache_resource
def _get_analyst() -> Analyst:
    return Analyst()


@st.cache_resource
def _get_narrator() -> Narrator:
    return Narrator()


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

def _estimate_api_cost(input_text: str, output_text: str) -> float:
    in_tok = len(input_text) / _CHARS_PER_TOKEN
    out_tok = len(output_text) / _CHARS_PER_TOKEN
    return in_tok * _INPUT_COST_PER_TOKEN + out_tok * _OUTPUT_COST_PER_TOKEN


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


def _ensure_cloudtrail() -> list[dict]:
    """Return CloudTrail events from session state, loading demo data as fallback."""
    if st.session_state.cloudtrail_logs:
        return st.session_state.cloudtrail_logs
    ct = _load_cloudtrail(DEMO_CLOUDTRAIL_DIR)
    st.session_state.cloudtrail_logs = ct
    return ct


def _persist_investigation(inv: InvestigationReport) -> None:
    """Store an InvestigationReport in session state, deduplicating by (service, date)."""
    st.session_state.current_investigation = inv
    existing = {(r.anomaly.service, r.anomaly.date) for r in st.session_state.investigations}
    if (inv.anomaly.service, inv.anomaly.date) not in existing:
        st.session_state.investigations.append(inv)


# ── Core pipeline logic (no Streamlit UI side-effects) ───────────────────────

def _pipeline_core(
    anomaly: Anomaly,
    ct_events: list[dict],
) -> tuple[InvestigationReport, str] | tuple[None, str]:
    """Run Sentinel→Detective→Analyst→Narrator for one anomaly.

    Returns:
        (InvestigationReport, "") on success, or (None, error_message) on failure.
    """
    t_start = time.monotonic()
    try:
        suspects = Detective.get_events_in_window(ct_events, anomaly)

        analysis = _get_analyst().analyze(anomaly, suspects)
        st.session_state.api_calls += 1

        hypotheses = analysis.get("hypotheses", [])
        ruled_out = analysis.get("ruled_out", [])

        report_md = _get_narrator().generate_report(anomaly, analysis)
        st.session_state.api_calls += 1

    except Exception as exc:
        logging.getLogger(__name__).exception("Pipeline error for %s", anomaly.service)
        return None, str(exc)

    elapsed = round(time.monotonic() - t_start, 2)
    cost_estimate = _estimate_api_cost(str(analysis) * 3, report_md)
    st.session_state.total_cost_estimate += cost_estimate

    inv = InvestigationReport(
        anomaly=anomaly,
        hypotheses=hypotheses,
        ruled_out=ruled_out,
        remediation=_extract_remediation(report_md),
        overall_confidence=hypotheses[0].confidence if hypotheses else 0.0,
        report_markdown=report_md,
        elapsed_seconds=elapsed,
    )
    return inv, ""


# ── Interactive single-anomaly runner (shows st.status with steps) ────────────

def _run_investigation(anomaly: Anomaly) -> None:
    """Execute the pipeline with live st.status progress, then rerun."""
    try:
        ct_events = _ensure_cloudtrail()
    except Exception as exc:
        st.error(f"Could not load CloudTrail logs: {exc}")
        return

    t_start = time.monotonic()

    try:
        with st.status("Running investigation pipeline…", expanded=True) as status:

            # Step 1 — Sentinel (instant)
            st.write("🔍 **Sentinel:** Anomaly confirmed")
            st.write(
                f"   Service `{anomaly.service}` · Date `{anomaly.date}` · "
                f"z = {anomaly.z_score:.2f} · δ = +${anomaly.delta:.2f}"
            )

            # Step 2 — Detective (fast, no LLM)
            st.write("🕵️ **Detective:** Correlating CloudTrail events…")
            suspects = Detective.get_events_in_window(ct_events, anomaly)
            st.write(f"   Found **{len(suspects)}** suspect event(s) in ±48 h window")

            # Step 3 — Analyst (slow LLM call)
            st.write("🧠 **Analyst:** Querying RAG knowledge base and reasoning…")
            with st.spinner("Analyst thinking — this may take 20–40 s…"):
                analysis = _get_analyst().analyze(anomaly, suspects)
            st.session_state.api_calls += 1
            hypotheses = analysis.get("hypotheses", [])
            ruled_out = analysis.get("ruled_out", [])
            st.write(
                f"   Generated **{len(hypotheses)}** hypothesis/hypotheses · "
                f"**{len(ruled_out)}** ruled out"
            )

            # Step 4 — Narrator (slow LLM call)
            st.write("📝 **Narrator:** Drafting cited investigation report…")
            with st.spinner("Narrator writing — usually 15–30 s…"):
                report_md = _get_narrator().generate_report(anomaly, analysis)
            st.session_state.api_calls += 1

            status.update(label="✅ Investigation complete!", state="complete")

    except Exception as exc:
        st.error(f"Investigation failed: {exc}")
        logging.getLogger(__name__).exception("Investigation error")
        return

    elapsed = round(time.monotonic() - t_start, 2)
    cost_estimate = _estimate_api_cost(str(analysis) * 3, report_md)
    st.session_state.total_cost_estimate += cost_estimate

    inv = InvestigationReport(
        anomaly=anomaly,
        hypotheses=hypotheses,
        ruled_out=ruled_out,
        remediation=_extract_remediation(report_md),
        overall_confidence=hypotheses[0].confidence if hypotheses else 0.0,
        report_markdown=report_md,
        elapsed_seconds=elapsed,
    )
    _persist_investigation(inv)

    top_conf = f"{hypotheses[0].confidence:.0%}" if hypotheses else "n/a"
    st.session_state._pending_toast = (
        f"Investigation done · {anomaly.service} · {anomaly.date} · "
        f"confidence {top_conf} · {elapsed:.1f}s"
    )
    st.rerun()


# ── Batch runner (used by "Run All Investigations") ───────────────────────────

def _run_all_investigations(anomalies: list[Anomaly]) -> None:
    """Process every anomaly sequentially with a progress bar, then rerun."""
    try:
        ct_events = _ensure_cloudtrail()
    except Exception as exc:
        st.error(f"Could not load CloudTrail logs: {exc}")
        return

    total = len(anomalies)
    if total == 0:
        st.warning("No anomalies to investigate.")
        return

    completed = 0
    failed: list[str] = []

    progress = st.progress(0.0, text="Starting batch investigation…")
    status_text = st.empty()

    for i, anomaly in enumerate(anomalies):
        progress.progress(i / total, text=f"Investigating {anomaly.service} ({i + 1}/{total})…")
        status_text.markdown(
            f"⏳ **{anomaly.service}** · {anomaly.date} · "
            f"z = {anomaly.z_score:.2f}"
        )

        # Skip if already investigated in this session
        existing_keys = {(r.anomaly.service, r.anomaly.date) for r in st.session_state.investigations}
        if (anomaly.service, anomaly.date) in existing_keys:
            status_text.markdown(f"⏭️ **{anomaly.service}** — already investigated, skipping")
            completed += 1
            continue

        with st.spinner(f"Running pipeline for {anomaly.service}…"):
            inv, err = _pipeline_core(anomaly, ct_events)

        if inv is not None:
            _persist_investigation(inv)
            completed += 1
        else:
            failed.append(f"{anomaly.service} ({anomaly.date}): {err}")

    progress.progress(1.0, text="Batch complete!")
    status_text.empty()

    if failed:
        st.warning(
            f"**{completed}/{total} succeeded.** Failed:\n"
            + "\n".join(f"- {f}" for f in failed)
        )
        st.session_state._pending_toast = (
            f"Batch done: {completed}/{total} succeeded, {len(failed)} failed"
        )
    else:
        st.session_state._pending_toast = (
            f"All {completed} investigations complete!"
        )

    st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("# 🔍 CostSherlock")
    st.markdown("*AWS Cost Anomaly Investigator*")
    st.divider()

    # Navigation — reads current_view so programmatic switches (e.g. "Investigate"
    # button) take effect on the next render via index=
    nav_choice = st.radio(
        "Navigation",
        VIEWS,
        index=VIEWS.index(st.session_state.current_view),
    )
    st.session_state.current_view = nav_choice

    st.divider()

    # ── Load Demo Data ────────────────────────────────────────────────────────
    if st.button("📥 Load Demo Data", width="stretch"):
        with st.spinner("Loading synthetic dataset…"):
            try:
                z = st.session_state.z_threshold_slider
                df = _load_cost_data(DEMO_COST_PATH)
                ct = _load_cloudtrail(DEMO_CLOUDTRAIL_DIR)
                anomaly_dicts = _detect_anomalies_cached(DEMO_COST_PATH, z)
                anomalies = [Anomaly(**a) for a in anomaly_dicts]
                st.session_state.update(
                    {
                        "data_loaded": True,
                        "cost_df": df,
                        "cloudtrail_logs": ct,
                        "anomalies": anomalies,
                    }
                )
                st.success(
                    f"✓ {len(anomalies)} anomaly/anomalies across "
                    f"{df['service'].nunique()} services"
                )
            except Exception as exc:
                st.error(f"Load failed: {exc}")

    # ── Custom file upload ────────────────────────────────────────────────────
    uploaded = st.file_uploader("Upload Cost JSON", type=["json"])
    if uploaded is not None:
        with st.spinner("Parsing uploaded file…"):
            try:
                with tempfile.NamedTemporaryFile(
                    suffix=".json", delete=False, mode="wb"
                ) as tmp:
                    tmp.write(uploaded.read())
                    tmp_path = tmp.name
                df = Sentinel.load_from_json(tmp_path)
                z = st.session_state.z_threshold_slider
                anomalies = Sentinel.detect_anomalies(df, z_threshold=z)
                st.session_state.update(
                    {
                        "data_loaded": True,
                        "cost_df": df,
                        "anomalies": anomalies,
                    }
                )
                st.success(f"✓ {len(anomalies)} anomaly/anomalies detected")
            except json.JSONDecodeError:
                st.error("Invalid JSON — check file format.")
            except ValueError as exc:
                st.error(f"Schema error: {exc}")
            except Exception as exc:
                st.error(f"Upload failed: {exc}")

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

    # ── Session stats ─────────────────────────────────────────────────────────
    st.caption(f"**Model:** `{MODEL_NAME}`")
    st.caption(f"**API calls:** {st.session_state.api_calls}")
    st.caption(f"**Est. API cost:** `${st.session_state.total_cost_estimate:.4f}`")
    inv_count = len(st.session_state.investigations)
    st.caption(f"**Investigations:** {inv_count}")


# ═════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT — dispatch on current_view
# ═════════════════════════════════════════════════════════════════════════════

view = st.session_state.current_view

# ─────────────────────────────────────────────────────────────────────────────
# VIEW 1 — ANOMALY TIMELINE
# ─────────────────────────────────────────────────────────────────────────────
if view == "Timeline":
    st.title("📈 Anomaly Timeline")

    if not st.session_state.data_loaded:
        st.info(
            "👈 Click **Load Demo Data** in the sidebar to get started, "
            "or upload your own Cost Explorer JSON export."
        )
    else:
        df: pd.DataFrame = st.session_state.cost_df
        anomalies: list[Anomaly] = st.session_state.anomalies

        if df is None or df.empty:
            st.error("Loaded dataset is empty. Please reload or upload a different file.")
        else:
            # ── Plotly chart ──────────────────────────────────────────────────
            palette = px.colors.qualitative.Set2
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
                        line=dict(color=color_map[service], width=1.8),
                        hovertemplate=(
                            f"<b>{service}</b><br>"
                            "Date: %{x|%Y-%m-%d}<br>"
                            "Cost: $%{y:.2f}<extra></extra>"
                        ),
                    )
                )

            if anomalies:
                fig.add_trace(
                    go.Scatter(
                        x=[pd.Timestamp(a.date) for a in anomalies],
                        y=[a.cost for a in anomalies],
                        mode="markers",
                        name="Anomaly",
                        marker=dict(
                            symbol="diamond",
                            size=14,
                            color=RED,
                            line=dict(width=2, color="darkred"),
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
                        hovertemplate="%{customdata}<extra></extra>",
                    )
                )

            fig.update_layout(
                paper_bgcolor="white",
                plot_bgcolor="white",
                legend=dict(
                    orientation="v",
                    x=1.01,
                    y=1.0,
                    bgcolor="rgba(0,0,0,0)",
                ),
                xaxis=dict(showgrid=True, gridcolor="#E5E7EB", title="Date"),
                yaxis=dict(showgrid=True, gridcolor="#E5E7EB", title="Daily Cost ($)"),
                hovermode="closest",
                margin=dict(l=60, r=40, t=40, b=60),
            )
            st.plotly_chart(fig, width="stretch")

            # ── Anomaly table ─────────────────────────────────────────────────
            col_left, col_right = st.columns([3, 1])
            with col_left:
                st.subheader(f"Detected Anomalies ({len(anomalies)})")
            with col_right:
                already_done = {
                    (r.anomaly.service, r.anomaly.date)
                    for r in st.session_state.investigations
                }
                pending = [
                    a for a in anomalies
                    if (a.service, a.date) not in already_done
                ]
                run_all_label = (
                    f"⚡ Run All ({len(pending)} pending)"
                    if pending
                    else "⚡ All Investigated"
                )
                run_all_disabled = len(pending) == 0
                if st.button(
                    run_all_label,
                    disabled=run_all_disabled,
                    type="primary",
                    width="stretch",
                    key="run_all_btn",
                ):
                    _run_all_investigations(anomalies)

            if not anomalies:
                st.info(
                    "No anomalies detected at the current z-score threshold "
                    f"({st.session_state.z_threshold_slider:.1f}). "
                    "Try lowering the threshold in ⚙️ Settings."
                )
            else:
                sorted_anomalies = sorted(anomalies, key=lambda a: a.z_score, reverse=True)

                # Styled table header
                hdr_cols = st.columns([2.5, 2, 1.4, 1.4, 1.2, 1.5, 1.5])
                labels = ["Service", "Date", "Cost", "Expected", "Z-Score", "Delta ($)", "Action"]
                for col, lbl in zip(hdr_cols, labels):
                    col.markdown(
                        f"<span style='font-weight:700;color:{NAVY};font-size:0.82rem;"
                        f"text-transform:uppercase;letter-spacing:0.04em'>{lbl}</span>",
                        unsafe_allow_html=True,
                    )
                st.markdown(
                    f"<hr style='margin:4px 0 6px 0;border:none;border-top:2px solid {NAVY}'>",
                    unsafe_allow_html=True,
                )

                for i, a in enumerate(sorted_anomalies):
                    is_high = a.z_score > 3.0
                    row = st.columns([2.5, 2, 1.4, 1.4, 1.2, 1.5, 1.5])
                    row[0].write(a.service)
                    row[1].write(a.date)
                    row[2].write(f"${a.cost:.2f}")
                    row[3].write(f"${a.expected_cost:.2f}")
                    if is_high:
                        row[4].markdown(f"**:red[{a.z_score:.2f}]**")
                    else:
                        row[4].write(f"{a.z_score:.2f}")
                    row[5].write(f"${a.delta:.2f}")
                    if row[6].button("🔍 Investigate", key=f"inv_{i}"):
                        st.session_state.selected_anomaly = a
                        st.session_state.current_view = "Investigation"
                        st.rerun()
                    # Thin row separator
                    st.markdown(
                        f"<hr style='margin:2px 0;border:none;"
                        f"border-top:1px solid {'#FECACA' if is_high else '#F1F5F9'}'>",
                        unsafe_allow_html=True,
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

        # Rounded anomaly summary card
        st.markdown(
            f"""
            <div class="anomaly-callout">
                <div style="font-size:1.15rem;font-weight:700;color:{NAVY};margin-bottom:6px">
                    {anomaly.service}
                    &nbsp;<span style="font-weight:400;color:#6B7280;font-size:0.95rem">
                    {anomaly.date}</span>
                </div>
                <span style="margin-right:18px">
                    💵 Cost <strong>${anomaly.cost:.2f}</strong>
                    &nbsp;<span style="color:#9CA3AF">vs expected ${anomaly.expected_cost:.2f}</span>
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
        already_done = (
            inv is not None
            and inv.anomaly.service == anomaly.service
            and inv.anomaly.date == anomaly.date
        )

        if already_done:
            # Metrics strip
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Elapsed", f"{inv.elapsed_seconds:.1f}s")
            m2.metric("Confidence", f"{inv.overall_confidence:.0%}")
            m3.metric("Hypotheses", len(inv.hypotheses))
            m4.metric("Ruled Out", len(inv.ruled_out))

            st.divider()

            if not inv.report_markdown:
                st.error(
                    "The report is empty — the Narrator agent may have returned no content. "
                    "Check your API key and retry."
                )
            else:
                st.markdown(inv.report_markdown)

            dl_col, _ = st.columns([1, 3])
            with dl_col:
                st.download_button(
                    label="⬇️ Download Report (.md)",
                    data=inv.report_markdown,
                    file_name=(
                        f"{inv.anomaly.date}_"
                        f"{inv.anomaly.service.replace(' ', '_').replace('/', '_')}.md"
                    ),
                    mime="text/markdown",
                )
        else:
            if not st.session_state.cloudtrail_logs:
                st.info(
                    "ℹ️ No CloudTrail logs loaded — the demo CloudTrail dataset will be "
                    "used automatically when you run the investigation."
                )
            st.info(
                "Click **Run Investigation** to start the 4-agent pipeline. "
                "This makes two LLM API calls (Analyst + Narrator) and takes ~60–90 s."
            )
            if st.button("🚀 Run Investigation", type="primary"):
                _run_investigation(anomaly)

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
        # Investigation header card
        st.markdown(
            f"""
            <div class="info-card">
                <strong style="font-size:1.05rem;color:{NAVY}">{inv.anomaly.service}</strong>
                &nbsp;&nbsp;<span style="color:#6B7280">{inv.anomaly.date}</span>
                &nbsp;&nbsp;·&nbsp;&nbsp;
                Overall confidence:
                <strong style="color:{GREEN if inv.overall_confidence >= 0.8
                                       else (ORANGE if inv.overall_confidence >= 0.55
                                             else RED)}">
                {inv.overall_confidence:.0%}
                </strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── Hypotheses ────────────────────────────────────────────────────────
        st.subheader(f"Hypotheses ({len(inv.hypotheses)})")

        if not inv.hypotheses:
            st.warning(
                "No hypotheses were generated for this anomaly. "
                "This can happen when the LLM cannot establish causal evidence. "
                "Check the raw report in the **Investigation** view for details."
            )
        else:
            for h in inv.hypotheses:
                with st.expander(
                    f"Hypothesis {h.rank}: {h.root_cause[:80]}{'…' if len(h.root_cause) > 80 else ''}"
                    f"  —  {h.confidence:.0%} confidence"
                ):
                    st.progress(
                        h.confidence,
                        text=f"Confidence: {h.confidence:.0%}",
                    )

                    st.markdown("**Evidence:**")
                    if h.evidence:
                        for item in h.evidence:
                            st.markdown(f"- {item}")
                    else:
                        st.caption("No evidence items recorded.")

                    st.markdown("**Cost Calculation:**")
                    if h.cost_calculation:
                        st.markdown(
                            f'<div class="cost-box">{h.cost_calculation}</div>',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.caption("No cost calculation available.")
                    st.markdown("")

                    st.markdown("**Causal Mechanism:**")
                    if h.causal_mechanism:
                        st.info(h.causal_mechanism)
                    else:
                        st.caption("No causal mechanism recorded.")

        # ── Ruled-out events ──────────────────────────────────────────────────
        st.subheader(f"Ruled Out Events ({len(inv.ruled_out)})")

        if not inv.ruled_out:
            st.caption("No events were explicitly ruled out in this investigation.")
        else:
            for ro in inv.ruled_out:
                date_str = ro.event_time[:10] if ro.event_time else "N/A"
                with st.expander(f"{ro.event_name}  ·  {date_str}"):
                    st.markdown(_category_badge(ro.category), unsafe_allow_html=True)
                    st.markdown(f"**Reason:** {ro.reason}")

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

            # ── Side-by-side summary cards ────────────────────────────────────
            col_a, col_b = st.columns(2)

            def _render_summary(inv: InvestigationReport, col) -> None:
                top = inv.hypotheses[0] if inv.hypotheses else None
                root_cause = (top.root_cause[:85] + "…") if top and len(top.root_cause) > 85 else (top.root_cause if top else "—")
                conf_color = (
                    GREEN if inv.overall_confidence >= 0.8
                    else (ORANGE if inv.overall_confidence >= 0.55 else RED)
                )
                with col:
                    st.markdown(
                        f"""
                        <div class="info-card">
                            <div style="font-size:1.05rem;font-weight:700;
                                        color:{NAVY};margin-bottom:8px">
                                {inv.anomaly.service}
                            </div>
                            <p style="margin:2px 0"><b>Date:</b> {inv.anomaly.date}</p>
                            <p style="margin:2px 0">
                                <b>Cost:</b> ${inv.anomaly.cost:.2f}
                                <span style="color:#9CA3AF">
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

            # ── Metrics comparison table ──────────────────────────────────────
            st.subheader("Metrics Comparison")
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

            # ── Recurring pattern detection ───────────────────────────────────
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
        st.markdown(
            f"""
            <div class="info-card">
                <strong style="color:{NAVY}">{inv.anomaly.service}</strong>
                &nbsp;·&nbsp; {inv.anomaly.date}
                &nbsp;·&nbsp; Confidence: <strong>{inv.overall_confidence:.0%}</strong>
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
                    f"{h.root_cause[:110]}{'…' if len(h.root_cause) > 110 else ''}"
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
                st.error(f"Failed to save feedback: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# FOOTER (rendered on every view)
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    "<div class='cs-footer'>"
    "CostSherlock v1.0 &nbsp;|&nbsp; Vatsal Naik &amp; Priti Ghosh "
    "&nbsp;|&nbsp; Northeastern University"
    "</div>",
    unsafe_allow_html=True,
)
