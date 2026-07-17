"""Generate a privacy-safe data dictionary from persisted pipeline schemas.

This read-only utility inventories per-athlete production Parquet files and
creates a Markdown reference describing each dataset and column. It records
pandas types, athlete/file coverage, nullability, and curated meanings for core
fields without emitting sample values, Garmin IDs, source filenames, or other
potentially identifying content.

Inputs are athlete output directories created by :mod:`pipeline`. The output is
a Markdown document suitable for developer documentation. Combined panel files
at the output root are excluded because their columns are already represented by
the per-athlete ``daily_master`` dataset.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import pandas as pd

from src.save_output import DATASET_REQUIRED_COLUMNS


DATASET_METADATA = {
    "runs": {
        "purpose": "Running activities normalized from Garmin summarized-activity exports.",
        "grain": "One row per running activity.",
        "primary_key": "`athlete_id`, `activity_id`",
        "duplicate_handling": "No activity-level deduplication; source activity IDs are retained for audit.",
        "merge_strategy": "Aggregated by normalized activity date when building `daily_master`.",
        "update_frequency": "One batch refresh per Garmin export ingestion.",
        "upstream": "Garmin ZIP → `*summarizedActivities*.json` → activities parser → running transformation",
        "downstream": "`daily_master`, combined athlete-day panel, research analyses",
    },
    "metrics": {
        "purpose": "Supported Garmin acute/chronic load and acclimation metrics.",
        "grain": "At most one retained record per athlete-date.",
        "primary_key": "`athlete_id`, `date`",
        "duplicate_handling": "Invalid dates are dropped; the first deterministic record per date is retained.",
        "merge_strategy": "Left-joined to the complete `daily_master` calendar by `date`.",
        "update_frequency": "One batch refresh per Garmin export ingestion.",
        "upstream": "Garmin ZIP → acute-load/heat-altitude metrics JSON → metrics parser",
        "downstream": "`daily_master`, workload and acclimation research",
    },
    "predictions": {
        "purpose": "Garmin race-time prediction snapshots and formatted finish-time features.",
        "grain": "Latest retained prediction snapshot per athlete-date.",
        "primary_key": "`athlete_id`, `date`",
        "duplicate_handling": "Invalid dates are dropped; the last deterministic snapshot per date is retained.",
        "merge_strategy": "Formatted predictions are left-joined to `daily_master` by `date`.",
        "update_frequency": "One batch refresh per Garmin export ingestion.",
        "upstream": "Garmin ZIP → `RunRacePredictions*.json` → predictions parser",
        "downstream": "`daily_master`, prediction-drift and race-performance research",
    },
    "readiness": {
        "purpose": "Intraday Garmin Training Readiness snapshots and contributing factors.",
        "grain": "One readiness snapshot; multiple athlete-date rows are intentional.",
        "primary_key": "No stable exported key; use `athlete_id`, `date`, and timestamp together.",
        "duplicate_handling": "Snapshots are preserved and sorted; they are not treated as duplicates.",
        "merge_strategy": "Aggregated to daily first/last/mean/count and left-joined by `date`.",
        "update_frequency": "Device-generated intraday; batch-refreshed per Garmin export.",
        "upstream": "Garmin ZIP → `TrainingReadiness*.json` → readiness parser",
        "downstream": "`daily_master`, recovery/readiness research",
    },
    "maxmet": {
        "purpose": "Garmin MaxMet, VO2-max, and fitness-age observations.",
        "grain": "One Garmin physiological observation; multiple same-day rows may occur.",
        "primary_key": "No universal key; activity-linked rows may use `activity_id`.",
        "duplicate_handling": "All valid observations are retained; daily merge selects the last date-sorted row.",
        "merge_strategy": "Latest daily VO2-max/MaxMet/fitness-age values are left-joined by `date`.",
        "update_frequency": "Device-estimated after qualifying activities; batch-refreshed per export.",
        "upstream": "Garmin ZIP → `MetricsMaxMetData*` or `ActivityVo2Max*` JSON → MaxMet parser",
        "downstream": "`daily_master`, physiological trend research",
    },
    "history": {
        "purpose": "Garmin training-status, training-load tunnel, and trend snapshots.",
        "grain": "One training-history snapshot; multiple athlete-date rows may be valid.",
        "primary_key": "No stable exported key; use athlete/date/timestamp and device context.",
        "duplicate_handling": "Snapshots are preserved; daily aggregation uses explicit first/last/min/max rules.",
        "merge_strategy": "Daily status/trend summaries are left-joined to `daily_master` by `date`.",
        "update_frequency": "Device-generated snapshots; batch-refreshed per Garmin export.",
        "upstream": "Garmin ZIP → `TrainingHistory*.json` → training-history parser",
        "downstream": "`daily_master`, training-status and load-trend research",
    },
    "daily_master": {
        "purpose": "Continuous research-ready athlete-day panel combining running and optional Garmin signals.",
        "grain": "Exactly one row per athlete-calendar date across each athlete's observed range.",
        "primary_key": "`athlete_id`, `date`",
        "duplicate_handling": "Persistence rejects duplicate athlete-date rows.",
        "merge_strategy": "Complete date calendar plus left joins; running totals are zero on rest days and optional signals remain null.",
        "update_frequency": "Rebuilt after successful athlete ingestion; combined panel rebuilt after a successful batch.",
        "upstream": "`runs`, `metrics`, `predictions`, `readiness`, `maxmet`, and `history`",
        "downstream": "Combined multi-athlete panel, statistical analyses, and machine-learning feature development",
    },
}

FIELD_OVERRIDES = {
    "athlete_id": ("Anonymized athlete key assigned from the raw athlete directory.", "Metadata", "N/A", "Non-empty pipeline-safe identifier", "Required in every saved dataset; never infer from Garmin identity fields.", "Directory name → athlete_id"),
    "date": ("Calendar date normalized to midnight.", "Canonical / Renamed", "date", "Valid calendar date; 1970 fallback dates rejected in daily master", "Derived from Garmin `calendarDate` or local activity start time; timezone-naive.", "calendarDate/startTimeLocal → date"),
    "source_file": ("Source JSON basename retained as parser provenance.", "Metadata", "N/A", "N/A", "Embedded email addresses are redacted before persistence.", "raw filename → redacted source_file"),
    "user_id": ("Garmin user-profile numeric identifier.", "Canonical / Renamed", "identifier", "Unknown", "Potentially stable within Garmin; use `athlete_id`, not this field, for research joins.", "userProfilePK → user_id"),
    "device_id": ("Garmin identifier for the recording or estimating device.", "Canonical / Renamed", "identifier", "Unknown", "Device ID is not a watch-model label and may vary across an athlete's history.", "deviceId → device_id"),
    "activity_id": ("Garmin activity identifier.", "Canonical / Renamed", "identifier", "Positive integer when present", "Expected to identify an activity within Garmin; activity-linked MaxMet rows may be sparse.", "activityId → activity_id"),
    "activity_uuid": ("Garmin UUID associated with an activity.", "Canonical / Renamed", "UUID", "UUID-form text", "Optional activity-level identifier.", "activityUuid → activity_uuid"),
    "run_count": ("Count of running activities on the date.", "Aggregated", "count", "≥0 integer", "Derived from running activities only; zero on rest days.", "runs.activity_id → daily count"),
    "total_distance_km": ("Sum of running distance on the date.", "Aggregated", "kilometres", "≥0", "Derived from running activities only; zero on rest days.", "distance ÷ 100000 → distance_km → daily sum"),
    "total_distance_miles": ("Sum of running distance on the date.", "Aggregated", "miles", "≥0", "Derived from running activities only; zero on rest days.", "distance ÷ 160934.4 → distance_miles → daily sum"),
    "total_duration_minutes": ("Sum of running activity duration on the date.", "Aggregated", "minutes", "≥0", "Includes recorded activity duration; zero on rest days.", "duration ms ÷ 60000 → daily sum"),
    "total_moving_minutes": ("Sum of Garmin moving duration on the date.", "Aggregated", "minutes", "≥0", "Dependent on Garmin movement detection; zero on rest days.", "movingDuration ms ÷ 60000 → daily sum"),
    "total_elevation_gain_m": ("Sum of running elevation gain on the date.", "Aggregated", "metres", "≥0", "Elevation source/correction can vary by device and activity.", "elevationGain ÷ 100 → daily sum"),
    "avg_hr": ("Mean of activity-average heart rate across runs on the date.", "Aggregated", "bpm", "20–250 bpm", "Unweighted mean across activities, not a duration-weighted daily heart rate.", "avgHr → daily mean"),
    "max_hr": ("Maximum reported heart rate across runs on the date.", "Aggregated", "bpm", "20–250 bpm", "Derived from running activities only and watch/sensor dependent.", "maxHr → daily maximum"),
    "avg_power": ("Mean of activity-average running power across runs on the date.", "Aggregated", "watts", "0–1500 W", "Optional and watch/sensor dependent; unweighted across activities.", "avgPower → daily mean"),
    "max_power": ("Maximum activity-level running power reported on the date.", "Aggregated", "watts", "0–1500 W validation range", "Optional and watch/sensor dependent; current data contain values above 1500 W that should be treated as potential spikes/outliers.", "maxPower → daily maximum"),
    "avg_cadence": ("Mean Garmin double cadence across runs on the date.", "Aggregated", "steps per minute", "0–300 steps/min", "Uses `avgDoubleCadence`; confirm cadence convention before comparing with single-leg fields.", "avgDoubleCadence → daily mean"),
    "avg_pace_mile": ("Pace derived from mean running speed for the date.", "Derived", "minutes per mile", ">0 when running speed is available", "Computed from the mean of activity-average speeds; not distance-weighted.", "avgSpeed × 10 → mean m/s → 26.8224 ÷ speed"),
    "avg_stride_length_m": ("Mean activity-average stride length across runs.", "Aggregated", "metres", "≥0", "Garmin stride definition and availability are device dependent.", "avgStrideLength ÷ 100 → daily mean"),
    "total_training_load": ("Sum of Garmin activity training-load values on the date.", "Aggregated", "Garmin load units", "≥0", "Proprietary Garmin/EPOC-derived load; zero on rest days when the source field exists.", "activityTrainingLoad → daily sum"),
    "aerobic_te_avg": ("Mean Garmin aerobic Training Effect across runs.", "Aggregated", "score", "0–5", "Unweighted across activities; Garmin Training Effect is a proprietary activity score.", "aerobicTrainingEffect → daily mean"),
    "anaerobic_te_avg": ("Mean Garmin anaerobic Training Effect across runs.", "Aggregated", "score", "0–5", "Unweighted across activities; may be absent for older devices.", "anaerobicTrainingEffect → daily mean"),
    "pr_count": ("Count/sum of Garmin personal-record flags on the date.", "Aggregated", "count", "≥0", "Depends on the semantics of Garmin's activity-level `pr` flag; zero on rest days.", "pr → daily sum"),
    "5K_pred": ("Garmin predicted 5 km finish time formatted by the pipeline.", "Derived", "HH:MM:SS", ">00:00:00", "Last prediction snapshot per date; null when unsupported.", "raceTime5K → race_time_5k seconds → formatted text"),
    "10K_pred": ("Garmin predicted 10 km finish time formatted by the pipeline.", "Derived", "HH:MM:SS", ">00:00:00", "Last prediction snapshot per date; null when unsupported.", "raceTime10K → race_time_10k seconds → formatted text"),
    "Half_pred": ("Garmin predicted half-marathon finish time formatted by the pipeline.", "Derived", "HH:MM:SS", ">00:00:00", "Last prediction snapshot per date; null when unsupported.", "raceTimeHalf → race_time_half seconds → formatted text"),
    "Marathon_pred": ("Garmin predicted marathon finish time formatted by the pipeline.", "Derived", "HH:MM:SS", ">00:00:00", "Last prediction snapshot per date; null when unsupported.", "raceTimeMarathon → race_time_marathon seconds → formatted text"),
    "vo2max": ("Garmin estimated maximal oxygen uptake.", "Canonical / Renamed", "mL/kg/min", "20–90 physiological validation range", "Model-derived estimate, not a laboratory measurement; zero occurs in raw exports as a likely missing/sentinel value and should not be interpreted physiologically.", "vo2MaxValue or vO2MaxValue → vo2max"),
    "max_met": ("Garmin maximum metabolic-equivalent estimate.", "Canonical / Renamed", "METs", "≥0", "Garmin estimate; approximately related to VO2 by 1 MET = 3.5 mL/kg/min.", "maxMet → max_met"),
    "fitnessAge": ("Garmin estimated fitness age.", "Raw Garmin", "years or categorical text", "Unknown", "Representation varies across export generations; do not assume numeric dtype.", "fitnessAge → latest daily value"),
    "readiness_available": ("Whether any readiness feature is populated on the athlete-date.", "Derived", "boolean", "True/False", "Coverage indicator; false can mean unsupported device/export, not poor readiness.", "daily readiness fields → any non-null"),
    "readiness_score_first": ("First Training Readiness score observed on the date.", "Aggregated", "score", "0–100", "First intraday snapshot; timestamp ordering is used.", "readiness.score → daily first"),
    "readiness_score_last": ("Last Training Readiness score observed on the date.", "Aggregated", "score", "0–100", "Preferred end-of-day snapshot when studying daily state.", "readiness.score → daily last"),
    "readiness_score_mean": ("Arithmetic mean of Training Readiness snapshots on the date.", "Aggregated", "score", "0–100", "Snapshot-weighted rather than time-weighted.", "readiness.score → daily mean"),
    "readiness_snapshots": ("Number of Training Readiness snapshots on the date.", "Aggregated", "count", "≥0 integer", "Snapshot count can reflect intraday recalculation after sleep, naps, or workouts.", "readiness.score → daily count"),
    "training_status_first": ("First Garmin training-status label on the date.", "Aggregated", "category", "Garmin-defined categories", "Multiple device/sport snapshots may exist.", "trainingStatus → daily first"),
    "training_status_last": ("Last Garmin training-status label on the date.", "Aggregated", "category", "Garmin-defined categories", "Multiple device/sport snapshots may exist.", "trainingStatus → daily last"),
    "training_status": ("Daily Garmin training-status label, equal to the last snapshot.", "Aggregated", "category", "Garmin-defined categories", "Proprietary status; interpret as a device estimate rather than clinical state.", "trainingStatus → daily last"),
}

RAW_CANONICAL_MAP = {
    "calendarDate": "date",
    "userProfilePK": "user_id",
    "deviceId": "device_id",
    "timestamp": "timestamp",
    "timestampGMT": "timestamp",
    "timestampGmt": "timestamp",
    "timestampLocal": "timestamp_local",
    "vo2MaxValue": "vo2max",
    "maxMet": "max_met",
    "raceTime5K": "race_time_5k",
    "raceTime10K": "race_time_10k",
    "raceTimeHalf": "race_time_half",
    "raceTimeMarathon": "race_time_marathon",
    "activityId": "activity_id",
    "activityUuid": "activity_uuid",
}

DAILY_LINEAGE = {
    "acute_load_last": "readiness.acuteLoad → daily last",
    "hrv_weekly_avg_last": "readiness.hrvWeeklyAverage → daily last",
    "readiness_level_last": "readiness.level → daily last",
    "recovery_time_last": "readiness.recoveryTime → daily last",
    "sleep_score_last": "readiness.sleepScore → daily last",
    "valid_sleep_any": "readiness.validSleep → daily maximum/any true",
    "fitness_level_trend": "history.fitnessLevelTrend → daily last",
    "load_level_trend": "history.loadLevelTrend → daily last",
    "load_tunnel_min": "history.loadTunnelMin → daily minimum",
    "load_tunnel_max": "history.loadTunnelMax → daily maximum",
    "max_met": "maxmet.max_met → daily last",
    "vo2max": "maxmet.vo2max → daily last",
    "fitnessAge": "maxmet.fitnessAge → daily last",
    "fitnessAgeDescription": "maxmet.fitnessAgeDescription → daily last",
}


def _raw_field_metadata(column_name):
    """Infer conservative metadata for recognizable Garmin source names."""
    lower = column_name.lower()
    lineage = f"{column_name} → retained without value transformation"
    variable_type = (
        "Canonical / Renamed"
        if column_name in {"timestamp", "timestamp_local"}
        or column_name in RAW_CANONICAL_MAP.values()
        else "Raw Garmin"
    )

    exact = {
        "activityType": ("Garmin activity type used to retain running activities.", "category", "Garmin-defined activity types", "The runs table contains only rows equal to `running`."),
        "name": ("User- or Garmin-assigned activity name.", "text", "Unknown", "Free text; avoid using directly as a model feature without privacy review."),
        "locationName": ("Garmin-reported activity location label.", "text", "Unknown", "Potentially identifying geographic text; requires privacy review before research export."),
        "sport": ("Garmin sport category associated with the observation.", "category", "Garmin-defined values", "May distinguish running/cycling estimates and device contexts."),
        "subSport": ("Garmin sport subtype associated with the observation.", "category", "Garmin-defined values", "Optional and export-generation dependent."),
        "timestamp": ("Garmin event/snapshot timestamp coerced by the pipeline.", "datetime", "Valid timestamp", "Numeric epochs are interpreted as seconds or milliseconds by magnitude."),
        "timestamp_local": ("Garmin local snapshot timestamp coerced by the pipeline.", "datetime", "Valid timestamp", "Timezone information is not retained in the current Parquet representation."),
        "updateTimestamp": ("Garmin timestamp indicating when the physiological estimate was updated.", "datetime", "Valid timestamp", "Coerced from numeric epoch values before Parquet persistence."),
        "start_time": ("Local activity start time derived from Garmin epoch milliseconds.", "datetime", "Valid timestamp", "Used to derive the activity calendar date."),
        "distance": ("Raw Garmin summarized activity distance.", "scaled distance", "≥0", "Pipeline scaling indicates 100,000 raw units per kilometre."),
        "duration": ("Raw Garmin activity duration.", "milliseconds", "≥0", "Converted to `duration_minutes`."),
        "elapsedDuration": ("Raw elapsed time from activity start to finish.", "milliseconds", "≥0", "May exceed moving duration because stopped time is included."),
        "movingDuration": ("Garmin-estimated moving time.", "milliseconds", "≥0", "Dependent on Garmin movement detection."),
        "elevationGain": ("Raw accumulated elevation gain.", "centimetres", "≥0", "Converted to `elevation_gain_m`."),
        "elevationLoss": ("Raw accumulated elevation loss.", "centimetres", "≥0", "Converted to `elevation_loss_m`."),
        "avgSpeed": ("Raw Garmin activity-average speed in the summarized export's scaled representation.", "0.1 metres/second", "≥0", "Multiplied by 10 to create `avg_speed_mps`."),
        "maxSpeed": ("Raw Garmin maximum speed in the summarized export's scaled representation.", "0.1 metres/second", "≥0", "Multiplied by 10 to create `max_speed_mps`."),
        "avgGradeAdjustedSpeed": ("Garmin activity-average speed adjusted for grade, retained in raw export scaling.", "0.1 metres/second", "≥0", "Not converted by the current pipeline; multiply by 10 for metres/second if validated against future fixtures."),
        "avgStrideLength": ("Raw Garmin average stride length.", "centimetres", "≥0", "Divided by 100 to create metres."),
        "avgVerticalOscillation": ("Garmin average vertical torso oscillation while running.", "centimetres", "≥0", "Running-dynamics metric; watch or compatible sensor dependent."),
        "avgVerticalRatio": ("Garmin average vertical ratio: vertical oscillation relative to stride length.", "percent", "0–100%", "Running-dynamics metric; lower is not universally better without pace/context."),
        "avgGroundContactTime": ("Garmin average time each foot is in contact with the ground.", "milliseconds", "≥0", "Running-dynamics metric; watch or compatible sensor dependent."),
        "avgGroundContactBalance": ("Garmin left/right ground-contact-time balance.", "percent", "0–100%", "Running-dynamics metric; exact left/right encoding should be confirmed before directional interpretation."),
        "avgHr": ("Garmin activity-average heart rate.", "bpm", "20–250 bpm", "Watch or paired heart-rate-sensor dependent."),
        "maxHr": ("Garmin maximum activity heart rate.", "bpm", "20–250 bpm", "Watch or paired heart-rate-sensor dependent."),
        "minHr": ("Garmin minimum activity heart rate.", "bpm", "20–250 bpm physiological range", "Zero occurs in the export and should be treated as missing/sensor dropout rather than a valid heart rate."),
        "avgPower": ("Garmin activity-average power.", "watts", "0–1500 W", "Optional; running-power availability is watch/sensor dependent."),
        "maxPower": ("Garmin maximum activity power.", "watts", "0–1500 W validation range", "Optional and watch/sensor dependent; current data contain values above 1500 W that should be treated as potential spikes/outliers."),
        "normPower": ("Garmin normalized power estimate.", "watts", "0–1500 W", "Primarily a cycling construct; sparse values in a running-filtered table require cautious interpretation."),
        "max20MinPower": ("Highest Garmin-reported 20-minute average power.", "watts", "0–1500 W", "Optional and device/sport dependent."),
        "maxFtp": ("Garmin-reported functional threshold power.", "watts", "0–1500 W", "Optional; may reflect cycling context rather than the run itself."),
        "calories": ("Garmin estimated activity energy expenditure.", "kilocalories", "≥0", "Device/model-derived estimate, not direct calorimetry."),
        "bmrCalories": ("Garmin basal-metabolic calories allocated to the activity period.", "kilocalories", "≥0", "Method is proprietary; do not equate with active calories."),
        "caloriesConsumed": ("Calories recorded as consumed during the activity.", "kilocalories", "≥0", "Often user-entered or absent."),
        "steps": ("Garmin step count associated with the activity.", "steps", "≥0 integer", "Device dependent and not interchangeable with cadence."),
        "pr": ("Garmin personal-record indicator/count attached to the activity.", "flag/count", "≥0", "Exact encoding requires manual review; daily master sums this field."),
        "activityTrainingLoad": ("Garmin activity training-load estimate.", "Garmin load units", "≥0", "Proprietary EPOC-derived value; device dependent."),
        "activityTrainingLoadSrvrCalc": ("Server-calculated Garmin activity training load.", "Garmin load units", "≥0", "Sparse alternative to device-calculated training load."),
        "aerobicTrainingEffect": ("Garmin aerobic Training Effect score.", "score", "0–5", "Proprietary estimate of aerobic training stimulus."),
        "anaerobicTrainingEffect": ("Garmin anaerobic Training Effect score.", "score", "0–5", "Proprietary estimate of anaerobic training stimulus."),
        "trainingEffectLabel": ("Garmin categorical Training Effect label.", "category", "Garmin-defined values", "Interpret alongside aerobic/anaerobic Training Effect."),
        "trainingEffectLabelSrvrCalc": ("Server-calculated Garmin Training Effect label.", "category", "Garmin-defined values", "May differ from device-calculated labeling."),
        "score": ("Garmin Training Readiness score.", "score", "0–100", "Multiple snapshots per date are valid."),
        "level": ("Garmin categorical Training Readiness level.", "category", "Garmin-defined values", "Interpret with score; category thresholds are Garmin-defined."),
        "acuteLoad": ("Acute training load used by Garmin Training Readiness.", "Garmin load units", "≥0", "Proprietary rolling-load estimate."),
        "recoveryTime": ("Garmin estimated remaining recovery time.", "minutes", "≥0", "Unit is inferred from Garmin readiness schema conventions; manual confirmation recommended."),
        "hrvWeeklyAverage": ("Garmin rolling weekly average heart-rate variability.", "milliseconds", "≥0", "HRV method and valid-night requirements are Garmin-defined."),
        "sleepScore": ("Garmin sleep score contributing to readiness.", "score", "0–100", "Optional; watch-model and valid-sleep dependent."),
        "validSleep": ("Whether Garmin considered the sleep input valid for readiness.", "boolean", "True/False", "Quality/eligibility flag, not a sleep outcome."),
        "acwrPercent": ("Garmin acute-to-chronic workload status expressed as a percentage.", "percent", "≥0%", "Proprietary workload windows; do not assume a simple 7-day/28-day formula."),
        "dailyAcuteChronicWorkloadRatio": ("Garmin daily acute-to-chronic workload ratio.", "ratio", "≥0", "Proprietary calculation and windows."),
        "dailyTrainingLoadAcute": ("Garmin acute training-load estimate for the date.", "Garmin load units", "≥0", "Optional and dependent on compatible device history."),
        "dailyTrainingLoadChronic": ("Garmin chronic training-load estimate for the date.", "Garmin load units", "≥0", "Optional and dependent on sufficient history."),
        "acwrStatus": ("Garmin categorical acute/chronic workload status.", "category", "Garmin-defined values", "Interpret jointly with ACWR measures."),
        "acwrStatusFeedback": ("Garmin explanatory text for acute/chronic workload status.", "text", "Garmin-defined phrases", "Presentation text rather than an independent quantitative measure."),
        "trainingStatus": ("Garmin training-status category.", "category", "Garmin-defined values", "Proprietary classification; multiple snapshots may occur per date."),
        "fitnessLevelTrend": ("Garmin categorical trend in estimated fitness level.", "category", "Garmin-defined values", "Daily master retains the last snapshot."),
        "loadLevelTrend": ("Garmin categorical trend in training-load level.", "category", "Garmin-defined values", "Optional in newer export schemas."),
        "loadTunnelMin": ("Garmin lower boundary of the suggested training-load range.", "Garmin load units", "≥0", "Daily master takes the minimum same-day value."),
        "loadTunnelMax": ("Garmin upper boundary of the suggested training-load range.", "Garmin load units", "≥0", "Daily master takes the maximum same-day value."),
        "weeklyTrainingLoadSum": ("Garmin rolling weekly training-load sum.", "Garmin load units", "≥0", "Proprietary load calculation."),
        "calibratedData": ("Indicator/value showing whether Garmin MaxMet data is calibrated.", "flag or code", "Unknown", "Encoding is not defined in the repository; manual review required."),
        "analyzerMethod": ("Garmin code identifying the physiological-analysis method.", "code", "Unknown", "Proprietary code; manual review required."),
        "maxMetCategory": ("Garmin category associated with the MaxMet estimate.", "category", "Garmin-defined values", "Category thresholds are not defined in the repository."),
        "fitnessAgeDescription": ("Garmin descriptive text accompanying fitness age.", "text/category", "Garmin-defined values", "Optional and export-generation dependent."),
        "primaryTrainingDevice": ("Whether/which device Garmin treated as the primary training device for the projection.", "flag/category", "Unknown", "Exact encoding requires manual review."),
        "sportingEventId": ("Garmin numeric identifier for the projected sporting event.", "identifier", "Positive integer when present", "Event metadata, not a performance measure."),
        "sportingEventUuid": ("Garmin UUID for the projected sporting event.", "UUID", "UUID-form text", "Event metadata, not a performance measure."),
        "currentPredictedRaceTime": ("Garmin current race-time projection in event projection records.", "seconds", ">0", "Event-specific field; do not mix across distances without event context."),
        "lowerBoundProjectionRaceTime": ("Lower bound of Garmin's projected race-time interval.", "seconds", ">0", "Only present in event projection schema."),
        "midpointProjectionRaceTime": ("Midpoint of Garmin's projected race-time interval.", "seconds", ">0", "Only present in event projection schema."),
        "upperBoundProjectionRaceTime": ("Upper bound of Garmin's projected race-time interval.", "seconds", ">0", "Only present in event projection schema."),
        "altitudeAcclimation": ("Garmin estimated altitude to which the athlete is acclimated.", "metres", "≥0", "Optional proprietary estimate; not the athlete's current elevation."),
        "previousAltitudeAcclimation": ("Previous Garmin altitude-acclimation estimate.", "metres", "≥0", "Use with its timestamp to study change."),
        "currentAltitude": ("Garmin-reported current altitude used by acclimation logic.", "metres", "Plausible terrestrial altitude", "Context for acclimation, not accumulated elevation."),
        "prevAltitude": ("Previous Garmin altitude value used by acclimation logic.", "metres", "Plausible terrestrial altitude", "Context field for acclimation changes."),
        "altitudeTrend": ("Garmin categorical direction/status of altitude acclimation.", "category", "Garmin-defined values", "Proprietary category; do not impose ordinal coding without review."),
        "heatTrend": ("Garmin categorical direction/status of heat acclimation.", "category", "Garmin-defined values", "Proprietary category; do not impose ordinal coding without review."),
        "heatAcclimationPercentage": ("Garmin estimated heat-acclimation percentage.", "percent", "0–100%", "Optional and dependent on qualifying environmental/training history."),
        "previousHeatAcclimationPercentage": ("Previous Garmin heat-acclimation percentage.", "percent", "0–100%", "Use with the associated timestamp to study changes."),
        "feedbackLong": ("Long-form Garmin explanation of the Training Readiness result.", "text", "Garmin-defined phrases", "Presentation text; may duplicate information encoded by scores/factors."),
        "feedbackShort": ("Short Garmin explanation of the Training Readiness result.", "text", "Garmin-defined phrases", "Presentation text; may change across firmware/localization."),
        "recoveryTimeChangePhrase": ("Garmin text describing a change in estimated recovery time.", "text", "Garmin-defined phrases", "Presentation text, not an independent quantitative measure."),
        "inputContext": ("Garmin context payload describing readiness inputs.", "JSON/text", "Unknown", "Schema varies and is serialized for Parquet; review before use."),
        "userProfileId": ("Garmin user-profile identifier present in summarized activities.", "identifier", "Unknown", "Potentially identifying; use anonymized `athlete_id` for research joins."),
        "vO2MaxValue": ("Raw Garmin activity VO2-max estimate.", "mL/kg/min", "20–90", "Canonicalized copy may appear as `vo2max`; model-derived, not laboratory measured."),
        "lapCount": ("Number of laps in the activity.", "count", "≥0 integer", "Lap creation may be automatic or manual."),
        "moderateIntensityMinutes": ("Garmin moderate-intensity minutes credited to the activity.", "minutes", "≥0", "Intensity classification is Garmin-defined."),
        "vigorousIntensityMinutes": ("Garmin vigorous-intensity minutes credited to the activity.", "minutes", "≥0", "Garmin may weight vigorous minutes differently in weekly goals."),
        "differenceBodyBattery": ("Change in Garmin Body Battery associated with the activity.", "score points", "-100 to 100", "Proprietary estimate; sign indicates increase/decrease."),
        "floorsClimbed": ("Garmin estimated floors climbed during the activity.", "floors", "≥0", "Barometric/device dependent."),
        "floorsDescended": ("Garmin estimated floors descended during the activity.", "floors", "≥0", "Barometric/device dependent."),
        "jumpCount": ("Garmin count of detected jumps.", "count", "≥0 integer", "Sport/device-specific and generally not relevant to running research."),
        "strokes": ("Garmin count of detected strokes.", "count", "≥0 integer", "Sport-specific passthrough; sparse in running-filtered data."),
        "activeLengths": ("Number of active pool lengths detected by Garmin.", "count", "≥0 integer", "Swimming-specific passthrough; sparse in running-filtered data."),
        "poolLengthYard": ("Pool length represented in yards.", "yards", "≥0", "Swimming-specific passthrough."),
        "waterConsumed": ("Water intake recorded for the activity.", "millilitres", "≥0", "May be user-entered and is frequently absent."),
        "waterEstimated": ("Garmin estimated sweat/fluid loss for the activity.", "millilitres", "≥0", "Model-derived estimate; environment and device inputs affect accuracy."),
        "lactateThresholdBpm": ("Garmin estimated lactate-threshold heart rate.", "bpm", "20–250 bpm", "Model-derived; may be carried from athlete profile rather than measured in the activity."),
        "lactateThresholdSpeed": ("Garmin estimated lactate-threshold speed in raw summarized-export scaling.", "0.1 metres/second", "≥0", "Not converted by the pipeline; values appear profile-derived and sparse."),
        "minElevation": ("Minimum Garmin activity elevation in raw summarized-export scaling.", "centimetres", "Plausible terrestrial elevation", "Not converted by the current pipeline; use engineered metre fields where available."),
        "maxElevation": ("Maximum Garmin activity elevation in raw summarized-export scaling.", "centimetres", "Plausible terrestrial elevation", "Not converted by the current pipeline; raw values may reflect device/elevation correction."),
        "poolLength": ("Garmin pool length in raw summarized-export scaling.", "centimetres", "≥0", "Swimming-specific passthrough; sparse in the running-filtered dataset."),
        "perceivedWorkoutEffort": ("Recorded perceived workout effort.", "score", "Unknown", "Scale is not established in this repository; confirm before analysis."),
        "rawGNSSDataStatusId": ("Garmin code describing raw GNSS data status.", "code", "Unknown", "Proprietary code; manual mapping required."),
    }
    if column_name in exact:
        description, unit, expected, note = exact[column_name]
        return description, variable_type, unit, expected, note, lineage

    if column_name.startswith("race_time_"):
        distance = column_name.removeprefix("race_time_").replace("_", " ")
        return (f"Garmin predicted {distance} finish duration.", "Canonical / Renamed", "seconds", ">0", "Last prediction snapshot per date is retained.", f"raceTime* → {column_name}")
    if "Timestamp" in column_name or lower.endswith("timestamp"):
        return (f"Garmin timestamp for {column_name.replace('Timestamp', '').replace('_', ' ').strip()}.", variable_type, "datetime", "Valid timestamp", "Epoch seconds/milliseconds are coerced by magnitude; timezone semantics may vary.", lineage)
    if "Latitude" in column_name:
        return (f"Garmin {column_name.replace('Latitude', '').lower() or 'activity'} latitude.", variable_type, "decimal degrees", "-90 to 90", "Potentially identifying location data; use only under the study privacy protocol.", lineage)
    if "Longitude" in column_name:
        return (f"Garmin {column_name.replace('Longitude', '').lower() or 'activity'} longitude.", variable_type, "decimal degrees", "-180 to 180", "Potentially identifying location data; use only under the study privacy protocol.", lineage)
    if lower.endswith("percentage") or lower.endswith("percent"):
        label = column_name.replace("Percentage", "").replace("Percent", "")
        if "Factor" in column_name:
            return (
                f"Garmin percentage contribution/status for the {label} Training Readiness factor.",
                variable_type,
                "percent",
                "0–100%",
                "Component of Garmin's proprietary readiness calculation; do not sum factors unless validated.",
                lineage,
            )
        return (f"Garmin percentage measure for {label}.", variable_type, "percent", "0–100%", "Optional Garmin metric; precise proprietary calculation may require manual review.", lineage)
    if lower.endswith("feedback") or "feedbackphrase" in lower:
        return (f"Garmin explanatory feedback associated with {column_name}.", variable_type, "text", "Garmin-defined phrases", "Presentation text; avoid treating categories as ordinal without validation.", lineage)
    if lower.startswith("hrtimeinzone_") or lower.startswith("powertimeinzone_"):
        zone = column_name.rsplit("_", 1)[-1]
        domain = "heart-rate" if lower.startswith("hr") else "power"
        return (f"Time accumulated in Garmin {domain} zone {zone}.", variable_type, "milliseconds", "≥0", "Zone boundaries are athlete/device settings; compare across athletes cautiously.", lineage)
    if "Cadence" in column_name:
        return (f"Garmin {column_name.replace('Cadence', '').lower()} cadence measure.", variable_type, "repetitions per minute", "0–300", "Cadence convention varies by sport and single/double cadence field.", lineage)
    if "Stress" in column_name:
        return (f"Garmin stress-related measure: {column_name}.", variable_type, "score", "0–100 when a stress score", "Exact context may be activity start/end/average; proprietary estimate.", lineage)
    if column_name in {"splits", "splitSummaries", "summarizedDiveInfo"}:
        return (f"Nested Garmin {column_name} payload serialized to JSON for Parquet.", variable_type, "JSON", "Unknown", "Not normalized by the production pipeline; manual schema review required before analysis.", lineage)
    if lower.endswith("count"):
        return (f"Garmin count represented by `{column_name}`.", variable_type, "count", "≥0 integer", "Event-detection rules are device and sport dependent.", lineage)
    return (
        f"Garmin field `{column_name}`; semantic definition is not established in the repository.",
        variable_type,
        "Unknown",
        "Unknown",
        "Manual review required before analytical use.",
        lineage,
    )


def field_metadata(dataset_name, column_name):
    """Return description, class, units, range, notes, and lineage for a field."""
    if dataset_name == "daily_master" and column_name in DAILY_LINEAGE:
        description, _, unit, expected, note, _ = (
            FIELD_OVERRIDES.get(column_name)
            or _raw_field_metadata(DAILY_LINEAGE[column_name].split(".")[-1].split(" ")[0])
        )
        return description, "Aggregated", unit, expected, note, DAILY_LINEAGE[column_name]
    if column_name in FIELD_OVERRIDES:
        return FIELD_OVERRIDES[column_name]
    engineered = {
        "distance_km": ("Activity distance converted from Garmin's scaled distance.", "Unit Converted", "kilometres", "≥0", "Running activities only.", "distance ÷ 100000 → distance_km"),
        "distance_miles": ("Activity distance converted from Garmin's scaled distance.", "Unit Converted", "miles", "≥0", "Running activities only.", "distance ÷ 160934.4 → distance_miles"),
        "duration_minutes": ("Activity duration converted from milliseconds.", "Unit Converted", "minutes", "≥0", "Includes stopped time represented in Garmin duration.", "duration ÷ 60000 → duration_minutes"),
        "elapsed_duration_minutes": ("Elapsed activity duration converted from milliseconds.", "Unit Converted", "minutes", "≥0", "Can exceed moving time.", "elapsedDuration ÷ 60000 → elapsed_duration_minutes"),
        "moving_duration_minutes": ("Garmin moving duration converted from milliseconds.", "Unit Converted", "minutes", "≥0", "Movement detection is Garmin/device dependent.", "movingDuration ÷ 60000 → moving_duration_minutes"),
        "elevation_gain_m": ("Activity elevation gain converted from centimetres.", "Unit Converted", "metres", "≥0", "Elevation correction/source may vary by activity.", "elevationGain ÷ 100 → elevation_gain_m"),
        "elevation_loss_m": ("Activity elevation loss converted from centimetres.", "Unit Converted", "metres", "≥0", "Elevation correction/source may vary by activity.", "elevationLoss ÷ 100 → elevation_loss_m"),
        "avg_speed_mps": ("Activity-average speed converted from Garmin's scaled value.", "Unit Converted", "metres/second", "≥0", "Used to derive pace fields.", "avgSpeed × 10 → avg_speed_mps"),
        "max_speed_mps": ("Activity maximum speed converted from Garmin's scaled value.", "Unit Converted", "metres/second", "≥0", "Short GPS spikes can inflate maximum speed.", "maxSpeed × 10 → max_speed_mps"),
        "avg_stride_length_m": ("Average stride length converted from centimetres.", "Unit Converted", "metres", "≥0", "Device dependent.", "avgStrideLength ÷ 100 → avg_stride_length_m"),
        "avg_pace_mile": ("Activity-average running pace derived from average speed.", "Derived", "M:SS per mile", ">0", "Null for zero/missing speed.", "avg_speed_mps → pace per mile"),
        "avg_pace_km": ("Activity-average running pace derived from average speed.", "Derived", "M:SS per kilometre", ">0", "Null for zero/missing speed.", "avg_speed_mps → pace per kilometre"),
        "max_pace_mile": ("Pace corresponding to Garmin maximum speed.", "Derived", "M:SS per mile", ">0", "Represents peak-speed pace, not sustainable pace.", "max_speed_mps → pace per mile"),
        "max_pace_km": ("Pace corresponding to Garmin maximum speed.", "Derived", "M:SS per kilometre", ">0", "Represents peak-speed pace, not sustainable pace.", "max_speed_mps → pace per kilometre"),
    }
    if column_name in engineered:
        return engineered[column_name]
    if column_name.endswith("_minutes") and (
        column_name.startswith("hrTimeInZone_")
        or column_name.startswith("powerTimeInZone_")
    ):
        raw_name = column_name.removesuffix("_minutes")
        domain = "heart-rate" if raw_name.startswith("hr") else "power"
        zone = raw_name.rsplit("_", 1)[-1]
        return (
            f"Time in Garmin {domain} zone {zone}, converted from milliseconds.",
            "Unit Converted",
            "minutes",
            "≥0",
            "Zone boundaries are athlete/device settings; compare across athletes cautiously.",
            f"{raw_name} ÷ 60000 → {column_name}",
        )
    if dataset_name == "daily_master":
        description, _, unit, expected, note, lineage = _raw_field_metadata(column_name)
        return description, "Aggregated", unit, expected, note, lineage
    return _raw_field_metadata(column_name)


def collect_schema(processed_root: Path):
    """Collect aggregate column metadata from per-athlete Parquet datasets.

    Args:
        processed_root (pathlib.Path): Root containing athlete output
            directories.

    Returns:
        dict[str, dict[str, dict]]: Dataset-to-column inventory. Each column
        records observed dtypes, number of athlete files containing it, total
        rows, non-null rows, and athlete IDs containing the column.

    Raises:
        FileNotFoundError: If ``processed_root`` does not exist.
        Exception: Parquet decoding errors propagate so incomplete dictionaries
            cannot be mistaken for successful documentation.

    Notes:
        Values are counted but never copied into the result, keeping the
        dictionary safe to publish without leaking source data.
    """
    processed_root = Path(processed_root)
    if not processed_root.exists():
        raise FileNotFoundError(processed_root)

    inventory = defaultdict(
        lambda: defaultdict(
            lambda: {
                "dtypes": set(),
                "files_present": 0,
                "rows": 0,
                "non_null_rows": 0,
                "athletes": set(),
            }
        )
    )
    dataset_stats = defaultdict(
        lambda: {
            "files": 0,
            "rows": 0,
            "athletes": set(),
            "key_duplicates": 0,
            "key_checked": False,
        }
    )
    athlete_directories = sorted(
        path for path in processed_root.iterdir() if path.is_dir()
    )

    for athlete_dir in athlete_directories:
        for parquet_path in sorted(athlete_dir.glob("*.parquet")):
            dataset_name = parquet_path.stem
            frame = pd.read_parquet(parquet_path)
            summary = dataset_stats[dataset_name]
            summary["files"] += 1
            summary["rows"] += len(frame)
            summary["athletes"].add(athlete_dir.name)
            if {"athlete_id", "date"}.issubset(frame.columns) and dataset_name in {
                "metrics",
                "predictions",
                "daily_master",
            }:
                summary["key_checked"] = True
                summary["key_duplicates"] += int(
                    frame.duplicated(["athlete_id", "date"]).sum()
                )
            elif {"athlete_id", "activity_id"}.issubset(frame.columns) and dataset_name == "runs":
                summary["key_checked"] = True
                summary["key_duplicates"] += int(
                    frame.duplicated(["athlete_id", "activity_id"]).sum()
                )
            for column_name in frame.columns:
                stats = inventory[dataset_name][column_name]
                stats["dtypes"].add(str(frame[column_name].dtype))
                stats["files_present"] += 1
                stats["rows"] += len(frame)
                stats["non_null_rows"] += int(frame[column_name].notna().sum())
                stats["athletes"].add(athlete_dir.name)

    result = {}
    for dataset, columns in inventory.items():
        result[dataset] = {
            "__dataset__": {
                **dataset_stats[dataset],
                "athletes": sorted(dataset_stats[dataset]["athletes"]),
                "total_athletes": len(athlete_directories),
            }
        }
        result[dataset].update({
            column: {
                **stats,
                "dtypes": sorted(stats["dtypes"]),
                "athletes": sorted(stats["athletes"]),
            }
            for column, stats in columns.items()
        })
    return result


def render_markdown(inventory):
    """Render collected schema metadata as a Markdown data dictionary.

    Args:
        inventory (Mapping): Result from :func:`collect_schema`.

    Returns:
        str: Markdown document with dataset and column tables.
    """
    lines = [
        "# Garmin pipeline data dictionary",
        "",
        "This reference combines production parser logic with the schemas of the "
        "currently persisted athlete datasets. It documents lineage and "
        "interpretation without exposing sample values or participant identity.",
        "",
        "> **Scope and caution:** Garmin physiological, load, readiness, and "
        "training-status variables are device/model-derived estimates. They are "
        "not clinical measurements, and Garmin may change proprietary algorithms "
        "across devices or firmware. `Unknown` means the repository does not "
        "support a more specific claim.",
        "",
        "## Production data flow",
        "",
        "```mermaid",
        "flowchart TD",
        "    A[Garmin account export ZIP] --> B[Manually extracted athlete directory]",
        "    B --> C[Recursive JSON discovery]",
        "    C --> D{Filename and content classification}",
        "    D --> E[Activities parser]",
        "    D --> F[Metrics parser]",
        "    D --> G[Race predictions parser]",
        "    D --> H[Readiness parser]",
        "    D --> I[MaxMet / VO2-max parser]",
        "    D --> J[Training history parser]",
        "    D --> U[Unmatched private diagnostics]",
        "    E --> K[runs.parquet]",
        "    F --> L[metrics.parquet]",
        "    G --> M[predictions.parquet]",
        "    H --> N[readiness.parquet]",
        "    I --> O[maxmet.parquet]",
        "    J --> P[history.parquet]",
        "    K --> Q[Complete athlete calendar + daily aggregation]",
        "    L --> Q",
        "    M --> Q",
        "    N --> Q",
        "    O --> Q",
        "    P --> Q",
        "    Q --> R[daily_master.parquet]",
        "    R --> S[all_athletes_daily_master.parquet]",
        "    S --> T[Statistical analysis / ML feature development]",
        "```",
        "",
        "## Dataset grain and missing values",
        "",
        "- `runs` is activity-grained; `readiness`, `maxmet`, and `history` may "
        "contain multiple snapshots per date.",
        "- `metrics` and `predictions` are reduced to one record per date.",
        "- `daily_master` is unique on (`athlete_id`, `date`) and includes rest days.",
        "- Optional device metrics remain null; daily running totals are zero on rest days.",
        "- `athlete_id` is the research join key. Garmin `user_id`, device IDs, "
        "source filenames, and free-text/location fields should not be used to "
        "link participants.",
        "",
        "## Variable classification",
        "",
        "| Variable Type | Meaning |",
        "|---|---|",
        "| Raw Garmin | Value retained from a Garmin JSON field without value conversion. |",
        "| Canonical / Renamed | Garmin value retained but renamed to the pipeline schema. |",
        "| Unit Converted | Garmin numeric value converted to a documented unit. |",
        "| Aggregated | Multiple source rows summarized to the output grain. |",
        "| Engineered | New feature constructed from one or more fields. |",
        "| Derived | Deterministic representation derived from another field. |",
        "| Metadata | Pipeline provenance, identity-safe keys, or processing context. |",
        "",
        "## Canonical Garmin field mapping",
        "",
        "These aliases are applied by the parsers from "
        "`src/schema/field_mappings.json`. Unmapped Garmin fields retain their "
        "source names.",
        "",
        "| Original Garmin field | Canonical pipeline field |",
        "|---|---|",
    ]
    for raw_name, canonical_name in RAW_CANONICAL_MAP.items():
        lines.append(f"| `{raw_name}` | `{canonical_name}` |")
    lines.append("")

    for dataset_name in sorted(inventory):
        columns = {
            name: stats
            for name, stats in inventory[dataset_name].items()
            if name != "__dataset__"
        }
        summary = inventory[dataset_name]["__dataset__"]
        dataset_metadata = DATASET_METADATA.get(dataset_name, {})
        dataset_coverage = (
            summary["files"] / summary["total_athletes"]
            if summary["total_athletes"]
            else 0.0
        )
        lines.extend([
            f"## `{dataset_name}`",
            "",
            dataset_metadata.get("purpose", "Persisted pipeline dataset."),
            "",
            "| Dataset property | Value |",
            "|---|---|",
            f"| Grain | {dataset_metadata.get('grain', 'Unknown')} |",
            f"| Primary key | {dataset_metadata.get('primary_key', 'Unknown')} |",
            f"| Rows | {summary['rows']:,} |",
            f"| Athlete coverage | {summary['files']}/{summary['total_athletes']} ({dataset_coverage:.1%}) |",
            "| Key duplicates observed | "
            + (
                f"{summary['key_duplicates']:,}"
                if summary["key_checked"]
                else "Not applicable: dataset intentionally permits multiple snapshots per date"
            )
            + " |",
            f"| Duplicate handling | {dataset_metadata.get('duplicate_handling', 'Unknown')} |",
            f"| Merge strategy | {dataset_metadata.get('merge_strategy', 'Unknown')} |",
            f"| Update frequency | {dataset_metadata.get('update_frequency', 'Unknown')} |",
            f"| Upstream lineage | {dataset_metadata.get('upstream', 'Unknown')} |",
            f"| Downstream dependencies | {dataset_metadata.get('downstream', 'Unknown')} |",
            "",
            "| Variable | Original Garmin field / lineage | Variable Type | Data type(s) | Units | Expected range | Missing | Athlete coverage | Required | Description | Research Notes |",
            "|---|---|---|---|---|---|---:|---:|---|---|---|",
        ])
        for column_name in sorted(columns):
            stats = columns[column_name]
            non_null_coverage = (
                stats["non_null_rows"] / stats["rows"] if stats["rows"] else 0.0
            )
            athlete_coverage = (
                stats["files_present"] / summary["total_athletes"]
                if summary["total_athletes"]
                else 0.0
            )
            description, variable_type, units, expected, notes, lineage = (
                field_metadata(dataset_name, column_name)
            )
            required = (
                "Required"
                if column_name in DATASET_REQUIRED_COLUMNS.get(dataset_name, set())
                else "Optional"
            )
            nullable = stats["non_null_rows"] < stats["rows"]
            if nullable:
                required = f"{required}; nullable"
            watch_note = (
                " Watch/export dependent."
                if stats["files_present"] < summary["total_athletes"]
                else ""
            )
            notes = f"{notes}{watch_note}"
            cells = [
                f"`{column_name}`",
                lineage,
                variable_type,
                ", ".join(stats["dtypes"]),
                units,
                expected,
                f"{1 - non_null_coverage:.1%}",
                f"{stats['files_present']}/{summary['total_athletes']} ({athlete_coverage:.1%})",
                required,
                description,
                notes,
            ]
            cells = [str(cell).replace("|", "\\|").replace("\n", " ") for cell in cells]
            lines.append(
                "| " + " | ".join(cells) + " |"
            )
        lines.append("")

    manual_review = []
    for dataset_name, dataset in inventory.items():
        for column_name in dataset:
            if column_name == "__dataset__":
                continue
            metadata = field_metadata(dataset_name, column_name)
            if "manual review" in metadata[4].lower():
                manual_review.append(f"`{dataset_name}.{column_name}`")
    lines.extend([
        "## Fields requiring manual semantic review",
        "",
        "The following fields are retained by production parsing but cannot be "
        "defined completely from repository logic alone. One or more semantics, "
        "units, encodings, or expected ranges remain uncertain; consult an "
        "authoritative Garmin schema before using them analytically:",
        "",
        ", ".join(manual_review) if manual_review else "None.",
        "",
    ])

    return "\n".join(lines)


def generate_data_dictionary(processed_root: Path, output_path: Path):
    """Generate and write the production Markdown data dictionary.

    Args:
        processed_root (pathlib.Path): Root containing per-athlete outputs.
        output_path (pathlib.Path): Markdown destination.

    Returns:
        pathlib.Path: Written output path.

    Side Effects:
        Creates the destination parent directory and writes UTF-8 Markdown.
    """
    inventory = collect_schema(processed_root)
    document = render_markdown(inventory)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")
    return output_path


def main():
    """Generate a data dictionary from command-line arguments.

    Side Effects:
        Writes the requested Markdown file and prints its path.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--processed-root",
        type=Path,
        default=Path("data_processed/athletes"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/data_dictionary.md"),
    )
    args = parser.parse_args()
    output_path = generate_data_dictionary(args.processed_root, args.output)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
