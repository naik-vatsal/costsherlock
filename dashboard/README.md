# CostSherlock Dashboard

The CostSherlock Streamlit dashboard (`dashboard/app.py`) provides five purpose-built views
for investigating, exploring, and auditing AWS cost anomalies.

---

## Running the Dashboard

```bash
# From the project root with the virtualenv active:
streamlit run dashboard/app.py
```

Opens at `http://localhost:8501` by default. On first load, the dashboard ingests
the synthetic demo data automatically — no AWS account required.

---

## Views

### 1. Timeline

The landing view. Shows:
- **Cost trend chart** — interactive Plotly line chart with anomaly markers overlaid,
  spanning the full date range of the loaded cost data.
- **KPI cards** — total anomalies detected, highest z-score, total excess spend ($),
  and number of affected services.
- **Anomaly table** — sortable table with one row per anomaly: service, date, observed
  cost, delta, z-score, severity badge, and an **Investigate** button that auto-runs
  the full pipeline and switches to the Investigation view.

### 2. Investigation

The primary report view. Shows:
- **Status banner** — severity (Critical / Warning / Info), delta, and confidence score
  (text label always shown, e.g. "HIGH CONFIDENCE (85%)", not just a colour indicator).
- **7-section markdown report** — Executive Summary, Root Cause Analysis, Cost Breakdown,
  Evidence Chain, Ruled Out, Remediation, Confidence & Caveats — rendered with full
  markdown formatting.
- **Navigation bar** — Previous / Next buttons and a select box to jump between all
  investigated anomalies without re-running the pipeline.

> **Work boundary note:** When no CloudTrail logs have been uploaded, the dashboard
> skips the Detective step and runs Analyst + Narrator in RAG-only mode. The dashboard
> detects this condition and shows a warning banner; the fallback logic itself is
> implemented in Vatsal's Analyst agent (`agents/analyst.py`).

### 3. Evidence Explorer

Detailed evidence breakdown, one expandable card per hypothesis:
- Evidence items (raw strings from the Analyst agent)
- Quantitative cost calculation
- Causal mechanism explanation
- Ruled-out events with reason categories
  (`WRONG_MECHANISM`, `WRONG_MAGNITUDE`, `TEMPORAL_ONLY`, etc.)

### 4. Compare

Cross-anomaly comparison view:
- **Grouped bar chart** (Plotly) — expected vs. actual cost for every investigated
  anomaly, side by side.
- **Confidence table** — service, date, delta, confidence score, and top hypothesis
  category for all investigations in the current session.

### 5. Feedback

Human audit interface for closing the feedback loop:
- **Per-hypothesis rating** — thumbs up/down on each hypothesis.
- **Overall actionability** — radio: "Report is actionable" / "Report is not actionable".
- **Actual root cause** — free-text field for the engineer's ground-truth correction.
- **Submit** — saves a timestamped JSON file to `data/feedback/`. These files are
  read by `evaluation/metrics.py` (Human Audit Pass Rate metric) and can be ingested
  back into ChromaDB to improve future investigations.

---

## Session State Keys

Key session state variables managed by the dashboard:

| Key | Type | Description |
|-----|------|-------------|
| `data_loaded` | bool | Whether cost data has been loaded |
| `cost_df` | DataFrame | Loaded cost time series |
| `anomalies` | list[Anomaly] | Detected anomalies from Sentinel |
| `investigations` | list[InvestigationReport] | Completed investigation reports |
| `current_investigation` | InvestigationReport | Report shown in Investigation view |
| `current_view` | str | Active navigation tab |
| `_auto_run` | bool | Trigger flag for auto-running the pipeline |

---

## Navigation Design

**The central UX question for multi-report navigation:** how do we make jumping between
several investigation reports feel instant and fluid, without forcing the user to
re-run expensive LLM pipelines for reports they've already seen?

Three design decisions address this:

1. **Cached results** — every completed `InvestigationReport` is stored in
   `st.session_state.investigations`. Switching to an already-investigated anomaly
   loads from cache; no API calls are made.

2. **Auto-run on click** — when the user clicks *Investigate* (table button or chart
   marker), the dashboard sets `_auto_run = True` and switches view to Investigation.
   If the result is cached, `_auto_run` stays `False` and the cached report displays
   immediately. The user never waits unnecessarily.

3. **In-view Previous / Next navigation** — once in the Investigation view, the user
   can step through all completed reports with `← Prev` / `Next →` buttons or a
   select box, all without leaving the view. The anomaly table in Timeline is only
   needed to start new investigations.

**Implementation:** these behaviours are wired through Streamlit `on_click` / `on_change`
callbacks (`_nav_prev`, `_nav_next`, `_nav_select`, `_on_investigate`) that mutate
session state before the rerun cycle, avoiding Streamlit's race condition between widget
state and `index=` parameters. Clickable chart markers use Plotly's `on_select` event
with `clickmode="event+select"` to feed directly into the same `_on_investigate` path.

---

*Priti Ghosh — Northeastern University — INFO 7375 Generative AI*
