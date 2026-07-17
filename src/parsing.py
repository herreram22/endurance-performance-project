"""Parse classified Garmin JSON files into athlete-scoped tabular datasets.

This module is the second production pipeline stage. File-level parsers decode a
single Garmin export and attach ``athlete_id`` plus privacy-safe source
provenance. Dataset-level parsers concatenate shards, normalize dates and field
aliases, and apply source-specific duplicate policies.

Inputs are file lists produced by :func:`discover_paths.explore_files`. Outputs
are pandas DataFrames consumed by :func:`table_builders.build_daily_master_table`
and persisted by :mod:`save_output`. Garmin exports are allowed to omit optional
datasets; those parsers return empty frames and emit explicit warnings.

Design decisions:
    * Canonical field mappings preserve compatibility across Garmin schemas.
    * Race predictions collapse duplicate dates to the latest snapshot.
    * Metrics collapse to the first deterministic daily record.
    * Readiness and history preserve intraday/device snapshots for later daily
      aggregation.
"""

from pathlib import Path
import pandas as pd

from helpers import (
    _read_json_records,
    _concat_dataframes,
    parse_garmin_date,
    drop_dup_dates,
    seconds_to_time,
    deidentify_source_filename,
)
from helpers import apply_field_mapping, drop_invalid_dates
import json
from table_builders import create_running_table

# =========================
# PARSING
# =========================
def parse_activities_file(file_path, athlete_id):
    """Parse one wrapped Garmin summarized-activities JSON file.

    Args:
        file_path (pathlib.Path | str): JSON object containing a
            ``summarizedActivitiesExport`` list.
        athlete_id (str): Anonymized ID propagated to every parsed row.

    Returns:
        pandas.DataFrame: Raw activity records with athlete and source
        provenance. An empty frame is returned when the wrapper contains no
        activities.

    Raises:
        json.JSONDecodeError: If the file is not valid JSON.

    Notes:
        Garmin activities use a wrapper object unlike most metric exports.
        Email-bearing filenames are redacted before entering analytical data.
    """
    file_path = Path(file_path)
    records = _read_json_records(file_path)

    rows = []
    for record in records:
        rows.extend(record.get("summarizedActivitiesExport", []))

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # apply canonical field mapping when possible
    try:
        mapping = json.load(open(Path(__file__).parent / "schema" / "field_mappings.json"))
        df = apply_field_mapping(df, mapping)
    except Exception:
        pass

    df.insert(0, "athlete_id", athlete_id)
    df.insert(1, "source_file", deidentify_source_filename(file_path.name))
    return df


def parse_activities(activity_files, athlete_id):
    """Combine activity shards and derive the running-activity table.

    Args:
        activity_files (Iterable[pathlib.Path]): Classified activity files.
        athlete_id (str): Anonymized athlete identifier.

    Returns:
        pandas.DataFrame: Running activities with normalized dates, units, and
        derived pace fields.

    Raises:
        RuntimeError: If any classified activity file fails parsing. Partial
            activity ingestion is rejected because it would silently understate
            training volume.

    Side Effects:
        Prints a warning when no activities are available.
    """
    frames = []
    failed_files = []

    for file_path in activity_files:
        try:
            frames.append(parse_activities_file(file_path, athlete_id))
        except Exception as e:
            failed_files.append({"file": str(file_path), "error": str(e)})

    activities_df = _concat_dataframes(frames)
    if activities_df.empty:
        print("Warning: no activities parsed")
        return activities_df

    if failed_files:
        failures = "; ".join(f"{item['file']}: {item['error']}" for item in failed_files)
        raise RuntimeError(
            f"{len(failed_files)} activity file(s) failed to parse: {failures}"
        )

    return create_running_table(activities_df)


def parse_metrics_files(file_path, athlete_id):
    """Parse one flat Garmin daily-metrics JSON shard.

    Args:
        file_path (pathlib.Path | str): Classified JSON list or record.
        athlete_id (str): Anonymized athlete identifier.

    Returns:
        pandas.DataFrame: Canonically named records with a normalized ``date``
        when ``date`` or ``calendarDate`` is present.
    """
    file_path = Path(file_path)
    df = pd.DataFrame(_read_json_records(file_path))
    if df.empty:
        return df

    df.insert(0, "athlete_id", athlete_id)
    df.insert(1, "source_file", deidentify_source_filename(file_path.name))
    # apply canonical mapping
    try:
        mapping = json.load(open(Path(__file__).parent / "schema" / "field_mappings.json"))
        df = apply_field_mapping(df, mapping)
    except Exception:
        pass

    if "date" in df.columns:
        df["date"] = parse_garmin_date(df["date"])
    elif "calendarDate" in df.columns:
        df["date"] = parse_garmin_date(df["calendarDate"])
    return df


