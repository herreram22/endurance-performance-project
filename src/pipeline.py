# PROTOTYPE VERSION (SINGLE FILE)
#########################################
# Garmin Pipeline
#########################################

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

# =========================
# CONFIG
# =========================
BASE_PATH = Path.cwd() / "data_raw/all_garmin_data"
DEFAULT_OUTPUT_DIR = Path.cwd() / "data_processed/athletes"
PIPELINE_VERSION = "0.1.0"


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


# =========================
# DISCOVER PATHS
# =========================
def explore_files(data_raw_dir=BASE_PATH):
    data_raw_dir = Path(data_raw_dir)
    all_files = sorted(data_raw_dir.rglob("*.json"))

    discovered = {
        "activities": [],
        "metrics": [],
        "race_predictions": [],
        "max_met": [],
        "training_readiness": [],
        "training_history": [],
    }

    for file in all_files:
        name = file.name.lower()

        if "summarizedactivities" in name:
            discovered["activities"].append(file)
        elif name.startswith("metricsacutetrainingload"):
            discovered["metrics"].append(file)
        elif name.startswith("runracepredictions"):
            discovered["race_predictions"].append(file)
        elif name.startswith("trainingreadinessdto"):
            discovered["training_readiness"].append(file)
        elif name.startswith("metricsmaxmetdata"):
            discovered["max_met"].append(file)
        elif name.startswith("traininghistory"):
            discovered["training_history"].append(file)

    return discovered


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


# =========================
# TRANSFORM
# =========================
def create_running_table(df):
    runs_df = df[df["activityType"].eq("running")].copy()
    if runs_df.empty:
        return runs_df

    runs_df["start_time"] = pd.to_datetime(runs_df["startTimeLocal"], unit="ms", errors="coerce")
    runs_df["date"] = runs_df["start_time"].dt.normalize()

    runs_df["duration_minutes"] = runs_df["duration"] / 1000 / 60
    runs_df["distance_km"] = runs_df["distance"] / 100000
    runs_df["distance_miles"] = runs_df["distance"] / 160934.4
    runs_df["elevation_gain_m"] = runs_df["elevationGain"] / 100
    runs_df["elevation_loss_m"] = runs_df["elevationLoss"] / 100

    runs_df["max_speed_mps"] = runs_df["maxSpeed"] * 10
    runs_df["max_pace_mile"] = runs_df["max_speed_mps"].apply(lambda x: speed_to_pace(x, "mile"))
    runs_df["max_pace_km"] = runs_df["max_speed_mps"].apply(lambda x: speed_to_pace(x, "km"))

    runs_df["avg_speed_mps"] = runs_df["avgSpeed"] * 10
    runs_df["avg_pace_mile"] = runs_df["avg_speed_mps"].apply(lambda x: speed_to_pace(x, "mile"))
    runs_df["avg_pace_km"] = runs_df["avg_speed_mps"].apply(lambda x: speed_to_pace(x, "km"))

    runs_df["avg_stride_length_m"] = runs_df["avgStrideLength"] / 100
    runs_df["elapsed_duration_minutes"] = runs_df["elapsedDuration"] / 1000 / 60
    runs_df["moving_duration_minutes"] = runs_df["movingDuration"] / 1000 / 60

    for i in range(1, 7):
        col = f"hrTimeInZone_{i}"
        if col in runs_df.columns:
            runs_df[f"{col}_minutes"] = runs_df[col] / 1000 / 60

    for i in range(1, 6):
        col = f"powerTimeInZone_{i}"
        if col in runs_df.columns:
            runs_df[f"{col}_minutes"] = runs_df[col] / 1000 / 60

    drop_cols = [
        "maxTemperature",
        "minTemperature",
        "workoutComplianceScore",
        "workoutId",
        "matchedCuratedCourseId",
        "avgVerticalSpeed",
        "description",
        "totalReps",
        "totalSets",
        "activeSets",
        "summarizedExerciseSets",
        "courseId",
        "avgRespirationRate",
        "maxRespirationRate",
        "minRespirationRate",
        "workoutRpe",
        "workoutFeel",
        "parent",
        "runPowerWindDataEnabled",
        "atpActivity",
        "elevationCorrected",
        "autoCalcCalories",
        "purposeful",
        "decoDive",
        "favorite",
        "isRunPowerWindDataEnabled",
        "anaerobicTrainingEffectMessage",
        "aerobicTrainingEffectMessage",
        "manufacturer",
        "startTimeGmt",
        "startTimeLocal",
        "rule",
        "eventTypeId",
        "uuidMsb",
        "uuidLsb",
        "timeZoneId",
        "beginTimestamp",
        "sportType",
    ]

    return runs_df.drop(columns=drop_cols, errors="ignore")


