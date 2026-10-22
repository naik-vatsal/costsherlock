"""CostSherlock visual system: design tokens, CSS, 3D hero and micro-interactions.

Everything visual lives here so ``app.py`` stays about behaviour.

* ``inject_css()``      – fonts, tokens, glass sidebar, cards, pills, buttons, tabs.
* ``inject_motion()``   – tiny script that adds 3D tilt + spotlight to cards.
* ``hero_html()``       – self-contained Three.js hero (3D cost skyline).
* ``style_figure()``    – one place to theme every Plotly chart.
* ``stepper_html()``    – live 4-agent pipeline stepper.
"""

from __future__ import annotations

import html
import json

import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# ── Design tokens (mirrored in the CSS below) ─────────────────────────────────
INK = "#14161F"
INK_2 = "#4A5062"
INK_3 = "#8089A0"
ACCENT = "#3B5BFF"
TEAL = "#12B5A5"
DANGER = "#E5484D"
WARN = "#F08A24"
OK = "#1FA971"

# Calm, distinguishable series colours (no pink / yellow).
SERIES = [
    "#3B5BFF", "#12B5A5", "#7A5AF8", "#2E90FA",
    "#16A34A", "#F08A24", "#64748B", "#0EA5A4",
]

_FONTS = (
    "https://fonts.googleapis.com/css2?"
    "family=Inter:wght@400;500;600;700&"
    "family=Plus+Jakarta+Sans:wght@600;700;800&"
    "family=JetBrains+Mono:wght@400;500&display=swap"
)

