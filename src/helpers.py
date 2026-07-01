import pandas as pd
import json

# =========================
# HELPERS
# =========================
def speed_to_pace(speed_mps, unit="mile"):
    """Convert meters/second to a pace string."""
    if pd.isna(speed_mps) or speed_mps <= 0:
        return None

    meters = 1609.34 if unit == "mile" else 1000
    pace = meters / speed_mps / 60
    minutes = int(pace)
    seconds = int(round((pace - minutes) * 60))

    if seconds == 60:
        minutes += 1
        seconds = 0

    return f"{minutes}:{seconds:02d}"


def safe_get(d, keys, default=None):
    """Get nested values from a dictionary."""
    current = d
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def seconds_to_time(seconds):
    if pd.isna(seconds):
        return None

    seconds = int(round(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_garmin_date(series):
    """Parse Garmin calendarDate values that may be strings or epoch ms."""
    if series.empty:
        return pd.to_datetime(series, errors="coerce")

    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().mean() > 0.8 and numeric.dropna().gt(10**11).all():
        return pd.to_datetime(numeric, unit="ms", errors="coerce").dt.normalize()

    return pd.to_datetime(series, errors="coerce").dt.normalize()


def normalize_date(df, date_col="date"):
    if df is not None and not df.empty and date_col in df.columns:
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.normalize()
    return df


def drop_dup_dates(df, keep="last"):
    """Drop duplicate date rows and return a new DataFrame."""
    if df is None or df.empty or "date" not in df.columns:
        return df
    return df.sort_values("date").drop_duplicates(subset=["date"], keep=keep).reset_index(drop=True)


def _read_json_records(file_path):
    with open(file_path, "r") as f:
        data = json.load(f)
    return data if isinstance(data, list) else [data]


def _concat_dataframes(frames):
    frames = [df for df in frames if isinstance(df, pd.DataFrame) and not df.empty]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def _select_existing(df, columns):
    return df[[col for col in columns if col in df.columns]].copy()
