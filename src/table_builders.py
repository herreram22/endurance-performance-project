"""Transform parsed Garmin datasets into athlete-day analytical tables.

This module is the pipeline's transformation and merge stage. It converts raw
running activities into stable engineering units, aggregates runs by day,
constructs a complete calendar spanning every available source, and left-joins
optional physiological, prediction, readiness, and training-status features.
It also stacks validated per-athlete daily tables into the combined panel.

Inputs are pandas DataFrames returned by :mod:`parsing`; outputs are DataFrames
persisted by :mod:`save_output`. Optional Garmin capabilities are represented by
null columns and coverage flags so athletes with older or different devices are
not lost from the panel.
"""

import pandas as pd
import numpy as np
from pathlib import Path

from helpers import normalize_date, drop_dup_dates, _select_existing, speed_to_pace

# =========================
# TRANSFORM
# =========================
def standardize_daily_master_schema(df):
    """Normalize a daily-master frame to the combined-panel contract.

    Args:
        df (pandas.DataFrame | None): Per-athlete daily table.

    Returns:
        pandas.DataFrame | None: Copy with normalized dates, required base
        columns, and a boolean ``readiness_available`` coverage flag.

    Notes:
        Missing required columns are added as nulls here so frames from different
        device generations can be aligned. Persistence validation still enforces
        the minimum production contract before saving.
    """
    if df is None or df.empty:
        return df

    df = df.copy()
    df = normalize_date(df)

    required = ["date", "athlete_id", "total_distance_km", "total_duration_minutes"]
    for col in required:
        if col not in df.columns:
            df[col] = np.nan

    readiness_cols = [
        "readiness_score_first",
        "readiness_score_last",
        "readiness_score_mean",
        "readiness_level_last",
        "recovery_time_last",
        "acute_load_last",
        "sleep_score_last",
        "valid_sleep_any",
    ]
    available_readiness_cols = [col for col in readiness_cols if col in df.columns]
    if available_readiness_cols:
        df["readiness_available"] = df[available_readiness_cols].notna().any(axis=1)
    else:
        df["readiness_available"] = False

    return df


def build_multi_athlete_daily_master(daily_master_frames):
    """Stack athlete-level daily tables into one canonical panel.

    Args:
        daily_master_frames (Iterable[pandas.DataFrame]): Per-athlete tables.

    Returns:
        pandas.DataFrame: Union-schema panel sorted by ``athlete_id`` and
        ``date``. Empty inputs are ignored; all-empty input returns an empty
        frame.

    Notes:
        Column order is stabilized for downstream consumers. Optional columns
        are unioned rather than intersected, preventing device-capability
        differences from deleting athlete rows.
    """
    frames = []
    for frame in daily_master_frames:
        if frame is None or frame.empty:
            continue
        frames.append(standardize_daily_master_schema(frame))

    if not frames:
        return pd.DataFrame()

    base_cols = ["date", "athlete_id", "total_distance_km", "total_duration_minutes"]
    extra_cols = []
    for df in frames:
        for col in df.columns:
            if col not in base_cols and col not in extra_cols:
                extra_cols.append(col)

    # Keep the logical order stable across athletes for downstream analysis.
    ordered_cols = list(base_cols)
    for col in [
        "readiness_score_last",
        "readiness_level_last",
        "recovery_time_last",
        "acute_load_last",
        "sleep_score_last",
        "valid_sleep_any",
        "readiness_snapshots",
        "load_tunnel_min",
        "training_status_first",
        "training_status_last",
        "training_status",
        "fitness_level_trend",
        "load_level_trend",
        "load_tunnel_max",
        "avg_power",
        "max_power",
        "avg_cadence",
        "acwrPercent",
        "acwrStatus",
        "acwrStatusFeedback",
        "dailyTrainingLoadAcute",
        "dailyTrainingLoadChronic",
        "dailyAcuteChronicWorkloadRatio",
        "5K_pred",
        "10K_pred",
        "Half_pred",
        "Marathon_pred",
        "fitnessAge",
        "fitnessAgeDescription",
        "readiness_available",
    ]:
        if col in extra_cols and col not in ordered_cols:
            ordered_cols.append(col)

    for col in extra_cols:
        if col not in ordered_cols:
            ordered_cols.append(col)

    combined = []
    for df in frames:
        combined.append(df.reindex(columns=ordered_cols))

    out = pd.concat(combined, ignore_index=True, sort=False)
    out["readiness_available"] = out["readiness_available"].fillna(False)
    out = out.sort_values(["athlete_id", "date"]).reset_index(drop=True)
    return out


