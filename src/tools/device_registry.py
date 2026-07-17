"""Enrich capability reports with a curated Garmin device registry.

This optional post-processing stage reads a capability JSON report and
``src/schema/device_registry.json``, then annotates athlete entries whose
detected device text matches registry keys. The current capability report stores
column evidence rather than device values, so enrichment is deliberately a
scaffold until a privacy-reviewed device-ID/model mapping is available.

Inputs and outputs are JSON files; analytical Parquet data is not modified.
"""
from pathlib import Path
import json
import logging

logger = logging.getLogger(__name__)


def load_registry(path: Path = None):
    """Load a device-model capability registry.

    Args:
        path (pathlib.Path | None): Optional registry JSON path. Defaults to the
            production schema directory.

    Returns:
        dict: Registry mapping device/model keys to metadata.

    Raises:
        FileNotFoundError: If the registry path does not exist.
        json.JSONDecodeError: If it is invalid JSON.
    """
    if path is None:
        path = Path(__file__).parent.parent / "schema" / "device_registry.json"
    if not path.exists():
        raise FileNotFoundError(f"Device registry not found: {path}")
    return json.loads(path.read_text())


def enrich_report(report_path: Path, registry_path: Path = None, out_path: Path = None):
    """Add registry matches to an existing device-capability report.

    Args:
        report_path (pathlib.Path): Capability report JSON.
        registry_path (pathlib.Path | None): Optional registry override.
        out_path (pathlib.Path | None): Output JSON path. Defaults beside the
            source report with an ``_enriched`` suffix.

    Returns:
        dict: Enriched report.

    Raises:
        FileNotFoundError: If the report or registry is missing.

    Side Effects:
        Writes the enriched JSON report and logs its location.
    """
    report_path = Path(report_path)
    if not report_path.exists():
        raise FileNotFoundError(report_path)

    data = json.loads(report_path.read_text())
    registry = load_registry(registry_path) if registry_path else load_registry()

    # This scaffold currently cannot map actual device IDs because report only
    # contains detected column names. Keep the structure for future enrichment.
    enriched = {"athletes": []}
    for a in data.get("athletes", []):
        ea = dict(a)
        # find any registry entries that match model_name substrings in device list
        ea["device_models"] = []
        for dev_key in registry.keys():
            # naive match: device key in athlete devices or in any dataset path
            if dev_key.lower() in " ".join(a.get("devices", [])).lower():
                ea["device_models"].append({dev_key: registry[dev_key]})
        enriched["athletes"].append(ea)

    out_path = out_path or report_path.parent / (report_path.stem + "_enriched.json")
    out_path.write_text(json.dumps(enriched, indent=2))
    logger.info("Wrote enriched report to %s", out_path)
    return enriched


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("report", help="Path to device_capability_report.json")
    parser.add_argument("--registry", help="Optional registry path")
    parser.add_argument("--out", help="Output path for enriched report")
    args = parser.parse_args()
    enrich_report(Path(args.report), registry_path=Path(args.registry) if args.registry else None, out_path=Path(args.out) if args.out else None)