_CSS = """
@import url('__FONTS__');

:root {
  --bg: #F4F5F9;
  --surface: #FFFFFF;
  --surface-2: #F9FAFD;
  --ink: #14161F;
  --ink-2: #4A5062;
  --ink-3: #8089A0;
  --line: rgba(20, 22, 31, 0.08);
  --line-strong: rgba(20, 22, 31, 0.14);
  --accent: #3B5BFF;
  --accent-soft: rgba(59, 91, 255, 0.10);
  --teal: #12B5A5;
  --danger: #E5484D;
  --danger-soft: rgba(229, 72, 77, 0.10);
  --warn: #F08A24;
  --warn-soft: rgba(240, 138, 36, 0.12);
  --ok: #1FA971;
  --ok-soft: rgba(31, 169, 113, 0.12);
  --r-sm: 10px; --r-md: 16px; --r-lg: 22px; --r-xl: 28px;
  --sh-1: 0 1px 2px rgba(20,22,31,.04), 0 2px 8px rgba(20,22,31,.04);
  --sh-2: 0 2px 4px rgba(20,22,31,.04), 0 12px 32px rgba(20,22,31,.08);
  --sh-3: 0 4px 8px rgba(20,22,31,.05), 0 28px 64px rgba(40,60,160,.18);
  --ease: cubic-bezier(.2,.8,.2,1);
  --font: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  --display: 'Plus Jakarta Sans', 'Inter', system-ui, sans-serif;
  --mono: 'JetBrains Mono', 'SF Mono', Menlo, monospace;
  color-scheme: light;
}

/* ── Base ─────────────────────────────────────────────────────────────── */
html, body, [data-testid="stApp"], .stApp, button, input, textarea, select {
  font-family: var(--font) !important;
}
[data-testid="stApp"] {
  background:
    radial-gradient(1100px 560px at 92% -8%, rgba(59,91,255,.10), transparent 60%),
    radial-gradient(900px 520px at -6% 8%, rgba(18,181,165,.09), transparent 60%),
    var(--bg) !important;
  color: var(--ink);
}
[data-testid="stHeader"] { background: transparent !important; border: 0 !important; }
[data-testid="stDecoration"], footer, #MainMenu { display: none !important; }
[data-testid="stMainBlockContainer"], .main .block-container {
  max-width: 1240px; padding: 1.4rem 2rem 3.5rem !important;
}
h1, h2, h3, h4, [data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2, [data-testid="stMarkdownContainer"] h3 {
  font-family: var(--display) !important; letter-spacing: -0.022em; color: var(--ink);
  font-weight: 700 !important;
}
h1 { font-size: 2.1rem !important; }
p, li, label, span { color: inherit; }
code, pre, kbd { font-family: var(--mono) !important; }
code { background: var(--accent-soft) !important; color: #2A44D6 !important;
  border-radius: 6px; padding: .12em .42em !important; font-size: .86em !important; }
a { color: var(--accent) !important; text-decoration: none; }
hr { border-color: var(--line) !important; }
::selection { background: rgba(59,91,255,.22); }
* { scrollbar-width: thin; scrollbar-color: rgba(20,22,31,.18) transparent; }

/* Snappier reruns: keep stale elements readable instead of ghosting out. */
[data-stale="true"] { opacity: .88 !important; transition: opacity .12s linear !important; }

/* ── Entrance motion (only fires on newly inserted nodes) ─────────────── */
@keyframes rise { from { opacity: 0; transform: translateY(14px) scale(.985);} to { opacity: 1; transform: none; } }
@keyframes pulse-ring { 0% { box-shadow: 0 0 0 0 rgba(59,91,255,.45);} 100% { box-shadow: 0 0 0 12px rgba(59,91,255,0);} }
@keyframes shimmer { 0% { background-position: -400px 0;} 100% { background-position: 400px 0; } }
@keyframes spin { to { transform: rotate(360deg); } }
.cs-rise, [data-testid="stMetric"], .cs-card, .cs-anom-row { animation: rise .55s var(--ease) both; }
@media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }

/* ── Sidebar: frosted glass ───────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: rgba(255,255,255,.72) !important;
  backdrop-filter: saturate(180%) blur(22px); -webkit-backdrop-filter: saturate(180%) blur(22px);
  border-right: 1px solid var(--line) !important;
  box-shadow: 8px 0 40px rgba(20,22,31,.04);
}
[data-testid="stSidebar"] * { color: var(--ink-2); }
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: var(--ink) !important; }
.sb-brand {
  display: flex; gap: 12px; align-items: center; padding: 14px 14px; margin: 4px 0 14px;
  background: linear-gradient(135deg, #FFFFFF, #EEF2FF); border: 1px solid var(--line);
  border-radius: var(--r-md); box-shadow: var(--sh-1);
}
.sb-logo { width: 38px; height: 38px; border-radius: 12px; display: grid; place-items: center; font-size: 19px;
  background: linear-gradient(145deg, #5B7CFF, #3B5BFF 55%, #2A3FD0); color: #fff !important;
  box-shadow: 0 8px 18px rgba(59,91,255,.35), inset 0 1px 0 rgba(255,255,255,.4); }
.sb-brand-title { font-family: var(--display); font-weight: 800; font-size: 1.12rem; color: var(--ink) !important; letter-spacing: -.02em; }
.sb-brand-sub { font-size: .66rem; color: var(--ink-3) !important; letter-spacing: .09em; text-transform: uppercase; font-weight: 600; }
.sb-stat { display: flex; align-items: center; justify-content: space-between; background: var(--surface);
  border: 1px solid var(--line); border-radius: 12px; padding: 9px 12px; margin-bottom: 8px; box-shadow: var(--sh-1); }
.sb-stat-label { font-size: .74rem; color: var(--ink-3) !important; font-weight: 500; }
.sb-stat-value { font-size: .88rem; font-weight: 700; color: var(--ink) !important; font-variant-numeric: tabular-nums; }
.api-limit-ok, .api-limit-warn { border-radius: 12px; padding: 8px 12px; font-size: .76rem; font-weight: 600; margin-top: 4px; }
.api-limit-ok { background: var(--ok-soft); color: #137A52 !important; border: 1px solid rgba(31,169,113,.25); }
.api-limit-warn { background: var(--warn-soft); color: #B35D0B !important; border: 1px solid rgba(240,138,36,.3); }

/* ── Top navigation: segmented control with depth ─────────────────────── */
[data-testid="stRadioGroup"] {
  display: inline-flex !important; flex-direction: row !important; gap: 4px; padding: 5px;
  background: rgba(20,22,31,.05); border-radius: 16px; box-shadow: inset 0 1px 2px rgba(20,22,31,.08);
  flex-wrap: wrap; width: fit-content;
}
[data-testid="stRadioOption"] {
  margin: 0 !important; padding: 8px 18px !important; border-radius: 12px; cursor: pointer;
  transition: all .28s var(--ease); font-weight: 600; font-size: .9rem; color: var(--ink-2);
}
/* the visual radio circle wrapper (first div inside the label body) */
[data-testid="stRadioOption"] > div > div:first-child:not([data-testid]) { display: none !important; }
[data-testid="stRadioOption"]:hover { color: var(--ink); background: rgba(255,255,255,.55); }
[data-testid="stRadioOption"][data-selected="true"] {
  background: #fff; color: var(--ink); box-shadow: 0 1px 2px rgba(20,22,31,.08), 0 6px 16px rgba(20,22,31,.10);
  transform: translateY(-1px);
}
[data-testid="stRadioOption"] p { font-weight: 600; margin: 0; }
/* Radios inside forms (feedback) stay regular. */
[data-testid="stForm"] [data-testid="stRadioGroup"] { display: flex !important; background: transparent; box-shadow: none; padding: 0; width: auto; }
[data-testid="stForm"] [data-testid="stRadioOption"] { padding: 4px 0 !important; box-shadow: none !important; background: transparent !important; transform: none; }
[data-testid="stForm"] [data-testid="stRadioOption"] > div > div:first-child:not([data-testid]) { display: flex !important; }

/* ── Buttons ──────────────────────────────────────────────────────────── */
.stButton > button, [data-testid="stDownloadButton"] > button, [data-testid^="stBaseButton"] {
  border-radius: 12px !important; font-weight: 600 !important; letter-spacing: -.005em;
  transition: transform .22s var(--ease), box-shadow .22s var(--ease), background .22s var(--ease), border-color .22s !important;
}
.stButton > button[kind="secondary"], [data-testid="stBaseButton-secondary"], [data-testid="stDownloadButton"] > button {
  background: var(--surface) !important; border: 1px solid var(--line-strong) !important; color: var(--ink) !important;
  box-shadow: var(--sh-1);
}
.stButton > button[kind="secondary"]:hover, [data-testid="stBaseButton-secondary"]:hover, [data-testid="stDownloadButton"] > button:hover {
  transform: translateY(-2px); box-shadow: var(--sh-2); border-color: rgba(59,91,255,.45) !important; color: var(--accent) !important;
}
.stButton > button[kind="primary"], [data-testid="stBaseButton-primary"] {
  background: linear-gradient(180deg, #5876FF 0%, #3B5BFF 55%, #2F49E0 100%) !important; border: 0 !important; color: #fff !important;
  box-shadow: 0 1px 0 rgba(255,255,255,.35) inset, 0 8px 20px rgba(59,91,255,.36), 0 2px 4px rgba(20,22,31,.12);
}
.stButton > button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
  transform: translateY(-2px); box-shadow: 0 1px 0 rgba(255,255,255,.4) inset, 0 14px 30px rgba(59,91,255,.46), 0 2px 4px rgba(20,22,31,.12);
}
.stButton > button:active, [data-testid^="stBaseButton"]:active { transform: translateY(0) scale(.985) !important; }
.stButton > button:disabled { opacity: .5; box-shadow: none !important; transform: none !important; }
div.btn-investigated button { background: var(--ok-soft) !important; border: 1px solid rgba(31,169,113,.35) !important; color: #137A52 !important; }

/* ── Metric cards ─────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
  position: relative; background: var(--surface) !important; border: 1px solid var(--line); border-radius: var(--r-lg);
  padding: 18px 20px !important; box-shadow: var(--sh-1); overflow: hidden;
  transition: box-shadow .35s var(--ease), transform .35s var(--ease);
  transform-style: preserve-3d; will-change: transform;
}
[data-testid="stMetric"]::before { content: ""; position: absolute; inset: 0 0 auto 0; height: 3px;
  background: linear-gradient(90deg, var(--accent), var(--teal)); opacity: .9; }
[data-testid="stMetric"]:hover { box-shadow: var(--sh-3); }
[data-testid="stMetricLabel"] p { color: var(--ink-3) !important; font-weight: 600 !important; font-size: .76rem !important;
  text-transform: uppercase; letter-spacing: .07em; }
[data-testid="stMetricValue"], [data-testid="stMetricValue"] * { font-family: var(--display) !important; font-weight: 800 !important;
  letter-spacing: -.03em; color: var(--ink) !important; font-variant-numeric: tabular-nums; }

/* ── Cards, callouts, banners ─────────────────────────────────────────── */
.cs-card, .info-card {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg); padding: 18px 22px; margin-bottom: 14px;
  box-shadow: var(--sh-1); transition: box-shadow .35s var(--ease), transform .35s var(--ease);
  transform-style: preserve-3d; will-change: transform;
}
.cs-card:hover, .info-card:hover { box-shadow: var(--sh-2); }
.anomaly-callout {
  position: relative; background: linear-gradient(135deg, #FFFFFF 0%, #FFF5F5 100%); border: 1px solid rgba(229,72,77,.22);
  border-radius: var(--r-lg); padding: 20px 26px; margin-bottom: 18px; color: var(--ink);
  box-shadow: 0 1px 2px rgba(20,22,31,.04), 0 14px 36px rgba(229,72,77,.12); animation: rise .55s var(--ease) both;
}
.anomaly-callout::before { content: ""; position: absolute; left: 0; top: 18px; bottom: 18px; width: 4px; border-radius: 4px; background: var(--danger); }
.status-banner { border-radius: 14px; padding: 11px 18px; margin-bottom: 16px; font-weight: 700; font-size: .88rem; letter-spacing: .02em; }
.status-high { background: var(--ok-soft); border: 1px solid rgba(31,169,113,.3); color: #137A52; }
.status-medium { background: var(--warn-soft); border: 1px solid rgba(240,138,36,.35); color: #A9570A; }
.status-low { background: var(--danger-soft); border: 1px solid rgba(229,72,77,.32); color: #B42318; }
.sev-badge, .cat-badge { display: inline-block; padding: 3px 11px; border-radius: 999px; font-size: .68rem; font-weight: 800;
  letter-spacing: .07em; text-transform: uppercase; color: #fff; }
.sev-critical { background: var(--danger); } .sev-warning { background: var(--warn); } .sev-info { background: var(--accent); }
.cost-box { background: #0F172A; color: #D6E4FF; border-radius: 14px; padding: 14px 18px; font-family: var(--mono);
  font-size: .84rem; white-space: pre-wrap; margin: 8px 0 12px; box-shadow: inset 0 1px 0 rgba(255,255,255,.06), var(--sh-1); }

/* ── Anomaly rows (Streamlit columns turned into floating cards) ──────── */
[data-testid="stHorizontalBlock"]:has(.row-marker) {
  background: var(--surface); border: 1px solid var(--line); border-radius: 18px; padding: 10px 16px; margin: 0 0 10px;
  align-items: center; box-shadow: var(--sh-1); position: relative;
  transition: transform .3s var(--ease), box-shadow .3s var(--ease), border-color .3s;
}
[data-testid="stHorizontalBlock"]:has(.row-marker):hover { transform: translateY(-3px) scale(1.003); box-shadow: var(--sh-2); border-color: rgba(59,91,255,.28); }
[data-testid="stHorizontalBlock"]:has(.row-marker.hi)::before { content: ""; position: absolute; left: 0; top: 14px; bottom: 14px; width: 4px; border-radius: 0 4px 4px 0; background: var(--danger); }
[data-testid="stHorizontalBlock"]:has(.row-marker.hdr) { background: transparent; border: 0; box-shadow: none; padding: 0 16px; margin-bottom: 4px; }
[data-testid="stHorizontalBlock"]:has(.row-marker.hdr):hover { transform: none; box-shadow: none; }
.col-h { font-size: .68rem; font-weight: 700; color: var(--ink-3); text-transform: uppercase; letter-spacing: .09em; }
.cell-svc { font-weight: 650; color: var(--ink); } .cell-num { font-variant-numeric: tabular-nums; color: var(--ink-2); }
.z-hot { color: var(--danger); font-weight: 800; font-variant-numeric: tabular-nums; }
.pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 11px; border-radius: 999px; font-size: .74rem; font-weight: 700; }
.pill-pending { background: rgba(20,22,31,.06); color: var(--ink-2); }
.pill-done { background: var(--ok-soft); color: #137A52; }
.pill-run { background: var(--accent-soft); color: #2A44D6; }
.pill-fail { background: var(--danger-soft); color: #B42318; }
.pill-queued { background: rgba(122,90,248,.12); color: #5B3FD6; }
.dot { width: 8px; height: 8px; border-radius: 50%; background: currentColor; }
.pill-run .dot { animation: pulse-ring 1.3s infinite; background: var(--accent); }

/* ── Tabs, expanders, inputs ──────────────────────────────────────────── */
[data-baseweb="tab-list"] { gap: 6px; border-bottom: 1px solid var(--line) !important; }
[data-baseweb="tab"] { border-radius: 12px 12px 0 0; font-weight: 600 !important; color: var(--ink-3) !important; padding: 10px 16px !important; transition: color .2s, background .2s; }
[data-baseweb="tab"]:hover { color: var(--ink) !important; background: rgba(20,22,31,.04); }
[data-baseweb="tab"][aria-selected="true"] { color: var(--accent) !important; }
[data-baseweb="tab-highlight"] { background: linear-gradient(90deg, var(--accent), var(--teal)) !important; height: 3px !important; border-radius: 3px; }
[data-testid="stExpander"] { border: 1px solid var(--line) !important; border-radius: var(--r-md) !important; background: var(--surface);
  box-shadow: var(--sh-1); overflow: hidden; transition: box-shadow .3s var(--ease); }
[data-testid="stExpander"]:hover { box-shadow: var(--sh-2); }
[data-testid="stExpander"] summary { font-weight: 600; }
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] { border-radius: 12px !important; }
[data-testid="stFileUploaderDropzone"] { background: var(--surface-2) !important; border: 1.5px dashed var(--line-strong) !important; border-radius: var(--r-md) !important; transition: all .25s var(--ease); }
[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--accent) !important; background: var(--accent-soft) !important; }
[data-testid="stAlert"] [data-testid="stAlertContainer"] { background: rgba(255,255,255,.85) !important; color: var(--ink) !important; border-left: 3px solid var(--accent); }
[data-testid="stAlert"] [data-testid="stAlertContainer"] * { color: var(--ink) !important; }
[data-testid="stAlert"], [data-testid="stAlert"] > div { background: rgba(255,255,255,.9) !important; }
[data-testid="stAlert"] { border-radius: var(--r-md) !important; border: 1px solid var(--line) !important; box-shadow: var(--sh-1); }
[data-testid="stProgress"] > div > div { background: rgba(20,22,31,.07) !important; border-radius: 999px; height: 8px; }
[data-testid="stProgress"] > div > div > div { background: linear-gradient(90deg, var(--accent), var(--teal)) !important; border-radius: 999px; }
[data-testid="stDataFrame"] { border-radius: var(--r-md); overflow: hidden; box-shadow: var(--sh-1); border: 1px solid var(--line); }
[data-testid="stPlotlyChart"] { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg); padding: 10px 8px 2px;
  box-shadow: var(--sh-1); transition: box-shadow .35s var(--ease); }
[data-testid="stPlotlyChart"]:hover { box-shadow: var(--sh-2); }
[data-testid="stToast"] { border-radius: 14px !important; box-shadow: var(--sh-3) !important; }

/* ── Hero + live pipeline ─────────────────────────────────────────────── */
iframe[title="streamlit_component"], iframe[title="st.iframe"], [data-testid="stIFrame"] iframe, [data-testid="stCustomComponentV1"] iframe {
  border: 0 !important; border-radius: var(--r-xl); }
.cs-pipeline { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-xl); padding: 22px 26px; box-shadow: var(--sh-2); animation: rise .5s var(--ease) both; }
.cs-steps { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 6px 0 16px; position: relative; }
.cs-step { position: relative; border: 1px solid var(--line); border-radius: 16px; padding: 14px 14px 12px; background: var(--surface-2); transition: all .35s var(--ease); }
.cs-step .ico { width: 34px; height: 34px; border-radius: 11px; display: grid; place-items: center; font-size: 17px; background: rgba(20,22,31,.06); margin-bottom: 8px; }
.cs-step .nm { font-weight: 700; font-size: .92rem; color: var(--ink); }
.cs-step .ds { font-size: .76rem; color: var(--ink-3); margin-top: 2px; }
.cs-step.done { background: linear-gradient(180deg,#FFFFFF,#F1FBF6); border-color: rgba(31,169,113,.35); }
.cs-step.done .ico { background: var(--ok-soft); }
.cs-step.active { background: linear-gradient(180deg,#FFFFFF,#F1F4FF); border-color: rgba(59,91,255,.5); box-shadow: 0 10px 30px rgba(59,91,255,.20); transform: translateY(-3px); }
.cs-step.active .ico { background: var(--accent); color: #fff; animation: pulse-ring 1.4s infinite; }
.cs-step.skipped { opacity: .55; }
.cs-log { font-family: var(--mono); font-size: .78rem; color: var(--ink-2); background: var(--surface-2); border: 1px solid var(--line); border-radius: 14px; padding: 12px 14px; line-height: 1.7; max-height: 190px; overflow: auto; }
.cs-log .t { color: var(--ink-3); margin-right: 8px; }
.cs-bar { height: 8px; border-radius: 999px; background: rgba(20,22,31,.07); overflow: hidden; margin: 6px 0 4px; }
.cs-bar > span { display: block; height: 100%; border-radius: 999px; background: linear-gradient(90deg, var(--accent), var(--teal)); transition: width .6s var(--ease); }
.cs-activity { display: flex; align-items: center; gap: 14px; background: var(--surface); border: 1px solid rgba(59,91,255,.25);
  border-radius: 18px; padding: 12px 18px; margin: 12px 0 16px; box-shadow: 0 10px 30px rgba(59,91,255,.14); animation: rise .45s var(--ease) both; }
.cs-spin { width: 18px; height: 18px; border-radius: 50%; border: 2.5px solid rgba(59,91,255,.25); border-top-color: var(--accent); animation: spin .8s linear infinite; }

.cs-footer { text-align: center; color: var(--ink-3); font-size: .78rem; padding: 26px 0 6px; margin-top: 46px; border-top: 1px solid var(--line); }
.cs-footer code { background: rgba(20,22,31,.05) !important; color: var(--ink-2) !important; }
.cs-empty { text-align: center; padding: 54px 24px; background: var(--surface); border: 1px dashed var(--line-strong); border-radius: var(--r-xl); color: var(--ink-2); }
.cs-empty .big { font-size: 2.6rem; margin-bottom: 6px; }

@media (max-width: 760px) {
  [data-testid="stMainBlockContainer"], .main .block-container { padding: 1rem 1rem 3rem !important; }
  .cs-steps { grid-template-columns: repeat(2, 1fr); }
  [data-testid="stRadioOption"] { padding: 7px 12px !important; font-size: .82rem; }
}
"""


