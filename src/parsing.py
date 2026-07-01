from pathlib import Path
import pandas as pd

from helpers import _read_json_records, _concat_dataframes, parse_garmin_date, drop_dup_dates, seconds_to_time
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
    df["5K_pred"] = df["raceTime5K"].apply(seconds_to_time)
    df["10K_pred"] = df["raceTime10K"].apply(seconds_to_time)
    df["Half_pred"] = df["raceTimeHalf"].apply(seconds_to_time)
    df["Marathon_pred"] = df["raceTimeMarathon"].apply(seconds_to_time)
    return df


def parse_training_readiness_file(file_path, athlete_id):
    file_path = Path(file_path)
    df = pd.DataFrame(_read_json_records(file_path))
    if df.empty:
        return df

    df.insert(0, "athlete_id", athlete_id)
    df.insert(1, "source_file", file_path.name)
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