def build_daily_master_table(athlete_id, runs, metrics, predictions, readiness, maxmet, history):
    if runs is None or runs.empty:
        print("Warning: daily master cannot be built without runs")
        return pd.DataFrame()

    runs = normalize_date(runs)

    daily_master = (
        runs.groupby("date")
        .agg(
            athlete_id=("athlete_id", "first"),
            run_count=("activityId", "count"),
            total_distance_km=("distance_km", "sum"),
            total_distance_miles=("distance_miles", "sum"),
            total_duration_minutes=("duration_minutes", "sum"),
            total_moving_minutes=("moving_duration_minutes", "sum"),
            total_elevation_gain_m=("elevation_gain_m", "sum"),
            avg_hr=("avgHr", "mean"),
            max_hr=("maxHr", "max"),
            avg_pace_mile=(
                "avg_speed_mps",
                lambda x: 26.8224 / x.mean() if pd.notna(x.mean()) and x.mean() > 0 else np.nan,
            ),
            avg_power=("avgPower", "mean"),
            max_power=("maxPower", "max"),
            avg_cadence=("avgDoubleCadence", "mean"),
            avg_stride_length_m=("avg_stride_length_m", "mean"),
            total_training_load=("activityTrainingLoad", "sum"),
            aerobic_te_avg=("aerobicTrainingEffect", "mean"),
            anaerobic_te_avg=("anaerobicTrainingEffect", "mean"),
            pr_count=("pr", "sum"),
        )
        .reset_index()
    )

    if metrics is not None and not metrics.empty:
        metrics_subset = _select_existing(
            drop_dup_dates(normalize_date(metrics), keep="first"),
            [
                "date",
                "acwrPercent",
                "acwrStatus",
                "acwrStatusFeedback",
                "dailyTrainingLoadAcute",
                "dailyTrainingLoadChronic",
                "dailyAcuteChronicWorkloadRatio",
            ],
        )
        daily_master = daily_master.merge(metrics_subset, on="date", how="left")

    if predictions is not None and not predictions.empty:
        prediction_subset = _select_existing(
            drop_dup_dates(normalize_date(predictions), keep="last"),
            ["date", "5K_pred", "10K_pred", "Half_pred", "Marathon_pred"],
        )
        daily_master = daily_master.merge(prediction_subset, on="date", how="left")

    if maxmet is not None and not maxmet.empty:
        max_met_subset = _select_existing(
            drop_dup_dates(normalize_date(maxmet), keep="last"),
            ["date", "vo2MaxValue", "fitnessAge", "fitnessAgeDescription", "maxMet"],
        )
        daily_master = daily_master.merge(max_met_subset, on="date", how="left")

    if readiness is not None and not readiness.empty:
        readiness = normalize_date(readiness)
        readiness_sort_col = "timestampLocal" if "timestampLocal" in readiness.columns else "timestamp"
        training_readiness_daily_df = (
            readiness.sort_values(["date", readiness_sort_col])
            .groupby("date")
            .agg(
                readiness_score_first=("score", "first"),
                readiness_score_last=("score", "last"),
                readiness_score_mean=("score", "mean"),
                readiness_level_last=("level", "last"),
                recovery_time_last=("recoveryTime", "last"),
                acute_load_last=("acuteLoad", "last"),
                hrv_weekly_avg_last=("hrvWeeklyAverage", "last"),
                sleep_score_last=("sleepScore", "last"),
                valid_sleep_any=("validSleep", "max"),
                readiness_snapshots=("score", "count"),
            )
            .reset_index()
        )
        daily_master = daily_master.merge(training_readiness_daily_df, on="date", how="left")

    if history is not None and not history.empty:
        history = normalize_date(history)
        agg_map = {
            "load_tunnel_min": ("loadTunnelMin", "min"),
            "training_status_first": ("trainingStatus", "first"),
            "training_status_last": ("trainingStatus", "last"),
            "training_status": ("trainingStatus", "last"),
            "fitness_level_trend": ("fitnessLevelTrend", "last"),
            "load_level_trend": ("loadLevelTrend", "last"),
        }
        if "loadTunnelMax" in history.columns:
            agg_map["load_tunnel_max"] = ("loadTunnelMax", "max")

        training_history_daily_df = (
            history.sort_values("date")
            .groupby("date")
            .agg(**agg_map)
            .reset_index()
        )
        daily_master = daily_master.merge(training_history_daily_df, on="date", how="left")

    daily_master["athlete_id"] = daily_master["athlete_id"].fillna(athlete_id)
    return daily_master.sort_values("date").reset_index(drop=True)


