"""Run parsing functions over discovered files and report any exceptions.

Usage:
    PYTHONPATH=src python src/tools/test_parsing.py
"""
from pathlib import Path
from discover_paths import explore_files
from parsing import (
    parse_activities_file,
    parse_metrics_files,
    parse_race_predictions_file,
    parse_training_readiness_file,
    parse_max_met_files,
    parse_training_history_files,
)

ROOT = Path.cwd()
RAW = ROOT / "data_raw"

report = []
for athlete in sorted(RAW.iterdir()):
    if not athlete.is_dir():
        continue
    report.append(f"Athlete: {athlete.name}")
    discovered = explore_files(athlete)
    # test each bucket
    def try_parse(func, files):
        for f in files[:10]:
            try:
                df = func(f, athlete.name)
                # report shape
                report.append(f"  OK {f.name}: {None if df is None else (getattr(df,'shape',None))}")
            except Exception as e:
                report.append(f"  ERR {f.name}: {e}")

    try_parse(parse_activities_file, discovered.get('activities', []))
    try_parse(parse_metrics_files, discovered.get('metrics', []))
    try_parse(parse_race_predictions_file, discovered.get('race_predictions', []))
    try_parse(parse_training_readiness_file, discovered.get('training_readiness', []))
    try_parse(parse_max_met_files, discovered.get('max_met', []))
    try_parse(parse_training_history_files, discovered.get('training_history', []))

OUT = ROOT / 'parsing_test_report.txt'
OUT.write_text('\n'.join(report))
print(f"Wrote {OUT}")
