"""Shared normalization helpers for Garmin parsers and table builders.

The functions here handle recurring Garmin-specific representation issues:
mixed date encodings, nested JSON records, duplicate daily snapshots, unit
conversion, canonical field aliases, and privacy-safe source provenance.
Parsers use these helpers to normalize individual datasets; table builders use
them to enforce a consistent athlete-day grain.

Inputs are primarily pandas Series/DataFrames and decoded JSON paths. Functions
return new objects where practical and do not write pipeline outputs.
"""

import pandas as pd
import json
import re

EMAIL_PATTERN = re.compile(r"[^@\s/\\]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,63}")
GARMIN_COMPACT_DATE_MIN = 19000101
GARMIN_COMPACT_DATE_MAX = 29991231
EPOCH_SECONDS_THRESHOLD = 10**9
EPOCH_MILLISECONDS_THRESHOLD = 10**12

# =========================
# HELPERS
# =========================
def speed_to_pace(speed_mps, unit="mile"):
    """Convert speed in metres per second to ``M:SS`` running pace.

    Args:
        speed_mps (float): Speed in metres per second.
        unit (str): Distance unit for the pace denominator; ``"mile"`` uses
            1,609.34 metres and any other value uses one kilometre.

    Returns:
        str | None: Pace text, or ``None`` for null/non-positive speeds.
    """
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
    """Read a nested dictionary path without raising for missing levels.

    Args:
        d (dict): Mapping to traverse.
        keys (Iterable[str]): Ordered nested keys.
        default (Any): Value returned when traversal cannot continue.

    Returns:
        Any: Located value or ``default``.
    """
    current = d
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def deidentify_source_filename(filename):
    """Redact email addresses that Garmin embeds in some export filenames.

    Args:
        filename (str | pathlib.Path): Source basename stored as provenance.

    Returns:
        str: Filename with email-like tokens replaced by ``[redacted-email]``.

    Notes:
        The original raw path remains in the private raw export. Analytical
        Parquet files retain useful provenance without exposing identity.
    """
    return EMAIL_PATTERN.sub("[redacted-email]", str(filename))


def seconds_to_time(seconds):
    """Format a numeric duration as zero-padded ``HH:MM:SS``.

    Args:
        seconds (int | float): Duration in seconds. Values are rounded.

    Returns:
        str | None: Formatted duration, or ``None`` when input is missing.
    """
    if pd.isna(seconds):
        return None

    seconds = int(round(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def parse_garmin_date(series):
    """Normalize heterogeneous Garmin dates to midnight pandas timestamps.

    Args:
        series (pandas.Series): Values encoded as date strings, numeric
            ``YYYYMMDD``, Unix seconds, or Unix milliseconds.

    Returns:
        pandas.Series: ``datetime64`` values normalized to midnight; malformed
        values become ``NaT``.

    Notes:
        Garmin reuses ``calendarDate`` across export generations with different
        encodings. Magnitude checks prevent integer ``YYYYMMDD`` values from
        being mistaken for nanoseconds since 1970.
    """
    if series.empty:
        return pd.to_datetime(series, errors="coerce")

    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().mean() > 0.8:
        # decide units based on magnitude
        mx = numeric.dropna().max()
        mn = numeric.dropna().min()
        if mn >= GARMIN_COMPACT_DATE_MIN and mx <= GARMIN_COMPACT_DATE_MAX:
            return pd.to_datetime(
                numeric.round().astype("Int64").astype("string"),
                format="%Y%m%d",
                errors="coerce",
            ).dt.normalize()
        if mx > EPOCH_MILLISECONDS_THRESHOLD:
            # very large -> milliseconds
            return pd.to_datetime(numeric, unit="ms", errors="coerce").dt.normalize()
        if mx > EPOCH_SECONDS_THRESHOLD:
            # likely seconds
            return pd.to_datetime(numeric, unit="s", errors="coerce").dt.normalize()

    # fallback: let pandas infer formats for mixed types
    return pd.to_datetime(series, errors="coerce").dt.normalize()


def drop_invalid_dates(df, dataset_name="dataset"):
    """Remove records that cannot participate in athlete-day outputs.

    Args:
        df (pandas.DataFrame | None): Parsed dataset.
        dataset_name (str): Human-readable name used in warning diagnostics.

    Returns:
        pandas.DataFrame | None: Reset filtered frame. Frames without a ``date``
        column are returned unchanged so the calling parser can decide whether
        that schema is supported.

    Side Effects:
        Prints a warning listing affected record counts and source filenames.
    """
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
    """Return a copy with one date column coerced and normalized to midnight.

    Args:
        df (pandas.DataFrame | None): Input table.
        date_col (str): Column to normalize.

    Returns:
        pandas.DataFrame | None: Normalized copy, or the original empty/invalid
        input when the requested column is unavailable.
    """
    if df is not None and not df.empty and date_col in df.columns:
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col], errors="coerce").dt.normalize()
    return df


def drop_dup_dates(df, keep="last"):
    """Collapse a daily snapshot dataset to one deterministic row per date.

    Args:
        df (pandas.DataFrame | None): Date-bearing input records.
        keep (str): Duplicate policy passed to ``DataFrame.drop_duplicates``.

    Returns:
        pandas.DataFrame | None: Date-sorted, reset frame.

    Notes:
        This helper is appropriate only for sources whose production contract is
        one record per day. Training readiness and training history preserve
        multiple intraday snapshots until their dedicated daily aggregation.
    """
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
    """Rename available Garmin fields to canonical schema names.

    Args:
        df (pandas.DataFrame | None): Parsed records.
        mapping (dict[str, str]): Raw-to-canonical field mapping.

    Returns:
        pandas.DataFrame | None: Frame with available mapped columns renamed.
        Unknown columns are preserved for backward compatibility.
    """
    if df is None or df.empty:
        return df

    # Build rename dict for columns present
    rename = {src: dst for src, dst in mapping.items() if src in df.columns}
    if rename:
        return df.rename(columns=rename)
    return df
