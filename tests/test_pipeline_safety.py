import pandas as pd
import pytest
import json

from src.discover_paths import explore_files
from src.parsing import parse_activities_file, parse_metrics
from src.pipeline import refresh_all_athletes_daily_master
from src.save_output import save_outputs
from src.table_builders import build_daily_master_table
from src.helpers import parse_garmin_date


def _minimal_runs(athlete_id="athlete_001"):
    return pd.DataFrame({
        "athlete_id": [athlete_id],
        "date": pd.to_datetime(["2024-01-01"]),
        "activity_id": [123],
        "distance_km": [5.0],
        "distance_miles": [3.1],
        "duration_minutes": [30.0],
        "moving_duration_minutes": [29.0],
        "elevation_gain_m": [20.0],
        "avg_speed_mps": [2.8],
    })


def test_parse_garmin_numeric_yyyymmdd():
    result = parse_garmin_date(pd.Series([20240620, 20240621]))
    assert result.tolist() == [pd.Timestamp("2024-06-20"), pd.Timestamp("2024-06-21")]


def test_discovery_keeps_profile_biometrics_and_health_status_unmatched(tmp_path):
    profile = tmp_path / "123_userBioMetrics.json"
    health = tmp_path / "2026-01-01_123_healthStatusData.json"
    acute = tmp_path / "MetricsAcuteTrainingLoad_20260101_20260102_123.json"
    profile.write_text(json.dumps({"weight": 70000}))
    health.write_text(json.dumps([{"calendarDate": "2026-01-01", "metrics": []}]))
    acute.write_text(json.dumps([{
        "calendarDate": "2026-01-01",
        "dailyTrainingLoadAcute": 100,
    }]))

    found = explore_files(tmp_path)

    assert found["metrics"] == [acute]
    assert set(found["unmatched"]) == {health, profile}


def test_metrics_parser_safely_rejects_records_without_dates(tmp_path):
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps([{"weight": 70000}]))

    result = parse_metrics([profile], "athlete_001")

    assert result.empty


def test_activity_source_filename_redacts_embedded_email(tmp_path):
    source = tmp_path / "private@example.com_0_summarizedActivities.json"
    source.write_text(json.dumps({
        "summarizedActivitiesExport": [{"activityType": "running"}]
    }))

    result = parse_activities_file(source, "athlete_001")

    assert result.loc[0, "source_file"] == "[redacted-email]_0_summarizedActivities.json"
    assert "private@example.com" not in result.to_string()


def test_save_outputs_rejects_path_traversal_athlete_id(tmp_path):
    with pytest.raises(ValueError, match="athlete_id"):
        save_outputs("../outside", {"runs": _minimal_runs()}, tmp_path)

    assert not (tmp_path.parent / "outside").exists()


def test_save_outputs_rejects_cross_athlete_rows(tmp_path):
    with pytest.raises(ValueError, match="unexpected athlete IDs"):
        save_outputs(
            "athlete_001",
            {"runs": _minimal_runs("athlete_002")},
            tmp_path,
        )


def test_save_outputs_writes_validated_data_and_leaves_no_temp_files(tmp_path):
    metadata = save_outputs(
        "athlete_001", {"runs": _minimal_runs()}, tmp_path
    )

    athlete_dir = tmp_path / "athlete_001"
    assert (athlete_dir / "runs.parquet").exists()
    assert (athlete_dir / "metadata.json").exists()
    assert metadata["datasets"]["runs"]["rows"] == 1
    assert not list(athlete_dir.glob("*.tmp"))
    assert not list(athlete_dir.glob(".*.tmp"))


def test_daily_master_includes_rest_days_with_recovery_data():
    runs = _minimal_runs()
    readiness = pd.DataFrame({
        "athlete_id": ["athlete_001"],
        "date": pd.to_datetime(["2024-01-03"]),
        "timestamp": pd.to_datetime(["2024-01-03 08:00:00"]),
        "score": [75.0],
        "level": ["HIGH"],
        "recoveryTime": [0],
        "acuteLoad": [300.0],
        "hrvWeeklyAverage": [50.0],
        "sleepScore": [85.0],
        "validSleep": [True],
    })

    result = build_daily_master_table(
        athlete_id="athlete_001",
        runs=runs,
        metrics=pd.DataFrame(),
        predictions=pd.DataFrame(),
        readiness=readiness,
        maxmet=pd.DataFrame(),
        history=pd.DataFrame(),
    )

    assert result["date"].tolist() == list(pd.date_range("2024-01-01", "2024-01-03"))
    rest_day = result.loc[result["date"] == pd.Timestamp("2024-01-03")].iloc[0]
    assert rest_day["total_distance_km"] == 0
    assert rest_day["readiness_score_last"] == 75.0
    assert result["athlete_id"].eq("athlete_001").all()


def test_refresh_all_athletes_daily_master_persists_combined_panel(tmp_path):
    for athlete_id, distance in (("athlete_001", 5.0), ("athlete_002", 7.0)):
        athlete_dir = tmp_path / athlete_id
        athlete_dir.mkdir()
        pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01"]),
            "athlete_id": [athlete_id],
            "total_distance_km": [distance],
            "total_duration_minutes": [30.0],
        }).to_parquet(athlete_dir / "daily_master.parquet", index=False)

    combined = refresh_all_athletes_daily_master(tmp_path)
    persisted = pd.read_parquet(tmp_path / "all_athletes_daily_master.parquet")

    assert len(combined) == 2
    assert persisted["athlete_id"].tolist() == ["athlete_001", "athlete_002"]
    assert not persisted.duplicated(["athlete_id", "date"]).any()
    assert (tmp_path / "all_athletes_daily_master.metadata.json").exists()


def test_refresh_all_athletes_rejects_misfiled_athlete_data(tmp_path):
    athlete_dir = tmp_path / "athlete_001"
    athlete_dir.mkdir()
    pd.DataFrame({
        "date": pd.to_datetime(["2024-01-01"]),
        "athlete_id": ["athlete_002"],
        "total_distance_km": [5.0],
        "total_duration_minutes": [30.0],
    }).to_parquet(athlete_dir / "daily_master.parquet", index=False)

    with pytest.raises(ValueError, match="expected athlete_001"):
        refresh_all_athletes_daily_master(tmp_path)
