import pandas as pd
from pathlib import Path

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