def inject_css() -> None:
    """Inject fonts, design tokens and component styles (call once per run)."""
    st.markdown(f"<style>{_CSS.replace('__FONTS__', _FONTS)}</style>", unsafe_allow_html=True)


# ── Motion: 3D tilt + spotlight on cards ──────────────────────────────────────
_MOTION_JS = """
<script>
(function () {
  try {
    const doc = window.parent.document;
    if (window.parent.__csMotion) return;
    window.parent.__csMotion = true;
    if (window.parent.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const SEL = '[data-testid="stMetric"], .cs-card, .info-card, .cs-step.active, .anomaly-callout';
    let raf = null, last = null;
    function apply(el, e) {
      const r = el.getBoundingClientRect();
      const px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height;
      const rx = (0.5 - py) * 9, ry = (px - 0.5) * 11;
      el.style.transform = 'perspective(900px) rotateX(' + rx.toFixed(2) + 'deg) rotateY(' + ry.toFixed(2) + 'deg) translateZ(6px)';
      el.style.setProperty('--mx', (px * 100).toFixed(1) + '%');
      el.style.setProperty('--my', (py * 100).toFixed(1) + '%');
    }
    doc.addEventListener('pointermove', function (e) {
      const el = e.target.closest ? e.target.closest(SEL) : null;
      if (last && last !== el) { last.style.transform = ''; }
      last = el;
      if (!el) return;
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(function () { apply(el, e); });
    }, { passive: true });
    doc.addEventListener('pointerleave', function () { if (last) { last.style.transform = ''; last = null; } }, true);
  } catch (err) { /* parent not reachable: skip silently */ }
})();
</script>
"""


