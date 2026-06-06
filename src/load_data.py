from pathlib import Path

import pandas as pd
import streamlit as st


DATA_DIR = Path(__file__).parent.parent / "data_processed"

BLOCK_FILES = {
    "BQ Marathon": "bq_block_daily_v1.parquet",
    "Mesa Marathon": "mesa_block_daily_v1.parquet",
    "Indianapolis Marathon": "indianapolis_block_daily_v1.parquet",
    "Boston Marathon": "boston_block_daily_v1.parquet",
}

SUMMARY_FILE = "marathon_block_summary_v1.parquet"
RUNS_FILE = "runs_v1.parquet"
DAILY_MASTER_FILE = "daily_master_v1.parquet"
PREDICTION_COLUMN = "Marathon_pred_x"
STABILITY_RANGE_MINUTES = 2


@st.cache_data
def load_block_data(file_name):
    df = pd.read_parquet(DATA_DIR / file_name)
    df["date"] = pd.to_datetime(df["date"])
    return df


@st.cache_data
def load_block_summary():
    df = pd.read_parquet(DATA_DIR / SUMMARY_FILE)
    df["race_date"] = pd.to_datetime(df["race_date"])
    df["stable_date"] = pd.to_datetime(df["stable_date"])
    return df


@st.cache_data
def load_runs():
    df = pd.read_parquet(DATA_DIR / RUNS_FILE)
    df["start_time"] = pd.to_datetime(df["start_time"])
    return df


@st.cache_data
def load_daily_master():
    df = pd.read_parquet(DATA_DIR / DAILY_MASTER_FILE)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_all_data():
    return {
        "summary": load_block_summary(),
        "runs": load_runs(),
        "daily": load_daily_master(),
    }


@st.cache_data
def load_block_date_ranges():
    ranges = {}
    for block_name, file_name in BLOCK_FILES.items():
        block_df = load_block_data(file_name)
        ranges[block_name] = (block_df["date"].min(), block_df["date"].max())
    return ranges


@st.cache_data
def load_all_block_daily():
    block_frames = []
    for block_name, file_name in BLOCK_FILES.items():
        block_df = load_block_data(file_name).copy()
        block_df["block_name"] = block_name
        block_df["days_from_start"] = (block_df["date"] - block_df["date"].min()).dt.days
        block_frames.append(block_df)
    return pd.concat(block_frames, ignore_index=True)
