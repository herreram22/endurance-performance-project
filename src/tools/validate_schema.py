"""Audit processed table columns against the legacy canonical-field checklist.

This read-only utility loads ``src/schema/field_mappings.json`` and scans
persisted Parquet/CSV schemas. It reports missing ``date``, ``activity_id``,
``device_id``, and ``user_id`` fields.

Important:
    The checklist predates dataset-specific contracts in :mod:`save_output`.
    Aggregate/daily tables legitimately omit activity-level fields, so findings
    are audit leads rather than universal pipeline failures.
"""
from pathlib import Path
import json
import logging
import pandas as pd

logger = logging.getLogger(__name__)


def load_field_mappings(mapping_path: Path):
    """Load raw-to-canonical Garmin field aliases.

    Args:
        mapping_path (pathlib.Path): Mapping JSON path.

    Returns:
        dict: Parsed mapping, or an empty mapping if the file is absent.

    Side Effects:
        Logs a warning for a missing mapping file.
    """
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
    """Inspect processed dataset schemas below an athlete output root.

    Args:
        processed_root (pathlib.Path): Root containing athlete directories.
        mapping_path (pathlib.Path): Canonical mapping path.

    Returns:
        list[dict]: Per-athlete missing-field summary and file-level findings.

    Notes:
        This legacy audit applies one broad field checklist to every table. Use
        persistence validation for authoritative dataset-specific requirements.
    """
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
