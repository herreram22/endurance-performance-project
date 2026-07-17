import pandas as pd

from src.table_builders import build_multi_athlete_daily_master
from src.tools.daily_master_quality import validate_daily_master


def test_validate_daily_master(tmp_path):
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02"],
        "athlete_id": ["athlete_001", "athlete_001"],
        "total_distance_km": [5.0, 6.1],
        "total_duration_minutes": [30, 35],
    })
    path = tmp_path / "daily_master.parquet"
    df.to_parquet(path, index=False)

    result = validate_daily_master(path)
    assert result["missing_columns"] == []
    assert result["bad_1970_dates"] == 0
    assert result["null_dates"] == 0
    assert result["athlete_id_values"] == ["athlete_001"]
    assert result["coverage_status"] == "partial"
    assert result["feature_coverage"] == 0.0


def test_build_multi_athlete_daily_master_stacks_and_marks_missing_features():
    athlete_001 = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02"],
        "athlete_id": ["athlete_001", "athlete_001"],
        "total_distance_km": [5.0, 6.1],
        "total_duration_minutes": [30, 35],
        "readiness_score_last": [80.0, 82.0],
    })
    athlete_002 = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02"],
        "athlete_id": ["athlete_002", "athlete_002"],
        "total_distance_km": [4.0, 3.8],
        "total_duration_minutes": [28, 31],
    })

    combined = build_multi_athlete_daily_master([athlete_001, athlete_002])

    assert list(combined.columns) == [
        "date",
        "athlete_id",
        "total_distance_km",
        "total_duration_minutes",
        "readiness_score_last",
        "readiness_available",
    ]
    assert combined.loc[combined["athlete_id"] == "athlete_001", "readiness_available"].all()
    assert combined.loc[combined["athlete_id"] == "athlete_002", "readiness_available"].eq(False).all()
    assert combined["readiness_score_last"].isna().sum() == 2


def test_validate_daily_master_reports_partial_coverage_when_readiness_is_missing(tmp_path):
    df = pd.DataFrame({
        "date": ["2024-01-01", "2024-01-02"],
        "athlete_id": ["athlete_002", "athlete_002"],
        "total_distance_km": [4.0, 3.8],
        "total_duration_minutes": [28, 31],
    })
    path = tmp_path / "daily_master.parquet"
    df.to_parquet(path, index=False)

    result = validate_daily_master(path)
    assert result["coverage_status"] == "partial"
    assert result["feature_coverage"] < 1.0
