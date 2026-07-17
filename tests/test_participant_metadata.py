import pandas as pd

from src.tools.prepare_participant_metadata import prepare_metadata


def test_metadata_outputs_separate_email_and_normalize_explicit_units(tmp_path):
    form_path = tmp_path / "form.csv"
    pd.DataFrame([{
        "Athlete ID": "athlete_004",
        "Email Address": "private@example.com",
        "Age": "34",
        "Height": "70 in",
        "Weight": "160 lb",
        "Raced within the past three years": "Yes",
        "Most recent race time": "Marathon 3:12:34",
    }]).to_csv(form_path, index=False)
    processed = tmp_path / "processed" / "athlete_004"
    processed.mkdir(parents=True)
    (processed / "daily_master.parquet").touch()

    private, metadata, reconciliation = prepare_metadata(form_path, processed.parent)

    assert private.loc[0, "email"] == "private@example.com"
    assert "email" not in metadata.columns
    assert metadata.loc[0, "height_cm"] == 177.8
    assert round(metadata.loc[0, "weight_kg"], 3) == 72.575
    assert metadata.loc[0, "latest_race_time_seconds"] == 11554
    assert reconciliation.empty


def test_metadata_reports_missing_manual_links(tmp_path):
    form_path = tmp_path / "form.csv"
    pd.DataFrame([{"Email": "unknown@example.com"}]).to_csv(form_path, index=False)

    _, metadata, reconciliation = prepare_metadata(form_path, tmp_path / "processed")

    assert metadata.empty
    assert reconciliation["issue"].tolist() == ["form_submission_missing_athlete_id"]
