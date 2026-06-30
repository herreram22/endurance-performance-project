from pathlib import Path
import sys

import streamlit as st


def find_project_root(start_path):
    for path in [start_path, *start_path.parents]:
        if (path / "src").exists() and (path / "data_processed").exists():
            return path
    return start_path


PROJECT_ROOT = find_project_root(Path(__file__).resolve().parent)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.load_data import load_all_data
from src.pages import (
    render_key_findings,
    render_block_explorer,
    render_how_garmin_works,
    render_landing_page,
    render_overview,
    render_personal_best_tracker,
    render_prediction_dynamics,
    render_running_atlas,
    render_timeline_view,
)


st.set_page_config(
    page_title="Endurance Performance Dashboard",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    :root {
        --hp-ink: #0f172a;
        --hp-soft-ink: #334155;
        --hp-muted: #64748b;
        --hp-border: #e2e8f0;
        --hp-panel: rgba(255, 255, 255, 0.92);
        --hp-accent: #2563eb;
        --hp-accent-soft: #eff6ff;
        --hp-green: #16a34a;
    }

    .stApp {
        background:
            radial-gradient(circle at 10% 0%, rgba(37, 99, 235, 0.07), transparent 28rem),
            radial-gradient(circle at 88% 4%, rgba(22, 163, 74, 0.06), transparent 24rem),
            linear-gradient(180deg, #ffffff 0%, #f8fafc 48%, #ffffff 100%);
    }

    .block-container {
        padding-top: 2.25rem;
        padding-bottom: 3.5rem;
        max-width: 1440px;
    }

    h1, h2, h3 {
        letter-spacing: 0;
        color: var(--hp-ink);
    }

    h1 {
        font-weight: 800;
        line-height: 1.05;
    }

    h2 {
        font-weight: 750;
        margin-top: 1.7rem;
        margin-bottom: 0.55rem;
    }

    .page-intro {
        margin-bottom: 1.1rem;
        padding: 1.05rem 1.15rem;
        border: 1px solid rgba(229, 231, 235, 0.9);
        border-radius: 14px;
        background: linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(248,250,252,0.96) 100%);
        box-shadow: 0 16px 40px rgba(15, 23, 42, 0.045);
    }

    .page-intro--compact {
        padding: 0.9rem 1rem;
        margin-bottom: 0.85rem;
    }

    .page-intro__eyebrow {
        color: var(--hp-accent);
        font-size: 0.74rem;
        font-weight: 800;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }

    .page-intro__title {
        color: var(--hp-ink);
        font-size: clamp(1.55rem, 2.5vw, 2.15rem);
        font-weight: 800;
        line-height: 1.12;
        margin: 0;
    }

    .page-intro__description {
        color: var(--hp-soft-ink);
        font-size: 0.98rem;
        line-height: 1.65;
        margin-top: 0.45rem;
        max-width: 960px;
    }

    p, li, label, .stMarkdown {
        color: var(--hp-soft-ink);
    }

    .story-note {
        margin: 0.9rem 0 1.15rem;
        padding: 0.95rem 1rem;
        border: 1px solid rgba(37, 99, 235, 0.15);
        border-left: 4px solid var(--hp-accent);
        border-radius: 12px;
        background: linear-gradient(135deg, rgba(239, 246, 255, 0.92) 0%, rgba(255, 255, 255, 0.97) 100%);
        box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04);
        color: var(--hp-ink);
        font-size: 0.96rem;
        line-height: 1.65;
    }

    div[data-testid="stMarkdownContainer"],
    div[data-testid="stMarkdownContainer"] p,
    div[data-testid="stMarkdownContainer"] li,
    div[data-testid="stMarkdownContainer"] span {
        color: var(--hp-soft-ink);
    }

    div[data-testid="stButton"] button,
    div[data-testid="stBaseButton-secondary"],
    div[data-testid="stBaseButton-secondary"] *,
    div[data-testid="stSegmentedControl"] button,
    div[data-testid="stSegmentedControl"] button *,
    div[data-testid="stPills"] button,
    div[data-testid="stPills"] button * {
        color: var(--hp-soft-ink) !important;
    }

    div[data-testid="stButton"] button {
        background: #ffffff;
        border: 1px solid var(--hp-border);
        color: var(--hp-soft-ink) !important;
    }

    div[data-testid="stButton"] button[kind="primary"],
    div[data-testid="stBaseButton-primary"],
    div[data-testid="stBaseButton-primary"] * {
        background: var(--hp-accent) !important;
        border-color: var(--hp-accent) !important;
        color: #ffffff !important;
    }

    div[data-testid="stSegmentedControl"] button[aria-checked="true"],
    div[data-testid="stSegmentedControl"] button[aria-selected="true"] {
        background: var(--hp-accent-soft) !important;
        border-color: #bfdbfe !important;
        color: var(--hp-accent) !important;
    }

    div[data-testid="stMetric"] {
        background: var(--hp-panel);
        border: 1px solid var(--hp-border);
        border-radius: 10px;
        padding: 1rem 1rem 0.9rem;
        box-shadow: 0 18px 45px rgba(15, 23, 42, 0.06);
        backdrop-filter: blur(12px);
        min-height: 7rem;
        display: flex;
        flex-direction: column;
        justify-content: flex-start;
        gap: 0.25rem;
        overflow-wrap: anywhere;
        word-break: break-word;
    }

    div[data-testid="stMetricLabel"] {
        color: var(--hp-muted);
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        line-height: 1.35;
    }

    div[data-testid="stMetricValue"] {
        color: var(--hp-ink);
        font-weight: 800;
        font-size: clamp(1.05rem, 2.3vw, 1.35rem);
        line-height: 1.2;
    }

    div[data-testid="stMetricDelta"] {
        color: var(--hp-accent);
        font-size: 0.92rem;
        font-weight: 650;
    }

    div[data-testid="stCaptionContainer"] {
        color: var(--hp-muted);
    }

    div[data-testid="stCaptionContainer"] p {
        color: var(--hp-muted);
    }

    div[data-testid="stTabs"] button {
        border-radius: 999px;
        padding: 0.35rem 0.8rem;
        color: var(--hp-soft-ink) !important;
    }

    div[data-testid="stTabs"] button[aria-selected="true"] {
        color: var(--hp-accent) !important;
    }

    section[data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.94);
        border-right: 1px solid var(--hp-border);
        box-shadow: 18px 0 45px rgba(15, 23, 42, 0.04);
    }

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        color: var(--hp-ink);
    }

    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
        color: var(--hp-muted);
    }

    section[data-testid="stSidebar"] button,
    section[data-testid="stSidebar"] div[data-testid="stButton"] button,
    section[data-testid="stSidebar"] div[data-testid="stSegmentedControl"] button,
    section[data-testid="stSidebar"] div[data-testid="stPills"] button {
        background: #ffffff !important;
        border-color: var(--hp-border) !important;
        color: var(--hp-soft-ink) !important;
        box-shadow: none !important;
    }

    section[data-testid="stSidebar"] button *,
    section[data-testid="stSidebar"] div[data-testid="stButton"] button *,
    section[data-testid="stSidebar"] div[data-testid="stSegmentedControl"] button *,
    section[data-testid="stSidebar"] div[data-testid="stPills"] button * {
        color: inherit !important;
    }

    section[data-testid="stSidebar"] button:hover,
    section[data-testid="stSidebar"] div[data-testid="stButton"] button:hover,
    section[data-testid="stSidebar"] div[data-testid="stSegmentedControl"] button:hover,
    section[data-testid="stSidebar"] div[data-testid="stPills"] button:hover {
        background: #f8fafc !important;
        border-color: #cbd5e1 !important;
        color: var(--hp-ink) !important;
    }

    section[data-testid="stSidebar"] button:focus,
    section[data-testid="stSidebar"] button:active,
    section[data-testid="stSidebar"] button:focus-visible {
        outline: 2px solid rgba(37, 99, 235, 0.22) !important;
        outline-offset: 2px !important;
        background: #ffffff !important;
        color: var(--hp-soft-ink) !important;
    }

    section[data-testid="stSidebar"] div[data-testid="stSegmentedControl"] button[aria-checked="true"],
    section[data-testid="stSidebar"] div[data-testid="stSegmentedControl"] button[aria-selected="true"],
    section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-selected="true"] {
        background: var(--hp-accent-soft) !important;
        border-color: #bfdbfe !important;
        color: var(--hp-accent) !important;
        font-weight: 650;
    }

    section[data-testid="stSidebar"] div[data-testid="stPills"] {
        gap: 0.35rem;
    }

    section[data-testid="stSidebar"] div[data-testid="stPills"] button {
        width: 100%;
        justify-content: flex-start;
        border-radius: 10px;
        border: 1px solid rgba(229, 231, 235, 0.0) !important;
        background: #ffffff !important;
        color: var(--hp-soft-ink) !important;
        padding: 0.55rem 0.75rem;
        min-height: 2.8rem;
        height: auto;
        white-space: normal;
        overflow: visible;
        text-align: left;
        line-height: 1.2;
        font-size: clamp(0.76rem, 1.8vw, 0.95rem);
    }

    section[data-testid="stSidebar"] div[data-testid="stPills"] button * {
        white-space: normal;
        overflow: visible;
        text-overflow: clip;
        line-height: 1.2;
        color: var(--hp-soft-ink) !important;
    }

    section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-selected="true"] {
        background: var(--hp-accent-soft) !important;
        border-color: #bfdbfe !important;
        color: var(--hp-accent) !important;
        font-weight: 650;
    }

    section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-selected="true"] * {
        color: var(--hp-accent) !important;
    }

    div[data-testid="stPlotlyChart"],
    iframe[title="streamlit_folium.st_folium"],
    div[data-testid="stDeckGlJsonChart"] {
        border: 1px solid var(--hp-border);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.94);
        box-shadow: 0 18px 45px rgba(15, 23, 42, 0.055);
        padding: 0.4rem;
    }

    div[data-testid="stImage"] img {
        border-radius: 8px;
        border: 1px solid var(--hp-border);
        box-shadow: 0 20px 50px rgba(15, 23, 42, 0.10);
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--hp-border);
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 18px 45px rgba(15, 23, 42, 0.045);
    }

    details[data-testid="stExpander"] {
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
        background: #f8fafc !important;
        box-shadow: 0 14px 34px rgba(15, 23, 42, 0.045);
        overflow: hidden;
    }

    details[data-testid="stExpander"] summary {
        background: #eef6ff !important;
        color: var(--hp-ink) !important;
        font-weight: 700;
    }

    details[data-testid="stExpander"] summary *,
    details[data-testid="stExpander"] div,
    details[data-testid="stExpander"] p,
    details[data-testid="stExpander"] span,
    details[data-testid="stExpander"] li {
        color: var(--hp-soft-ink) !important;
    }

    hr {
        border-color: var(--hp-border);
    }

    .hero-card {
        min-height: 430px;
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.70);
        box-shadow: 0 24px 70px rgba(15, 23, 42, 0.16);
        background-size: cover;
        background-position: center;
        overflow: hidden;
        margin-bottom: 1.5rem;
    }

    .hero-card__overlay {
        min-height: 430px;
        display: flex;
        flex-direction: column;
        justify-content: flex-end;
        padding: 2.25rem;
        background: linear-gradient(180deg, rgba(15, 23, 42, 0.08) 0%, rgba(15, 23, 42, 0.68) 100%);
    }

    .hero-card--large,
    .hero-card--large .hero-card__overlay {
        min-height: min(76vh, 720px);
    }

    .hero-card--large .hero-card__title {
        font-size: clamp(2.8rem, 6.8vw, 6.4rem);
        max-width: 1040px;
    }

    .hero-card--large .hero-card__copy {
        font-size: 1.18rem;
        max-width: 860px;
    }

    .hero-card__eyebrow {
        color: rgba(255, 255, 255, 0.82);
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.45rem;
    }

    .hero-card__title {
        color: #ffffff;
        font-size: clamp(2.2rem, 5vw, 4.8rem);
        font-weight: 800;
        line-height: 0.98;
        max-width: 880px;
        margin: 0;
    }

    .hero-card__copy {
        color: rgba(255, 255, 255, 0.88);
        font-size: 1.05rem;
        max-width: 760px;
        margin-top: 1rem;
    }

    .race-report-card,
    .finding-card,
    .pb-card,
    .placeholder-panel {
        border: 1px solid var(--hp-border);
        border-left: 4px solid var(--hp-accent);
        border-radius: 10px;
        background: linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(248,250,252,0.96) 100%);
        box-shadow: 0 16px 40px rgba(15, 23, 42, 0.055);
        padding: 1.1rem 1.15rem;
        height: 100%;
    }

    .card-eyebrow {
        color: var(--hp-muted);
        font-size: 0.74rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }

    .card-title {
        color: var(--hp-ink);
        font-size: 1.1rem;
        font-weight: 750;
        margin-bottom: 0.35rem;
    }

    .card-copy {
        color: var(--hp-soft-ink);
        font-size: 0.95rem;
        line-height: 1.55;
    }

    .landing-hero {
        position: relative;
        width: 100vw;
        min-height: calc(100vh - 4.5rem);
        margin: -1.25rem 0 -3.5rem calc(50% - 50vw);
        overflow: hidden;
        background: #f8fafc;
    }

    .landing-image {
        position: absolute;
        inset: 0;
        width: 100%;
        height: 100%;
        object-fit: cover;
        object-position: center 42%;
        z-index: 0;
    }

    .landing-scrim {
        position: relative;
        z-index: 1;
        min-height: calc(100vh - 4.5rem);
        display: flex;
        align-items: center;
        justify-content: flex-end;
        padding: clamp(1.25rem, 4vw, 4rem);
        background:
            linear-gradient(90deg, rgba(15, 23, 42, 0.03) 0%, rgba(15, 23, 42, 0.13) 48%, rgba(15, 23, 42, 0.42) 100%),
            linear-gradient(180deg, rgba(15, 23, 42, 0.05) 0%, rgba(15, 23, 42, 0.22) 100%);
    }

    .landing-bubble {
        width: min(760px, 100%);
        border: 1px solid rgba(255, 255, 255, 0.26);
        border-radius: 18px;
        background: rgba(31, 41, 55, 0.30);
        box-shadow: 0 28px 90px rgba(31, 41, 55, 0.24);
        backdrop-filter: blur(14px) saturate(125%);
        padding: clamp(1.35rem, 4vw, 3rem);
    }

    .landing-eyebrow {
        color: rgba(255, 255, 255, 0.84);
        font-size: 0.78rem;
        font-weight: 750;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        margin-bottom: 1rem;
    }

    .landing-title {
        color: #ffffff;
        font-size: clamp(2.65rem, 7.2vw, 6.4rem);
        font-weight: 850;
        letter-spacing: 0;
        line-height: 0.94;
        max-width: 720px;
        margin: 0;
    }

    .landing-copy {
        color: rgba(255, 255, 255, 0.88);
        font-size: clamp(1rem, 1.6vw, 1.24rem);
        line-height: 1.55;
        max-width: 650px;
        margin-top: 1.2rem;
    }

    .landing-actions {
        margin-top: 1.65rem;
    }

    .landing-enter {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 3.25rem;
        padding: 0.85rem 1.35rem;
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.56);
        background: rgba(255, 255, 255, 0.18);
        color: #ffffff;
        font-weight: 750;
        text-decoration: none;
        box-shadow: 0 16px 40px rgba(31, 41, 55, 0.18);
    }

    .landing-enter:hover {
        background: rgba(255, 255, 255, 0.26);
        color: #ffffff;
        text-decoration: none;
    }

    @media (max-width: 900px) {
        .landing-hero,
        .landing-scrim {
            min-height: calc(100vh - 3.5rem);
        }

        .landing-scrim {
            align-items: flex-end;
            justify-content: center;
            padding: 1rem;
            background:
                linear-gradient(180deg, rgba(31, 41, 55, 0.12) 0%, rgba(31, 41, 55, 0.72) 100%);
        }

        .landing-bubble {
            border-radius: 14px;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


data = load_all_data()
summary_df = data["summary"]
runs_df = data["runs"]
daily_df = data["daily"]
events_df = data["events"]

if "distance_unit" not in st.session_state:
    st.session_state.distance_unit = "mi"
if "dashboard_started" not in st.session_state:
    st.session_state.dashboard_started = False
if st.query_params.get("dashboard") == "1":
    st.session_state.dashboard_started = True

if not st.session_state.dashboard_started:
    render_landing_page()
    st.stop()

st.sidebar.title("My Endurance Story")
if st.sidebar.button("Start over"):
    st.session_state.dashboard_started = False
    st.query_params.clear()
    st.rerun()

unit_label = st.sidebar.segmented_control(
    "Units",
    ["Miles", "Kilometers"],
    default="Miles" if st.session_state.distance_unit == "mi" else "Kilometers",
)
st.session_state.distance_unit = "km" if unit_label == "Kilometers" else "mi"

page = st.sidebar.pills(
    "Navigate",
    [
        "Overview",
        "Key Findings",
        "Marathon Block Explorer",
        "Timeline View",
        "Personal Best Tracker",
        "Prediction Dynamics",
        "Running Atlas",
        "How Garmin Works",
    ],
    default="Overview",
    label_visibility="collapsed",
)

st.sidebar.divider()
st.sidebar.caption("Built from my own Garmin history")
st.sidebar.caption(f"{summary_df['block_name'].nunique()} marathon blocks")

if page == "Overview":
    render_overview(summary_df, runs_df, st.session_state.distance_unit)
elif page == "Key Findings":
    render_key_findings(summary_df, st.session_state.distance_unit)
elif page == "Marathon Block Explorer":
    render_block_explorer(summary_df, st.session_state.distance_unit)
elif page == "Timeline View":
    render_timeline_view(summary_df, daily_df, st.session_state.distance_unit)
elif page == "Personal Best Tracker":
    render_personal_best_tracker(events_df, runs_df, st.session_state.distance_unit)
elif page == "Prediction Dynamics":
    render_prediction_dynamics(summary_df, st.session_state.distance_unit)
elif page == "Running Atlas":
    render_running_atlas(runs_df, st.session_state.distance_unit)
elif page == "How Garmin Works":
    render_how_garmin_works()
