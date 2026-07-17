"""Validate structural and readiness coverage quality of daily-master outputs.

This production validation utility reads persisted per-athlete Parquet tables
after pipeline execution. It reports required columns, invalid dates, athlete ID
values, and readiness-feature coverage without modifying data. Reports may be
printed or written as JSON for ingestion diagnostics and regression checks.
"""
from pathlib import Path
import pandas as pd
import json

REQUIRED_COLUMNS = ["date", "athlete_id", "total_distance_km", "total_duration_minutes"]
OPTIONAL_COVERAGE_COLUMNS = [
    "readiness_score_first",
    "readiness_score_last",
    "readiness_score_mean",
    "readiness_level_last",
    "recovery_time_last",
    "acute_load_last",
    "sleep_score_last",
    "valid_sleep_any",
    "readiness_snapshots",
]


def validate_daily_master(path: Path):
    """Validate one persisted daily-master Parquet file.

    Args:
        path (pathlib.Path): Daily-master Parquet path.

    Returns:
        dict: Row count, missing required columns, invalid-date counts, observed
        athlete IDs, and readiness coverage status/fraction.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        Exception: Parquet decoding errors propagate to make corrupt outputs
            visible.

    Notes:
        Readiness is optional across Garmin devices. Its absence is reported as
        partial coverage, not as a structural failure.
    """
    df = pd.read_parquet(path)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    dates = pd.to_datetime(df["date"], errors="coerce") if "date" in df.columns else pd.Series(dtype="datetime64[ns]")
    bad_1970 = int((dates.dt.year == 1970).sum()) if not dates.empty else 0
    null_dates = int(dates.isna().sum()) if not dates.empty else 0

    athlete_id_values = sorted(df["athlete_id"].dropna().unique().astype(str)) if "athlete_id" in df.columns else []
    readiness_cols_present = [col for col in OPTIONAL_COVERAGE_COLUMNS if col in df.columns]
    if readiness_cols_present:
        readiness_present = df[readiness_cols_present].notna().any(axis=1)
        feature_coverage = float(readiness_present.mean()) if not readiness_present.empty else 0.0
        coverage_status = "full" if readiness_present.all() else "partial"
    elif "readiness_available" in df.columns:
        readiness_available = df["readiness_available"].fillna(False)
        feature_coverage = float(readiness_available.mean()) if not readiness_available.empty else 0.0
        coverage_status = "full" if readiness_available.all() else "partial"
    else:
        # Absence of readiness columns is missing capability/coverage regardless
        # of athlete ID; IDs must not encode device-specific validation rules.
        feature_coverage = 0.0
        coverage_status = "partial"

    result = {
        "file": str(path),
        "rows": len(df),
        "missing_columns": missing,
        "bad_1970_dates": bad_1970,
        "null_dates": null_dates,
        "athlete_id_values": athlete_id_values,
        "coverage_status": coverage_status,
        "feature_coverage": feature_coverage,
    }
    return result


def generate_report(root: Path, out_path: Path = None):
    """Validate every athlete daily master below an output root.

    Args:
        root (pathlib.Path): Directory containing athlete subdirectories.
        out_path (pathlib.Path | None): Optional JSON report destination.

    Returns:
        dict: ``athletes`` list containing validation results or missing-file
        markers.

    Side Effects:
        Writes formatted JSON when ``out_path`` is provided.
    """
    root = Path(root)
    report = {"athletes": []}
    for athlete_dir in sorted(root.iterdir()):
        if not athlete_dir.is_dir():
            continue
        daily_master_path = athlete_dir / "daily_master.parquet"
        if not daily_master_path.exists():
            report["athletes"].append({"athlete": athlete_dir.name, "missing": True})
            continue
        res = validate_daily_master(daily_master_path)
        res["athlete"] = athlete_dir.name
        report["athletes"].append(res)
    if out_path:
        out_path.write_text(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("root", default="data_processed_temp", nargs="?", help="Processed root directory")
    parser.add_argument("--out", help="Output JSON report path")
    args = parser.parse_args()
    report = generate_report(Path(args.root), out_path=Path(args.out) if args.out else None)
    print(json.dumps(report, indent=2))