def create_running_table(df):
    """Filter summarized activities to running and derive analytical fields.

    Args:
        df (pandas.DataFrame): Parsed summarized activities. Expected Garmin
            fields include ``activityType``, millisecond timestamps/durations,
            scaled distance/elevation values, and speed.

    Returns:
        pandas.DataFrame: Running-only activities with normalized ``date``,
        kilometres/miles, minutes, metres, metre-per-second speeds, paces, and
        available heart-rate/power-zone durations.

    Notes:
        Garmin summarized exports encode several quantities in scaled integer
        units: distance uses 1/100,000 km, elevation uses centimetres, duration
        uses milliseconds, and summarized speed requires a factor of ten.
        Raw analysis-irrelevant columns are removed with ``errors="ignore"`` so
        older devices with narrower schemas remain compatible.
    """
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
    """Merge parsed sources into a single continuous athlete-day table.

    Args:
        athlete_id (str): Anonymized identifier written to every output row.
        runs (pandas.DataFrame): Engineered running activities; this source is
            required because it establishes the analytical athlete.
        metrics (pandas.DataFrame): Optional one-row-per-day acute-load metrics.
        predictions (pandas.DataFrame): Optional race-prediction snapshots.
        readiness (pandas.DataFrame): Optional intraday readiness snapshots.
        maxmet (pandas.DataFrame): Optional MaxMet/VO2-max observations.
        history (pandas.DataFrame): Optional training-status snapshots.

    Returns:
        pandas.DataFrame: One row per calendar day from the earliest through
        latest valid date across all supplied sources. Rest-day training totals
        are zero; unavailable physiological fields remain null.

    Side Effects:
        Prints warnings when runs are unavailable or invalid 1970 fallback dates
        are removed.

    Notes:
        A complete calendar is used because recovery and prediction signals can
        exist on non-running days. Merge policies are source-specific:
        predictions/MaxMet use the last daily snapshot, metrics use their
        deduplicated daily record, readiness exposes first/last/mean/count, and
        history exposes explicit first/last/min/max values.
    """
    if runs is None or runs.empty:
        print("Warning: daily master cannot be built without runs")
        return pd.DataFrame()

    runs = normalize_date(runs)
    # Field aliases allow old processed schemas and newly canonicalized parser
    # outputs to enter the same aggregation without duplicating merge logic.
    import json
    mapping = {}
    try:
        mapping = json.load(open(Path(__file__).parent / "schema" / "field_mappings.json"))
    except Exception:
        mapping = {}

    def _resolve_col(col, df):
        # Return the column name present in df: prefer the original raw name, else the mapped canonical name
        if col in df.columns:
            return col
        mapped = mapping.get(col)
        if mapped and mapped in df.columns:
            return mapped
        # also try reverse: if col looks like canonical, try to find raw by checking mapping items
        for raw, canon in mapping.items():
            if canon == col and raw in df.columns:
                return raw
        return None

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

    # Resolve agg_map columns to actual columns present in `runs`
    resolved_agg = {}
    for out_col, expr in agg_map.items():
        src = expr[0]
        func = expr[1]
        actual = _resolve_col(src, runs)
        if actual is not None:
            resolved_agg[out_col] = (actual, func)

    run_daily = runs.groupby("date").agg(**resolved_agg).reset_index()

    # Recovery and training signals exist on rest days. Using only run dates as
    # the merge base would systematically discard those observations.
    date_series = []
    for frame in (runs, metrics, predictions, readiness, maxmet, history):
        if frame is None or frame.empty or "date" not in frame.columns:
            continue
        dates = pd.to_datetime(frame["date"], errors="coerce").dropna().dt.normalize()
        if not dates.empty:
            date_series.append(dates)

    all_dates = pd.concat(date_series, ignore_index=True)
    calendar = pd.DataFrame({
        "date": pd.date_range(all_dates.min(), all_dates.max(), freq="D")
    })
    daily_master = calendar.merge(run_daily, on="date", how="left")
    daily_master["athlete_id"] = athlete_id

    zero_on_rest_days = [
        "run_count",
        "total_distance_km",
        "total_distance_miles",
        "total_duration_minutes",
        "total_moving_minutes",
        "total_elevation_gain_m",
        "total_training_load",
        "pr_count",
    ]
    for col in zero_on_rest_days:
        if col in daily_master.columns:
            daily_master[col] = daily_master[col].fillna(0)

    for optional_col in optional_columns.keys():
        if optional_col not in daily_master.columns:
            daily_master[optional_col] = np.nan

    if metrics is not None and not metrics.empty:
        metrics_df = drop_dup_dates(normalize_date(metrics), keep="first")
        # expand candidate columns using mapping
        desired = [
            "date",
            "acwrPercent",
            "acwrStatus",
            "acwrStatusFeedback",
            "dailyTrainingLoadAcute",
            "dailyTrainingLoadChronic",
            "dailyAcuteChronicWorkloadRatio",
        ]
        expanded = []
        for col in desired:
            expanded.append(col)
            if col in mapping:
                expanded.append(mapping[col])

        metrics_subset = _select_existing(metrics_df, expanded)
        daily_master = daily_master.merge(metrics_subset, on="date", how="left")

    if predictions is not None and not predictions.empty:
        pred_df = drop_dup_dates(normalize_date(predictions), keep="last")
        desired = ["date", "5K_pred", "10K_pred", "Half_pred", "Marathon_pred"]
        expanded = []
        for col in desired:
            expanded.append(col)
            if col in mapping:
                expanded.append(mapping[col])
        prediction_subset = _select_existing(pred_df, expanded)
        daily_master = daily_master.merge(prediction_subset, on="date", how="left")

    if maxmet is not None and not maxmet.empty:
        mm = drop_dup_dates(normalize_date(maxmet), keep="last")
        desired = ["date", "vo2MaxValue", "fitnessAge", "fitnessAgeDescription", "maxMet"]
        expanded = []
        for col in desired:
            expanded.append(col)
            if col in mapping:
                expanded.append(mapping[col])
        max_met_subset = _select_existing(mm, expanded)
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

    daily_master["athlete_id"] = athlete_id

    if "date" in daily_master.columns:
        bad_dates = pd.to_datetime(daily_master["date"], errors="coerce")
        bad_mask = bad_dates.dt.year == 1970
        if bad_mask.any():
            print(f"Warning: dropping {bad_mask.sum()} invalid 1970-01-01 daily_master rows for athlete {athlete_id}")
            daily_master = daily_master.loc[~bad_mask]

    return daily_master.sort_values("date").reset_index(drop=True)
