"""Create private and de-identified participant metadata from a form export.

This utility is the privacy boundary between participant intake and analytical
Garmin data. It reads a Google Form CSV whose ``athlete_id`` links have been
manually verified, normalizes supported demographic/training fields, and
produces three independent outputs:

* a private email/upload lookup;
* de-identified athlete metadata keyed only by ``athlete_id``;
* a private reconciliation report for missing or unmatched links.

The tool never guesses identity from Garmin filenames or profile JSON. Height
and weight are converted only when units are explicit, ambiguous raw values are
retained, and duplicate non-null athlete IDs are rejected.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


ALIASES = {
    "timestamp": "form_submission_timestamp",
    "form_submission_timestamp": "form_submission_timestamp",
    "email_address": "email",
    "email": "email",
    "athlete_id": "athlete_id",
    "upload_filename": "upload_identifier",
    "upload_identifier": "upload_identifier",
    "age": "age",
    "sex": "sex",
    "height": "height_raw",
    "country": "country",
    "garmin_watch_model": "garmin_watch",
    "garmin_watch": "garmin_watch",
    "weight": "weight_raw",
    "years_of_endurance_training": "years_endurance_training",
    "years_endurance_training": "years_endurance_training",
    "main_sport": "main_sport",
    "typical_weekly_training_volume": "weekly_volume_raw",
    "weekly_volume": "weekly_volume_raw",
    "raced_within_the_past_three_years": "raced_past_3_years",
    "raced_past_3_years": "raced_past_3_years",
    "injury_history": "injury_history",
    "whether_the_athlete_has_experienced_injuries": "injury_history",
    "most_recent_race_time": "latest_race_time_raw",
    "latest_race_time": "latest_race_time_raw",
}

DEIDENTIFIED_COLUMNS = [
    "athlete_id", "age", "sex", "height_cm", "height_raw", "country",
    "garmin_watch", "garmin_watch_normalized", "weight_kg", "weight_raw",
    "years_endurance_training", "main_sport", "weekly_volume_raw",
    "raced_past_3_years", "injury_history", "latest_race_distance",
    "latest_race_time_seconds", "latest_race_date", "latest_race_time_raw",
]


def _canonical_name(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.strip().lower())).strip("_")


def _normalize_yes_no(value):
    if pd.isna(value):
        return pd.NA
    text = str(value).strip().lower()
    if text in {"yes", "y", "true", "1"}:
        return True
    if text in {"no", "n", "false", "0"}:
        return False
    return pd.NA


def _measurement(value, kind):
    """Return a canonical measurement only when its unit is explicit."""
    if pd.isna(value):
        return pd.NA
    text = str(value).strip().lower().replace(",", ".")
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*(cm|m|in|inch|inches|kg|lb|lbs|pounds?)\b", text)
    if not match:
        return pd.NA
    number, unit = float(match.group(1)), match.group(2)
    if kind == "height":
        if unit == "cm":
            return number
        if unit == "m":
            return number * 100
        if unit in {"in", "inch", "inches"}:
            return number * 2.54
    if kind == "weight":
        if unit == "kg":
            return number
        if unit in {"lb", "lbs", "pound", "pounds"}:
            return number * 0.45359237
    return pd.NA


def _race_seconds(value):
    if pd.isna(value):
        return pd.NA
    match = re.search(r"\b(?:(\d{1,2}):)?(\d{1,2}):(\d{2})\b", str(value))
    if not match:
        return pd.NA
    hours = int(match.group(1) or 0)
    return hours * 3600 + int(match.group(2)) * 60 + int(match.group(3))


def prepare_metadata(form_csv: Path, processed_root: Path):
    """Normalize form responses and reconcile them with processed athletes.

    Args:
        form_csv (pathlib.Path): Google Form CSV containing a manually assigned
            ``athlete_id`` column where links are known.
        processed_root (pathlib.Path): Pipeline output root used to identify
            athletes with a saved ``daily_master.parquet``.

    Returns:
        tuple[pandas.DataFrame, pandas.DataFrame, pandas.DataFrame]: Private
        participant lookup, de-identified analytical metadata, and
        reconciliation findings.

    Raises:
        ValueError: If more than one form row uses the same non-null athlete ID.
        FileNotFoundError: If the form CSV is missing.

    Notes:
        Email appears only in the first returned frame. Explicit measurement
        units are converted to centimetres/kilograms while raw fields remain
        available for ambiguous responses.
    """
    form = pd.read_csv(form_csv)
    form.columns = [ALIASES.get(_canonical_name(col), _canonical_name(col)) for col in form.columns]
    if "athlete_id" not in form:
        form["athlete_id"] = pd.NA
    form["athlete_id"] = form["athlete_id"].astype("string").str.strip().replace("", pd.NA)

    duplicate_ids = sorted(form.loc[
        form["athlete_id"].notna() & form["athlete_id"].duplicated(keep=False), "athlete_id"
    ].unique())
    if duplicate_ids:
        raise ValueError(f"More than one form record for athlete_id(s): {duplicate_ids}")

    private = pd.DataFrame()
    for col in ["athlete_id", "email", "form_submission_timestamp", "upload_identifier"]:
        private[col] = form[col] if col in form else pd.NA
    private["processing_status"] = private["athlete_id"].map(
        lambda value: "linked" if pd.notna(value) else "needs_reconciliation"
    )

    deidentified = pd.DataFrame(index=form.index)
    for col in DEIDENTIFIED_COLUMNS:
        deidentified[col] = form[col] if col in form else pd.NA
    deidentified["age"] = pd.to_numeric(deidentified["age"], errors="coerce")
    deidentified["years_endurance_training"] = pd.to_numeric(
        deidentified["years_endurance_training"], errors="coerce"
    )
    deidentified["height_cm"] = deidentified["height_raw"].map(lambda x: _measurement(x, "height"))
    deidentified["weight_kg"] = deidentified["weight_raw"].map(lambda x: _measurement(x, "weight"))
    for col in ["raced_past_3_years", "injury_history"]:
        deidentified[col] = deidentified[col].map(_normalize_yes_no)
    deidentified["garmin_watch_normalized"] = (
        deidentified["garmin_watch"].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
    )
    deidentified["latest_race_time_seconds"] = deidentified["latest_race_time_raw"].map(_race_seconds)
    deidentified = deidentified.loc[deidentified["athlete_id"].notna(), DEIDENTIFIED_COLUMNS]

    processed_ids = {
        path.name for path in processed_root.iterdir()
        if path.is_dir() and (path / "daily_master.parquet").exists()
    } if processed_root.exists() else set()
    linked_ids = set(deidentified["athlete_id"].astype(str))
    reconciliation = pd.concat([
        pd.DataFrame({
            "issue": "form_submission_missing_athlete_id",
            "athlete_id": pd.NA,
            "form_row": form.index[form["athlete_id"].isna()] + 2,
        }),
        pd.DataFrame({
            "issue": "processed_athlete_missing_form",
            "athlete_id": sorted(processed_ids - linked_ids),
            "form_row": pd.NA,
        }),
        pd.DataFrame({
            "issue": "form_athlete_not_processed",
            "athlete_id": sorted(linked_ids - processed_ids),
            "form_row": pd.NA,
        }),
    ], ignore_index=True)
    return private, deidentified, reconciliation


def main():
    """Run metadata preparation from command-line arguments.

    Side Effects:
        Creates parent directories and writes private lookup, de-identified
        metadata, and reconciliation CSV files.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--form-csv", required=True, type=Path)
    parser.add_argument("--processed-root", default=Path("data_processed/athletes"), type=Path)
    parser.add_argument("--private-output", default=Path("data_private/participant_lookup.csv"), type=Path)
    parser.add_argument("--metadata-output", default=Path("data_processed/athletes/athlete_metadata.csv"), type=Path)
    parser.add_argument("--reconciliation-output", default=Path("data_private/metadata_reconciliation.csv"), type=Path)
    args = parser.parse_args()

    private, metadata, reconciliation = prepare_metadata(args.form_csv, args.processed_root)
    for frame, path in (
        (private, args.private_output),
        (metadata, args.metadata_output),
        (reconciliation, args.reconciliation_output),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
        print(f"Wrote {path}: {len(frame)} row(s)")


if __name__ == "__main__":
    main()