# =========================
# SAVING
# =========================
def _safe_date_range(df, date_col="date"):
    if df is None or df.empty or date_col not in df.columns:
        return None

    dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
    if dates.empty:
        return None

    return {
        "start": dates.min().strftime("%Y-%m-%d"),
        "end": dates.max().strftime("%Y-%m-%d"),
    }


def _make_parquet_safe(df):
    """Convert nested Garmin JSON columns to strings before parquet writes."""
    df = df.copy()

    for col in df.columns:
        if df[col].dtype != "object":
            continue

        has_nested = df[col].map(lambda x: isinstance(x, (dict, list))).any()
        if not has_nested:
            continue

        df[col] = df[col].map(
            lambda x: json.dumps(x)
            if isinstance(x, (dict, list)) and len(x) > 0
            else (None if isinstance(x, (dict, list)) else x)
        )

    return df


def save_outputs(athlete_id, outputs, output_dir, pipeline_version=PIPELINE_VERSION, overwrite=True):
    output_dir = Path(output_dir)
    athlete_output_dir = output_dir / str(athlete_id)
    athlete_output_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "athlete_id": athlete_id,
        "pipeline_version": pipeline_version,
        "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(athlete_output_dir),
        "datasets": {},
    }

    for dataset_name, df in outputs.items():
        if df is None:
            metadata["datasets"][dataset_name] = {
                "saved": False,
                "reason": "DataFrame is None",
            }
            print(f"Skipped {dataset_name}: DataFrame is None")
            continue

        if not isinstance(df, pd.DataFrame):
            metadata["datasets"][dataset_name] = {
                "saved": False,
                "reason": "Object is not a DataFrame",
            }
            print(f"Skipped {dataset_name}: Object not a DataFrame: {type(df)}")
            continue

        if df.empty:
            metadata["datasets"][dataset_name] = {
                "saved": False,
                "reason": "DataFrame is empty",
            }
            print(f"Skipped {dataset_name}: DataFrame is empty")
            continue

        output_path = athlete_output_dir / f"{dataset_name}.parquet"
        if output_path.exists() and not overwrite:
            raise FileExistsError(f"{output_path} already exists and overwrite=False")

        df_to_save = _make_parquet_safe(df)
        df_to_save.to_parquet(output_path, index=False)

        metadata["datasets"][dataset_name] = {
            "saved": True,
            "file": str(output_path),
            "rows": len(df_to_save),
            "columns": len(df_to_save.columns),
            "column_names": list(df_to_save.columns),
            "date_range": _safe_date_range(df_to_save),
        }

        print(f"Saved {dataset_name}: {len(df_to_save)} rows x {len(df_to_save.columns)} columns")

    metadata_path = athlete_output_dir / "metadata.json"
    if metadata_path.exists() and not overwrite:
        raise FileExistsError(f"{metadata_path} already exists and overwrite=False")

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=4)

    print(f"Saved metadata: {metadata_path}")
    return metadata


# =========================
# PIPELINE
# =========================
def process_athlete(
    athlete_id,
    raw_data_dir=BASE_PATH,
    output_dir=DEFAULT_OUTPUT_DIR,
    overwrite=True,
):
    files = explore_files(raw_data_dir)

    runs_df = parse_activities(files["activities"], athlete_id)
    metrics_df = parse_metrics(files["metrics"], athlete_id)
    predictions_df = parse_race_predictions(files["race_predictions"], athlete_id)
    readiness_df = parse_training_readiness(files["training_readiness"], athlete_id)
    maxmet_df = parse_max_met(files["max_met"], athlete_id)
    history_df = parse_training_history(files["training_history"], athlete_id)

    daily_master = build_daily_master_table(
        athlete_id=athlete_id,
        runs=runs_df,
        metrics=metrics_df,
        predictions=predictions_df,
        readiness=readiness_df,
        maxmet=maxmet_df,
        history=history_df,
    )

    outputs = {
        "runs": runs_df,
        "metrics": metrics_df,
        "predictions": predictions_df,
        "readiness": readiness_df,
        "maxmet": maxmet_df,
        "history": history_df,
        "daily_master": daily_master,
    }

    save_outputs(
        athlete_id,
        outputs,
        output_dir,
        pipeline_version=PIPELINE_VERSION,
        overwrite=overwrite,
    )

    return daily_master


if __name__ == "__main__":
    process_athlete("pablo", BASE_PATH, DEFAULT_OUTPUT_DIR)
