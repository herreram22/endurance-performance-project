"""Utilities to infer device capabilities from processed athlete data.

The inference is heuristic-based: it detects presence of common columns
to decide whether a device/report contains HR, power, cadence, GPS, etc.
"""
from pathlib import Path
import json
import pandas as pd
import logging

logger = logging.getLogger(__name__)

# Mapping of capability name -> list of indicative column name patterns
CAPABILITY_COLUMN_MAP = {
    "heart_rate": ["heartrate", "heart_rate", "hr", "avgheartrate", "maxheartrate"],
    "power": ["power", "avgpower", "maxpower"],
    "cadence": ["cadence", "avgcadence"],
    "gps": ["latitude", "longitude", "gps", "position_lat", "position_long"],
    "vo2max": ["vo2max", "vo2_max"],
    "steps": ["steps", "stepcount"],
    "elevation": ["elevation", "altitude", "gain"],
    "temperature": ["temperature", "temp"],
}


def _lower_cols(cols):
    return [c.lower() for c in cols]


def infer_capabilities_from_columns(columns):
    cols = _lower_cols(columns)
    caps = set()
    for cap, patterns in CAPABILITY_COLUMN_MAP.items():
        for p in patterns:
            if any(p in c for c in cols):
                caps.add(cap)
                break
    return sorted(caps)


def _sample_columns_from_file(path: Path, nrows: int = 50):
    try:
        if path.suffix in (".parquet", ".pq"):
            df = pd.read_parquet(path, engine="pyarrow", columns=None)
            return list(df.columns)
        elif path.suffix in (".csv", ".txt"):
            df = pd.read_csv(path, nrows=nrows)
            return list(df.columns)
        else:
            # try to read with pandas generically
            df = pd.read_csv(path, nrows=nrows)
            return list(df.columns)
    except Exception as e:
        logger.debug("Could not sample %s: %s", path, e)
        return []


def analyze_athlete_dir(athlete_path: Path):
    result = {
        "athlete": athlete_path.name,
        "datasets": [],
        "capabilities": {},
        "devices": set(),
    }

    for f in athlete_path.glob("**/*"):
        if f.is_file() and f.suffix.lower() in {".parquet", ".csv", ".txt"}:
            cols = _sample_columns_from_file(f)
            if not cols:
                continue
            caps = infer_capabilities_from_columns(cols)
            result["datasets"].append({"path": str(f.relative_to(athlete_path)), "columns": cols, "caps": caps})
            for c in _lower_cols(cols):
                if c in ("deviceid", "device_id", "device"):
                    # devices may be ids — actual mapping to models must be external
                    # We capture the presence; values would require reading values.
                    result["devices"].add(c)
            # add per-dataset capability summary
            for cap in caps:
                result["capabilities"].setdefault(cap, 0)
                result["capabilities"][cap] += 1

    # convert sets to lists for JSON
    result["devices"] = sorted(list(result["devices"]))
    return result


def generate_report(processed_roots, output_dir: Path = Path("data_reports")):
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {"athletes": []}

    for root in processed_roots:
        p = Path(root)
        if not p.exists():
            logger.debug("Processed root not found: %s", p)
            continue
        for athlete_dir in sorted(p.iterdir()):
            if not athlete_dir.is_dir():
                continue
            analysis = analyze_athlete_dir(athlete_dir)
            report["athletes"].append(analysis)

    # write json and markdown summary
    out_json = output_dir / "device_capability_report.json"
    out_md = output_dir / "device_capability_report.md"
    out_json.write_text(json.dumps(report, indent=2))

    with out_md.open("w") as fh:
        fh.write("# Device Capability Report\n\n")
        for a in report["athletes"]:
            fh.write(f"## {a['athlete']}\n")
            fh.write(f"- Datasets scanned: {len(a['datasets'])}\n")
            fh.write(f"- Devices (detected id columns): {a['devices']}\n")
            fh.write(f"- Capabilities summary: {a['capabilities']}\n\n")

    logger.info("Wrote device capability report to %s and %s", out_json, out_md)
    return report


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--processed-roots", nargs="+", default=["data_processed_temp", "data_processed/athletes"], help="Processed data roots to scan")
    parser.add_argument("--output-dir", default="data_reports")
    args = parser.parse_args()
    generate_report(args.processed_roots, output_dir=Path(args.output_dir))
