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
    render_block_explorer,
    render_data_tables,
    render_overview,
    render_prediction_dynamics,
    render_running_atlas,
)


st.set_page_config(
    page_title="Endurance Performance Dashboard",
    layout="wide",
)

st.markdown(
    """
    <style>
    :root {
        --hp-ink: #111827;
        --hp-soft-ink: #4b5563;
        --hp-muted: #6b7280;
        --hp-border: #e5e7eb;
        --hp-panel: rgba(255, 255, 255, 0.88);
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

    p, li, label, .stMarkdown {
        color: var(--hp-soft-ink);
    }

    div[data-testid="stMetric"] {
        background: var(--hp-panel);
        border: 1px solid var(--hp-border);
        border-radius: 12px;
        padding: 1rem 1rem 0.85rem;
        box-shadow: 0 18px 45px rgba(15, 23, 42, 0.06);
        backdrop-filter: blur(12px);
    }

    div[data-testid="stMetricLabel"] {
        color: var(--hp-muted);
        font-size: 0.82rem;
    }

    div[data-testid="stMetricValue"] {
        color: var(--hp-ink);
        font-weight: 750;
    }

    div[data-testid="stMetricDelta"] {
        color: var(--hp-accent);
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
        color: var(--hp-soft-ink);
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

    section[data-testid="stSidebar"] div[data-testid="stPills"] {
        gap: 0.35rem;
    }

    section[data-testid="stSidebar"] div[data-testid="stPills"] button {
        width: 100%;
        justify-content: flex-start;
        border-radius: 10px;
        border: 1px solid transparent;
        background: transparent;
        color: var(--hp-soft-ink);
        padding: 0.55rem 0.75rem;
    }

    section[data-testid="stSidebar"] div[data-testid="stPills"] button[aria-selected="true"] {
        background: var(--hp-accent-soft);
        border-color: #bfdbfe;
        color: var(--hp-accent);
        font-weight: 650;
    }

    div[data-testid="stPlotlyChart"],
    iframe[title="streamlit_folium.st_folium"],
    div[data-testid="stDeckGlJsonChart"] {
        border: 1px solid var(--hp-border);
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.94);
        box-shadow: 0 18px 45px rgba(15, 23, 42, 0.055);
        padding: 0.4rem;
    }

    div[data-testid="stImage"] img {
        border-radius: 12px;
        border: 1px solid var(--hp-border);
        box-shadow: 0 20px 50px rgba(15, 23, 42, 0.10);
    }

    div[data-testid="stDataFrame"] {
        border: 1px solid var(--hp-border);
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 18px 45px rgba(15, 23, 42, 0.045);
    }

    hr {
        border-color: var(--hp-border);
    }
    </style>
    """,
    unsafe_allow_html=True,
)


data = load_all_data()
summary_df = data["summary"]
runs_df = data["runs"]
daily_df = data["daily"]

st.sidebar.title("Endurance Analytics")
page = st.sidebar.pills(
    "Navigate",
    [
        "Overview",
        "Marathon Block Explorer",
        "Prediction Dynamics",
        "Running Atlas",
        "Data Tables",
    ],
    default="Overview",
    label_visibility="collapsed",
)

st.sidebar.divider()
st.sidebar.caption("Historical Garmin export analysis")
st.sidebar.caption(f"{summary_df['block_name'].nunique()} marathon blocks")

if page == "Overview":
    render_overview(summary_df, runs_df)
elif page == "Marathon Block Explorer":
    render_block_explorer(summary_df)
elif page == "Prediction Dynamics":
    render_prediction_dynamics(summary_df)
elif page == "Running Atlas":
    render_running_atlas(runs_df)
else:
    render_data_tables(summary_df, daily_df, runs_df)
