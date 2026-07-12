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
    if numeric.notna().mean() > 0.8:
        # decide units based on magnitude
        mx = numeric.dropna().max()
        mn = numeric.dropna().min()
        if mn >= 19000101 and mx <= 29991231:
            return pd.to_datetime(
                numeric.round().astype("Int64").astype("string"),
                format="%Y%m%d",
                errors="coerce",
            ).dt.normalize()
        if mx > 10 ** 12:
            # very large -> milliseconds
            return pd.to_datetime(numeric, unit="ms", errors="coerce").dt.normalize()
        if mx > 10 ** 9:
            # likely seconds
            return pd.to_datetime(numeric, unit="s", errors="coerce").dt.normalize()

    # fallback: let pandas infer formats for mixed types
    return pd.to_datetime(series, errors="coerce").dt.normalize()


def drop_invalid_dates(df, dataset_name="dataset"):
    """Remove records that cannot participate in date-grained outputs."""
    if df is None or df.empty or "date" not in df.columns:
        return df
    invalid = df["date"].isna()
    if invalid.any():
        sources = []
        if "source_file" in df.columns:
            sources = sorted(df.loc[invalid, "source_file"].dropna().astype(str).unique())
        source_note = f" from {sources}" if sources else ""
        print(
            f"Warning: dropping {int(invalid.sum())} {dataset_name} record(s) "
            f"with no valid date{source_note}"
        )
        df = df.loc[~invalid].copy()
    return df.reset_index(drop=True)


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


def apply_field_mapping(df, mapping):
    """Rename columns in `df` according to `mapping` dict where keys are
    source names (or variants) and values are canonical names.
    Only renames columns that exist in the DataFrame.
    """
    if df is None or df.empty:
        return df

    # Build rename dict for columns present
    rename = {src: dst for src, dst in mapping.items() if src in df.columns}
    if rename:
        return df.rename(columns=rename)
    return df
