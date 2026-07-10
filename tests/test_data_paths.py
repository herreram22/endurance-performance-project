from src.load_data import load_block_summary


def test_load_block_summary_reads_dashboard_analytics_data():
    df = load_block_summary()

    assert not df.empty
    assert "race_date" in df.columns
    assert "stable_date" in df.columns
