"""Audit raw Garmin discovery buckets and representative JSON schemas.

This read-only diagnostic runs the production discovery stage across every
athlete under ``data_raw``. It records bucket counts, sample filenames, and up
to twenty top-level keys from representative files. The report supports parser
development and unmatched-file review; because raw Garmin filenames can contain
identity, the generated Markdown is ignored by version control and must be
treated as private operational data.

Usage:
    PYTHONPATH=src python src/tools/audit_data.py

Output:
    ``data_audit_report.md`` at the repository root.
"""
from pathlib import Path
from discover_paths import explore_files
import json

ROOT = Path.cwd()
RAW = ROOT / "data_raw"
OUT = ROOT / "data_audit_report.md"

report = []
report.append("# Data Audit Report\n")

athlete_dirs = sorted([p for p in RAW.iterdir() if p.is_dir()])
for athlete in athlete_dirs:
    report.append(f"## Athlete: {athlete.name}\n")
    discovered = explore_files(athlete)
    counts = {k: len(v) for k, v in discovered.items()}
    report.append(f"- Counts: {json.dumps(counts)}\n")

    # For each bucket, show up to 5 samples and sample keys from first file
    for key, files in discovered.items():
        report.append(f"### {key} ({len(files)})\n")
        for f in files[:5]:
            report.append(f"- {f.name}\n")
            # try to load first record and list keys
            try:
                with open(f, 'r') as fh:
                    data = json.load(fh)
                sample = None
                if isinstance(data, dict):
                    if 'summarizedActivitiesExport' in data and isinstance(data['summarizedActivitiesExport'], list):
                        sample = data['summarizedActivitiesExport'][0] if data['summarizedActivitiesExport'] else {}
                    else:
                        sample = data
                elif isinstance(data, list) and data:
                    sample = data[0]
                if isinstance(sample, dict):
                    keys = sorted(list(sample.keys()))
                    report.append(f"  - sample keys: {keys[:20]}\n")
            except Exception as e:
                report.append(f"  - could not read sample: {e}\n")
        report.append("\n")

# write report
OUT.write_text("\n".join(report))
print(f"Wrote {OUT}")
