from pathlib import Path
import pandas as pd

from helpers import _read_json_records, _concat_dataframes, parse_garmin_date, drop_dup_dates, seconds_to_time
from helpers import apply_field_mapping
import json
from table_builders import create_running_table

# =========================
# PARSING
# =========================
def parse_activities_file(file_path, athlete_id):
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
    df.insert(1, "source_file", file_path.name)
    return df


def parse_activities(activity_files, athlete_id):
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
        print(f"Warning: {len(failed_files)} activity files failed to parse")

    return create_running_table(activities_df)


def parse_metrics_files(file_path, athlete_id):
    file_path = Path(file_path)
    df = pd.DataFrame(_read_json_records(file_path))
    if df.empty:
        return df

    df.insert(0, "athlete_id", athlete_id)
    df.insert(1, "source_file", file_path.name)
    # apply canonical mapping
    try:
        mapping = json.load(open(Path(__file__).parent / "schema" / "field_mappings.json"))
        df = apply_field_mapping(df, mapping)
    except Exception:
        pass

    if "date" in df.columns:
        # if mapping renamed calendarDate -> date, parse it
        df["date"] = parse_garmin_date(df["date"]) if df["date"].dtype == object else pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    elif "calendarDate" in df.columns:
        df["date"] = parse_garmin_date(df["calendarDate"])
    return df


def parse_metrics(metric_files, athlete_id):
    df = _concat_dataframes(
        [parse_metrics_files(file_path, athlete_id) for file_path in metric_files]
    )

    if df.empty:
        print("Warning: no metrics parsed")
        return df

    return drop_dup_dates(df, keep="first")


def parse_race_predictions_file(file_path, athlete_id):
    file_path = Path(file_path)
    df = pd.DataFrame(_read_json_records(file_path))
    if df.empty:
        return df

    df.insert(0, "athlete_id", athlete_id)
    df.insert(1, "source_file", file_path.name)
    try:
        mapping = json.load(open(Path(__file__).parent / "schema" / "field_mappings.json"))
        df = apply_field_mapping(df, mapping)
    except Exception:
        pass

    if "date" in df.columns:
        df["date"] = parse_garmin_date(df["date"]) if df["date"].dtype == object else pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    elif "calendarDate" in df.columns:
        df["date"] = parse_garmin_date(df["calendarDate"])
    return df


def parse_race_predictions(prediction_files, athlete_id):
    df = _concat_dataframes(
        [parse_race_predictions_file(file_path, athlete_id) for file_path in prediction_files]
    )

    if df.empty:
        print("Warning: no race predictions parsed")
        return df

    df = drop_dup_dates(df, keep="last")

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
    file_path = Path(file_path)
    df = pd.DataFrame(_read_json_records(file_path))
    if df.empty:
        return df

    df.insert(0, "athlete_id", athlete_id)
    df.insert(1, "source_file", file_path.name)
    try:
        mapping = json.load(open(Path(__file__).parent / "schema" / "field_mappings.json"))
        df = apply_field_mapping(df, mapping)
    except Exception:
        pass

    if "date" in df.columns:
        df["date"] = parse_garmin_date(df["date"]) if df["date"].dtype == object else pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    elif "calendarDate" in df.columns:
        df["date"] = parse_garmin_date(df["calendarDate"])
    return df


def parse_training_readiness(readiness_files, athlete_id):
    df = _concat_dataframes(
        [parse_training_readiness_file(file_path, athlete_id) for file_path in readiness_files]
    )

    if df.empty:
        print("Warning: no training readiness parsed")
        return df

    return df.sort_values(["date", "timestampLocal" if "timestampLocal" in df.columns else "timestamp"])


def parse_max_met_files(file_path, athlete_id):
    file_path = Path(file_path)
    df = pd.DataFrame(_read_json_records(file_path))
    if df.empty:
        return df

    df.insert(0, "athlete_id", athlete_id)
    df.insert(1, "source_file", file_path.name)
    try:
        mapping = json.load(open(Path(__file__).parent / "schema" / "field_mappings.json"))
        df = apply_field_mapping(df, mapping)
    except Exception:
        pass

    if "date" in df.columns:
        df["date"] = parse_garmin_date(df["date"]) if df["date"].dtype == object else pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    elif "calendarDate" in df.columns:
        df["date"] = parse_garmin_date(df["calendarDate"])
    return df


def parse_max_met(maxmet_files, athlete_id):
    df = _concat_dataframes(
        [parse_max_met_files(file_path, athlete_id) for file_path in maxmet_files]
    )

    if df.empty:
        print("Warning: no MaxMet parsed")
        return df

    return df.sort_values("date").reset_index(drop=True)


def parse_training_history_files(file_path, athlete_id):
    file_path = Path(file_path)
    df = pd.DataFrame(_read_json_records(file_path))
    if df.empty:
        return df

    df.insert(0, "athlete_id", athlete_id)
    df.insert(1, "source_file", file_path.name)
    try:
        mapping = json.load(open(Path(__file__).parent / "schema" / "field_mappings.json"))
        df = apply_field_mapping(df, mapping)
    except Exception:
        pass

    if "date" in df.columns:
        df["date"] = parse_garmin_date(df["date"]) if df["date"].dtype == object else pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    elif "calendarDate" in df.columns:
        df["date"] = parse_garmin_date(df["calendarDate"])
    return df


def parse_training_history(history_files, athlete_id):
    df = _concat_dataframes(
        [parse_training_history_files(file_path, athlete_id) for file_path in history_files]
    )

    if df.empty:
        print("Warning: no training history parsed")
        return df

    return df.sort_values("date").reset_index(drop=True)