def inject_motion() -> None:
    """Add the 3D tilt behaviour (zero-height component, idempotent)."""
    components.html(_MOTION_JS, height=0)


# ── Hero (Three.js) ───────────────────────────────────────────────────────────
_DEFAULT_BARS = [0.35, 0.55, 0.42, 1.0, 0.5, 0.68, 0.38, 0.6, 0.3]

_HERO = """
<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="__FONTS__" rel="stylesheet">
<style>
  :root { color-scheme: light; }
  html, body { margin: 0; height: 100%; background: transparent; font-family: 'Inter', system-ui, sans-serif; color: #14161F; overflow: hidden; }
  .wrap { position: relative; height: 100%; border-radius: 28px; overflow: hidden;
    background: radial-gradient(900px 420px at 88% -12%, #DCE5FF 0%, rgba(220,229,255,0) 62%),
                radial-gradient(700px 380px at -4% 112%, #D5F3EC 0%, rgba(213,243,236,0) 60%),
                linear-gradient(180deg, #FFFFFF 0%, #F1F4FC 100%);
    box-shadow: inset 0 0 0 1px rgba(20,22,31,.07), 0 24px 60px rgba(40,60,160,.14); }
  canvas { position: absolute; inset: 0; width: 100%; height: 100%; display: block; touch-action: pan-y; }
  .copy { position: absolute; left: 44px; top: 50%; transform: translateY(-50%); max-width: 44%; z-index: 2; pointer-events: none; }
  .eyebrow { display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 999px; font-size: 11.5px; font-weight: 700;
    letter-spacing: .09em; text-transform: uppercase; color: #2A44D6; background: rgba(59,91,255,.10); border: 1px solid rgba(59,91,255,.18); }
  .eyebrow i { width: 7px; height: 7px; border-radius: 50%; background: #3B5BFF; box-shadow: 0 0 0 0 rgba(59,91,255,.5); animation: ping 1.8s infinite; }
  @keyframes ping { to { box-shadow: 0 0 0 10px rgba(59,91,255,0); } }
  h1 { font-family: 'Plus Jakarta Sans', 'Inter', sans-serif; font-weight: 800; font-size: clamp(34px, 5.2vw, 58px); letter-spacing: -.035em;
    line-height: 1.02; margin: 16px 0 14px; background: linear-gradient(120deg, #14161F 18%, #3B5BFF 78%); -webkit-background-clip: text; background-clip: text; color: transparent; }
  p { font-size: 16.5px; line-height: 1.55; color: #4A5062; margin: 0 0 20px; max-width: 460px; }
  .chips { display: flex; gap: 8px; flex-wrap: wrap; }
  .chip { padding: 7px 13px; border-radius: 12px; font-size: 12.5px; font-weight: 600; color: #14161F; background: rgba(255,255,255,.78);
    border: 1px solid rgba(20,22,31,.08); box-shadow: 0 1px 2px rgba(20,22,31,.05), 0 8px 18px rgba(20,22,31,.06); backdrop-filter: blur(8px); }
  .chip b { color: #3B5BFF; }
  .hint { position: absolute; right: 22px; bottom: 14px; font-size: 11.5px; color: #8089A0; z-index: 2; letter-spacing: .02em; }
  @media (max-width: 760px) {
    .copy { left: 22px; right: 22px; top: 22px; transform: none; max-width: none; }
    p { font-size: 14.5px; } canvas { opacity: .55; } .hint { display: none; }
  }
</style></head>
<body><div class="wrap" id="wrap">
  <canvas id="c"></canvas>
  <div class="copy">
    <span class="eyebrow"><i></i>__EYEBROW__</span>
    <h1>CostSherlock</h1>
    <p>__TAGLINE__</p>
    <div class="chips">__CHIPS__</div>
  </div>
  <div class="hint">move your cursor to explore</div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
(function () {
  var BARS = __BARS__;
  var wrap = document.getElementById('wrap'), canvas = document.getElementById('c');
  if (!window.THREE) { return; }
  var renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true, powerPreference: 'high-performance' }); }
  catch (e) { return; }
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputEncoding = THREE.sRGBEncoding;
  var scene = new THREE.Scene();
  var camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
  camera.position.set(8.6, 6.4, 10.4); camera.lookAt(0, 1.3, 0);

  scene.add(new THREE.HemisphereLight(0xffffff, 0xd9e2ff, 0.95));
  var sun = new THREE.DirectionalLight(0xffffff, 1.15); sun.position.set(5, 11, 6); sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048); sun.shadow.radius = 7; sun.shadow.bias = -0.0004;
  var sc = sun.shadow.camera; sc.left = -9; sc.right = 9; sc.top = 9; sc.bottom = -9; sc.near = 1; sc.far = 30;
  scene.add(sun);
  var rim = new THREE.PointLight(0x7a8cff, 0.8, 30); rim.position.set(-7, 4, -5); scene.add(rim);

  var stage = new THREE.Group(); scene.add(stage);
  var plat = new THREE.Mesh(new THREE.CylinderGeometry(7.1, 7.3, 0.34, 120),
    new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.92, metalness: 0.0 }));
  plat.position.y = -0.17; plat.receiveShadow = true; stage.add(plat);
  var ring = new THREE.Mesh(new THREE.RingGeometry(6.2, 6.28, 160), new THREE.MeshBasicMaterial({ color: 0x3B5BFF, transparent: true, opacity: 0.18, side: THREE.DoubleSide }));
  ring.rotation.x = -Math.PI / 2; ring.position.y = 0.006; stage.add(ring);

  function roundedBar(w, d, h, r) {
    var s = new THREE.Shape(), x = -w / 2, y = -d / 2;
    s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
    s.lineTo(x + w, y + d - r); s.quadraticCurveTo(x + w, y + d, x + w - r, y + d);
    s.lineTo(x + r, y + d); s.quadraticCurveTo(x, y + d, x, y + d - r);
    s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
    var g = new THREE.ExtrudeGeometry(s, { depth: h, bevelEnabled: true, bevelThickness: 0.05, bevelSize: 0.05, bevelSegments: 4, curveSegments: 10 });
    g.rotateX(-Math.PI / 2); return g;
  }

  var palette = [0x7C93FF, 0x5ECDC0, 0xA7B6FF, 0x6FA8FF, 0x8FD9CF, 0x9B8CFF];
  var n = Math.min(BARS.length, 10), maxV = Math.max.apply(null, BARS) || 1, bars = [];
  var hotIdx = BARS.indexOf(maxV);
  for (var i = 0; i < n; i++) {
    var v = BARS[i] / maxV, h = 0.7 + 3.7 * v, isHot = i === hotIdx;
    var col = isHot ? 0xFF4D52 : palette[i % palette.length];
    var mat = new THREE.MeshStandardMaterial({ color: col, roughness: 0.38, metalness: 0.08,
      emissive: isHot ? 0xFF2A30 : 0x000000, emissiveIntensity: isHot ? 0.22 : 0 });
    var m = new THREE.Mesh(roundedBar(0.78, 0.78, h, 0.2), mat); m.castShadow = true; m.receiveShadow = true;
    var ang = (i / n) * Math.PI * 2 + 0.4, rad = n > 1 ? 3.7 : 0;
    m.position.set(Math.cos(ang) * rad * 0.95, 0, Math.sin(ang) * rad * 0.62);
    m.scale.y = 0.001; m.userData = { h: h, delay: 0.1 + i * 0.09, hot: isHot };
    stage.add(m); bars.push(m);
  }
  var halo = null;
  if (bars[hotIdx]) {
    halo = new THREE.Mesh(new THREE.RingGeometry(0.62, 0.7, 64), new THREE.MeshBasicMaterial({ color: 0xFF4D52, transparent: true, opacity: 0.5, side: THREE.DoubleSide }));
    halo.rotation.x = -Math.PI / 2; halo.position.copy(bars[hotIdx].position); halo.position.y = 0.02; stage.add(halo);
  }
  var orbs = [];
  for (var k = 0; k < 7; k++) {
    var o = new THREE.Mesh(new THREE.SphereGeometry(0.1 + Math.random() * 0.12, 24, 24),
      new THREE.MeshStandardMaterial({ color: k % 2 ? 0x3B5BFF : 0x12B5A5, roughness: 0.2, metalness: 0.2, transparent: true, opacity: 0.8 }));
    o.userData = { a: Math.random() * 6.28, r: 4.2 + Math.random() * 1.6, y: 1.2 + Math.random() * 3.2, s: 0.18 + Math.random() * 0.25 };
    o.castShadow = true; stage.add(o); orbs.push(o);
  }

  var tx = 0, ty = 0, cx = 0, cy = 0, W = 1, H = 1, visible = true;
  window.addEventListener('pointermove', function (e) {
    var r = wrap.getBoundingClientRect();
    tx = ((e.clientX - r.left) / r.width - 0.5) * 2; ty = ((e.clientY - r.top) / r.height - 0.5) * 2;
  }, { passive: true });
  function resize() {
    W = wrap.clientWidth; H = wrap.clientHeight; renderer.setSize(W, H, false);
    camera.aspect = W / H;
    var narrow = W < 760; camera.fov = narrow ? 38 : 32;
    camera.setViewOffset(W, H, narrow ? 0 : -W * 0.2, narrow ? -H * 0.16 : 0, W, H);
    camera.updateProjectionMatrix();
  }
  window.addEventListener('resize', resize); resize();
  document.addEventListener('visibilitychange', function () { visible = !document.hidden; });
  if ('IntersectionObserver' in window) new IntersectionObserver(function (en) { visible = en[0].isIntersecting && !document.hidden; }).observe(wrap);

  function ease(t) { var c = 1.70158, c3 = c + 1; return 1 + c3 * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2); }
  var clock = new THREE.Clock();
  function tick() {
    requestAnimationFrame(tick);
    if (!visible) return;
    var t = clock.getElapsedTime();
    cx += (tx - cx) * 0.05; cy += (ty - cy) * 0.05;
    stage.rotation.y = -0.5 + Math.sin(t * 0.18) * 0.22 + cx * 0.42;
    stage.rotation.x = cy * 0.05;
    for (var i = 0; i < bars.length; i++) {
      var b = bars[i], p = Math.min(Math.max((t - b.userData.delay) / 1.1, 0), 1);
      b.scale.y = Math.max(ease(p), 0.001);
      if (b.userData.hot && p >= 1) b.material.emissiveIntensity = 0.2 + Math.sin(t * 2.6) * 0.12;
    }
    if (halo) { var s = 1 + ((t * 0.7) % 1) * 1.6; halo.scale.set(s, s, s); halo.material.opacity = 0.5 * (1 - ((t * 0.7) % 1)); }
    for (var j = 0; j < orbs.length; j++) {
      var d = orbs[j].userData, a = d.a + t * d.s * 0.4;
      orbs[j].position.set(Math.cos(a) * d.r, d.y + Math.sin(t * d.s * 2 + j) * 0.25, Math.sin(a) * d.r * 0.7);
    }
    renderer.render(scene, camera);
  }
  tick();
})();
</script></body></html>
"""


