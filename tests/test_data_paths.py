from pathlib import Path

from src import load_data
from src.load_data import load_block_summary


def test_load_block_summary_reads_dashboard_analytics_data():
    df = load_block_summary()

    assert not df.empty
    assert "race_date" in df.columns
    assert "stable_date" in df.columns


def test_resolve_data_path_finds_nested_analytics_file(tmp_path, monkeypatch):
    nested_dir = tmp_path / "data_processed" / "pablo_dashboard_analytics"
    nested_dir.mkdir(parents=True)
    target_file = nested_dir / "daily_master_v1.parquet"
    target_file.write_bytes(b"placeholder")

    monkeypatch.setattr(load_data, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(load_data, "DATA_DIR", tmp_path / "data_processed")
    monkeypatch.setattr(load_data, "RAW_DIR", tmp_path / "data_raw")
    monkeypatch.setattr(load_data, "ANALYTICS_DATA_DIR", nested_dir)

    resolved = load_data._resolve_data_path("daily_master_v1.parquet")

    assert resolved == target_file
