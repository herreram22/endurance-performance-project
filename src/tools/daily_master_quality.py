"""Quality checks for the daily_master output."""
from pathlib import Path
import pandas as pd
import json

REQUIRED_COLUMNS = ["date", "athlete_id", "total_distance_km", "total_duration_minutes"]


def validate_daily_master(path: Path):
    df = pd.read_parquet(path)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    dates = pd.to_datetime(df["date"], errors="coerce") if "date" in df.columns else pd.Series(dtype="datetime64[ns]")
    bad_1970 = int((dates.dt.year == 1970).sum()) if not dates.empty else 0
    null_dates = int(dates.isna().sum()) if not dates.empty else 0
    result = {
        "file": str(path),
        "rows": len(df),
        "missing_columns": missing,
        "bad_1970_dates": bad_1970,
        "null_dates": null_dates,
        "athlete_id_values": sorted(df["athlete_id"].dropna().unique().astype(str)) if "athlete_id" in df.columns else [],
    }
    return result


def generate_report(root: Path, out_path: Path = None):
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