def parse_metrics(metric_files, athlete_id):
    """Build one-row-per-day Garmin acute-load/metrics data.

    Args:
        metric_files (Iterable[pathlib.Path]): Supported flat metric shards.
        athlete_id (str): Anonymized athlete identifier.

    Returns:
        pandas.DataFrame: Valid, date-deduplicated daily metrics. Date-less
        profile schemas are rejected as empty instead of entering merges.

    Side Effects:
        Prints warnings for missing or unsupported metric content and for
        records dropped due to invalid dates.
    """
    df = _concat_dataframes(
        [parse_metrics_files(file_path, athlete_id) for file_path in metric_files]
    )

    if df.empty:
        print("Warning: no metrics parsed")
        return df
    if "date" not in df.columns:
        print("Warning: no dated daily metrics parsed")
        return pd.DataFrame()

    return drop_dup_dates(drop_invalid_dates(df, "metrics"), keep="first")


def parse_race_predictions_file(file_path, athlete_id):
    """Parse one Garmin race-prediction export shard.

    Args:
        file_path (pathlib.Path | str): Race-prediction JSON path.
        athlete_id (str): Anonymized athlete identifier.

    Returns:
        pandas.DataFrame: Prediction snapshots with canonical fields and dates.
    """
    file_path = Path(file_path)
    df = pd.DataFrame(_read_json_records(file_path))
    if df.empty:
        return df

    df.insert(0, "athlete_id", athlete_id)
    df.insert(1, "source_file", deidentify_source_filename(file_path.name))
    try:
        mapping = json.load(open(Path(__file__).parent / "schema" / "field_mappings.json"))
        df = apply_field_mapping(df, mapping)
    except Exception:
        pass

    if "date" in df.columns:
        df["date"] = parse_garmin_date(df["date"])
    elif "calendarDate" in df.columns:
        df["date"] = parse_garmin_date(df["calendarDate"])
    return df


def parse_race_predictions(prediction_files, athlete_id):
    """Combine Garmin race predictions and format predicted finish times.

    Args:
        prediction_files (Iterable[pathlib.Path]): Prediction shards.
        athlete_id (str): Anonymized athlete identifier.

    Returns:
        pandas.DataFrame: One latest snapshot per date, including ``5K_pred``,
        ``10K_pred``, ``Half_pred``, and ``Marathon_pred`` strings. Missing
        device capabilities remain null.

    Notes:
        Candidate raw and canonical column names support exports produced before
        and after schema normalization.
    """
    df = _concat_dataframes(
        [parse_race_predictions_file(file_path, athlete_id) for file_path in prediction_files]
    )

    if df.empty:
        print("Warning: no race predictions parsed")
        return df

    df = drop_dup_dates(drop_invalid_dates(df, "race predictions"), keep="last")

    # Helper to pick the first existing candidate column name
    def _pick_col(df, candidates):
        for c in candidates:
            if c in df.columns:
                return c
        return None

    col_5k = _pick_col(df, ["race_time_5k", "raceTime5K", "raceTime5k"])
    col_10k = _pick_col(df, ["race_time_10k", "raceTime10K", "raceTime10k"])
    col_half = _pick_col(df, ["race_time_half", "raceTimeHalf"])
    col_marathon = _pick_col(df, ["race_time_marathon", "raceTimeMarathon"])

    df["5K_pred"] = df[col_5k].apply(seconds_to_time) if col_5k is not None else None
    df["10K_pred"] = df[col_10k].apply(seconds_to_time) if col_10k is not None else None
    df["Half_pred"] = df[col_half].apply(seconds_to_time) if col_half is not None else None
    df["Marathon_pred"] = df[col_marathon].apply(seconds_to_time) if col_marathon is not None else None
    return df


def parse_training_readiness_file(file_path, athlete_id):
    """Parse one Garmin training-readiness snapshot shard.

    Args:
        file_path (pathlib.Path | str): Readiness JSON path.
        athlete_id (str): Anonymized athlete identifier.

    Returns:
        pandas.DataFrame: Readiness snapshots with canonical date fields.
    """
    file_path = Path(file_path)
    df = pd.DataFrame(_read_json_records(file_path))
    if df.empty:
        return df

    df.insert(0, "athlete_id", athlete_id)
    df.insert(1, "source_file", deidentify_source_filename(file_path.name))
    try:
        mapping = json.load(open(Path(__file__).parent / "schema" / "field_mappings.json"))
        df = apply_field_mapping(df, mapping)
    except Exception:
        pass

    if "date" in df.columns:
        df["date"] = parse_garmin_date(df["date"])
    elif "calendarDate" in df.columns:
        df["date"] = parse_garmin_date(df["calendarDate"])
    return df