def _fmt_money(v: float) -> str:
    return f"${v:,.0f}"


def hero_html(
    bar_values: list[float] | None = None,
    eyebrow: str = "Agentic FinOps",
    tagline: str = "Four AI agents investigate AWS cost spikes and explain the root cause with cited evidence.",
    chips: list[tuple[str, str]] | None = None,
) -> str:
    """Return the self-contained hero HTML (Three.js scene + copy)."""
    bars = [float(v) for v in (bar_values or _DEFAULT_BARS) if v and v > 0][:10] or _DEFAULT_BARS
    chip_html = "".join(
        f'<span class="chip"><b>{html.escape(a)}</b> {html.escape(b)}</span>' for a, b in (chips or [])
    )
    return (
        _HERO.replace("__FONTS__", _FONTS)
        .replace("__BARS__", json.dumps(bars))
        .replace("__EYEBROW__", html.escape(eyebrow))
        .replace("__TAGLINE__", html.escape(tagline))
        .replace("__CHIPS__", chip_html)
    )


def render_hero(bar_values: list[float] | None, chips: list[tuple[str, str]] | None, height: int = 380) -> None:
    components.html(hero_html(bar_values, chips=chips), height=height)


# ── Plotly styling ────────────────────────────────────────────────────────────
def style_figure(fig: go.Figure, height: int = 420, legend: bool = True) -> go.Figure:
    """Apply the light 'Apple-ish' theme to any Plotly figure."""
    fig.update_layout(
        template="plotly_white",
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, system-ui, sans-serif", color=INK_2, size=12),
        margin=dict(l=48, r=24, t=18, b=44),
        showlegend=legend,
        legend=dict(orientation="h", y=-0.18, x=0, bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor="rgba(20,22,31,.12)", font=dict(family="Inter", size=12, color=INK)),
        transition=dict(duration=350, easing="cubic-in-out"),
    )
    fig.update_xaxes(showgrid=False, linecolor="rgba(20,22,31,.10)", tickfont=dict(color=INK_3), zeroline=False)
    fig.update_yaxes(gridcolor="rgba(20,22,31,.06)", zeroline=False, tickfont=dict(color=INK_3))
    return fig


