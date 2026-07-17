import pandas as pd

from src.tools.generate_data_dictionary import (
    collect_schema,
    generate_data_dictionary,
    render_markdown,
)


def test_data_dictionary_reports_schema_without_sample_values(tmp_path):
    athlete_dir = tmp_path / "processed" / "athlete_001"
    athlete_dir.mkdir(parents=True)
    pd.DataFrame({
        "athlete_id": ["athlete_001", "athlete_001"],
        "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
        "private_metric": ["secret-value", None],
    }).to_parquet(athlete_dir / "daily_master.parquet", index=False)

    inventory = collect_schema(athlete_dir.parent)
    document = render_markdown(inventory)

    assert "`daily_master`" in document
    assert "`private_metric`" in document
    assert "50.0%" in document
    assert "secret-value" not in document
    assert "Variable Type" in document
    assert "Expected range" in document
    assert "Research Notes" in document
    assert "Manual review required" in document


def test_generate_data_dictionary_writes_markdown(tmp_path):
    athlete_dir = tmp_path / "processed" / "athlete_001"
    athlete_dir.mkdir(parents=True)
    pd.DataFrame({
        "athlete_id": ["athlete_001"],
        "date": pd.to_datetime(["2024-01-01"]),
    }).to_parquet(athlete_dir / "runs.parquet", index=False)
    output_path = tmp_path / "docs" / "dictionary.md"

    result = generate_data_dictionary(athlete_dir.parent, output_path)

    assert result == output_path
    assert output_path.exists()