def parse_training_readiness(readiness_files, athlete_id):
    """Combine readiness shards while retaining intraday snapshots.

    Args:
        readiness_files (Iterable[pathlib.Path]): Readiness JSON shards.
        athlete_id (str): Anonymized athlete identifier.

    Returns:
        pandas.DataFrame: Valid snapshots sorted by date and local timestamp
        where available.

    Notes:
        Multiple records on one day are intentional: Garmin may update
        readiness after sleep, naps, or workouts. Daily first/last/mean values
        are calculated later by the table builder.
    """
    df = _concat_dataframes(
        [parse_training_readiness_file(file_path, athlete_id) for file_path in readiness_files]
    )

    if df.empty:
        print("Warning: no training readiness parsed")
        return df

    df = drop_invalid_dates(df, "training readiness")
    return df.sort_values(["date", "timestampLocal" if "timestampLocal" in df.columns else "timestamp"])


def parse_max_met_files(file_path, athlete_id):
    """Parse one Garmin MaxMet or activity VO2-max shard.

    Args:
        file_path (pathlib.Path | str): MaxMet/VO2-max JSON path.
        athlete_id (str): Anonymized athlete identifier.

    Returns:
        pandas.DataFrame: Canonically named physiological snapshots with dates.
    """
    file_path = Path(file_path)
    df = pd.DataFrame(_read_json_records(file_path))
    if df.empty:
        return df

    df.insert(0, "athlete_id", athlete_id)
    df.insert(1, "source_file", deidentify_source_filename(file_path.name))
    try:
        mapping = json.load(open(Path(__file__).parent / "schema" / "field_mappings.json"))
        df = apply_field_mapping(df, mapping)
    except Exception:
        pass

    if "date" in df.columns:
        df["date"] = parse_garmin_date(df["date"])
    elif "calendarDate" in df.columns:
        df["date"] = parse_garmin_date(df["calendarDate"])
    return df


def parse_max_met(maxmet_files, athlete_id):
    """Combine Garmin MaxMet and activity VO2-max records.

    Args:
        maxmet_files (Iterable[pathlib.Path]): Classified physiological shards.
        athlete_id (str): Anonymized athlete identifier.

    Returns:
        pandas.DataFrame: Valid records sorted by date. Multiple same-day
        observations remain available; the daily merge later selects the latest.
    """
    df = _concat_dataframes(
        [parse_max_met_files(file_path, athlete_id) for file_path in maxmet_files]
    )

    if df.empty:
        print("Warning: no MaxMet parsed")
        return df

    return drop_invalid_dates(df, "MaxMet").sort_values("date").reset_index(drop=True)


def parse_training_history_files(file_path, athlete_id):
    """Parse one Garmin training-history shard.

    Args:
        file_path (pathlib.Path | str): Training-history JSON path.
        athlete_id (str): Anonymized athlete identifier.

    Returns:
        pandas.DataFrame: Canonically named training-status snapshots.
    """
    file_path = Path(file_path)
    df = pd.DataFrame(_read_json_records(file_path))
    if df.empty:
        return df

    df.insert(0, "athlete_id", athlete_id)
    df.insert(1, "source_file", deidentify_source_filename(file_path.name))
    try:
        mapping = json.load(open(Path(__file__).parent / "schema" / "field_mappings.json"))
        df = apply_field_mapping(df, mapping)
    except Exception:
        pass

    if "date" in df.columns:
        df["date"] = parse_garmin_date(df["date"])
    elif "calendarDate" in df.columns:
        df["date"] = parse_garmin_date(df["calendarDate"])
    return df


def parse_training_history(history_files, athlete_id):
    """Combine Garmin training-history shards without losing snapshots.

    Args:
        history_files (Iterable[pathlib.Path]): Training-history JSON paths.
        athlete_id (str): Anonymized athlete identifier.

    Returns:
        pandas.DataFrame: Valid training-status records sorted by date.

    Notes:
        Same-day device/sport snapshots are meaningful. The daily master uses
        explicit first/last/min/max aggregations rather than dropping them here.
    """
    df = _concat_dataframes(
        [parse_training_history_files(file_path, athlete_id) for file_path in history_files]
    )

    if df.empty:
        print("Warning: no training history parsed")
        return df

    return drop_invalid_dates(df, "training history").sort_values("date").reset_index(drop=True)