# ── Live pipeline stepper ─────────────────────────────────────────────────────
_AGENTS = [
    ("sentinel", "🔍", "Sentinel", "Confirms the anomaly"),
    ("detective", "🕵️", "Detective", "Correlates CloudTrail"),
    ("analyst", "🧠", "Analyst", "RAG causal reasoning"),
    ("narrator", "📝", "Narrator", "Writes the cited report"),
]


def stepper_html(step: str, state: str, skipped: set[str] | None = None, log: list[str] | None = None, progress: float | None = None) -> str:
    """Render the 4-agent stepper. ``step`` is the active agent key; ``state`` queued|running|done|failed."""
    skipped = skipped or set()
    order = [a[0] for a in _AGENTS]
    cur = order.index(step) if step in order else (len(order) if state == "done" else -1)
    cells = []
    for i, (key, ico, name, desc) in enumerate(_AGENTS):
        if key in skipped:
            cls, desc2 = "skipped", "Skipped (no CloudTrail logs)"
        elif state == "done" or i < cur:
            cls, desc2 = "done", "Done"
        elif i == cur and state == "running":
            cls, desc2 = "active", "Working…"
        else:
            cls, desc2 = "", desc
        mark = "✓" if cls == "done" else ico
        cells.append(f'<div class="cs-step {cls}"><div class="ico">{mark}</div><div class="nm">{name}</div><div class="ds">{html.escape(desc2)}</div></div>')
    pct = progress if progress is not None else (1.0 if state == "done" else max(cur, 0) / len(order))
    lines = "".join(f'<div>{html.escape(line)}</div>' for line in (log or [])[-8:])
    log_html = f'<div class="cs-log">{lines}</div>' if lines else ""
    return (
        f'<div class="cs-pipeline"><div class="cs-steps">{"".join(cells)}</div>'
        f'<div class="cs-bar"><span style="width:{pct * 100:.0f}%"></span></div>{log_html}</div>'
    )


def pill(kind: str, label: str) -> str:
    """Small status pill HTML. kind: pending|done|run|fail|queued."""
    dot = '<span class="dot"></span>' if kind in ("run", "queued") else ""
    return f'<span class="pill pill-{kind}">{dot}{html.escape(label)}</span>'
