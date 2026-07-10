"""Validate processed tables against the canonical schema mapping.

This tool loads `src/schema/field_mappings.json` (if present) and checks
that key canonical fields exist in processed outputs.
"""
from pathlib import Path
import json
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def load_field_mappings(mapping_path: Path):
    if not mapping_path.exists():
        logger.warning("Field mappings not found at %s", mapping_path)
        return {}
    return json.loads(mapping_path.read_text())


def _sample_columns_from_file(path: Path):
    try:
        if path.suffix in (".parquet", ".pq"):
            df = pd.read_parquet(path, engine="pyarrow", columns=None)
            return list(df.columns)
        elif path.suffix in (".csv", ".txt"):
            df = pd.read_csv(path, nrows=20)
            return list(df.columns)
    except Exception as e:
        logger.debug("Could not read %s: %s", path, e)
    return []


def validate_processed(processed_root: Path, mapping_path: Path = Path("src/schema/field_mappings.json")):
    mappings = load_field_mappings(mapping_path)
    required = {"date", "activity_id", "device_id", "user_id"}
    findings = []

    for athlete_dir in sorted(processed_root.iterdir()):
        if not athlete_dir.is_dir():
            continue
        athlete_issues = {"athlete": athlete_dir.name, "missing_required": set(), "files": []}
        for f in athlete_dir.glob("**/*"):
            if not f.is_file() or f.suffix.lower() not in {".parquet", ".csv"}:
                continue
            cols = _sample_columns_from_file(f)
            if not cols:
                continue
            cols_l = {c.lower() for c in cols}
            missing = [r for r in required if r not in cols_l]
            if missing:
                athlete_issues["missing_required"].update(missing)
                athlete_issues["files"].append({"file": str(f.relative_to(athlete_dir)), "missing": missing})
        athlete_issues["missing_required"] = sorted(list(athlete_issues["missing_required"]))
        findings.append(athlete_issues)

    return findings


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-root", default="data_processed_temp", help="Processed data root to validate")
    args = parser.parse_args()
    res = validate_processed(Path(args.processed_root))
    for r in res:
        print(r)
