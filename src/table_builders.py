import pandas as pd
import numpy as np

from helpers import normalize_date, drop_dup_dates, _select_existing, speed_to_pace

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

    agg_map = {
        "athlete_id": ("athlete_id", "first"),
        "run_count": ("activityId", "count"),
        "total_distance_km": ("distance_km", "sum"),
        "total_distance_miles": ("distance_miles", "sum"),
        "total_duration_minutes": ("duration_minutes", "sum"),
        "total_moving_minutes": ("moving_duration_minutes", "sum"),
        "total_elevation_gain_m": ("elevation_gain_m", "sum"),
        "avg_hr": ("avgHr", "mean"),
        "max_hr": ("maxHr", "max"),
        "avg_pace_mile": (
            "avg_speed_mps",
            lambda x: 26.8224 / x.mean() if pd.notna(x.mean()) and x.mean() > 0 else np.nan,
        ),
        "avg_stride_length_m": ("avg_stride_length_m", "mean"),
        "total_training_load": ("activityTrainingLoad", "sum"),
        "aerobic_te_avg": ("aerobicTrainingEffect", "mean"),
        "anaerobic_te_avg": ("anaerobicTrainingEffect", "mean"),
        "pr_count": ("pr", "sum"),
    }

    optional_columns = {
        "avg_power": ("avgPower", "mean"),
        "max_power": ("maxPower", "max"),
        "avg_cadence": ("avgDoubleCadence", "mean"),
    }

    for output_col, agg_expr in optional_columns.items():
        if agg_expr[0] in runs.columns:
            agg_map[output_col] = agg_expr

    daily_master = runs.groupby("date").agg(**agg_map).reset_index()

    for optional_col in optional_columns.keys():
        if optional_col not in daily_master.columns:
            daily_master[optional_col] = np.nan

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