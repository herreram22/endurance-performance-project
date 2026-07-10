"""Compare existing processed outputs with newly generated temp outputs.

Usage:
    PYTHONPATH=src python src/tools/compare_outputs.py

Writes `data_compare_report.md` in repo root.
"""
from pathlib import Path
import pandas as pd

ROOT = Path.cwd()
BASE = ROOT / "data_processed" / "athletes"
TEMP = ROOT / "data_processed_temp"
OUT = ROOT / "data_compare_report.md"

datasets = ["runs", "metrics", "predictions", "readiness", "maxmet", "history", "daily_master"]

report = ["# Data Compare Report\n"]

athletes = sorted({p.name for p in BASE.iterdir() if p.is_dir()} | {p.name for p in TEMP.iterdir() if p.is_dir()})

for athlete in athletes:
    report.append(f"## Athlete: {athlete}\n")
    base_dir = BASE / athlete
    temp_dir = TEMP / athlete
    for ds in datasets:
        base_file = base_dir / f"{ds}.parquet"
        temp_file = temp_dir / f"{ds}.parquet"
        if not base_file.exists() and not temp_file.exists():
            report.append(f"- {ds}: missing in both\n")
            continue
        if not base_file.exists():
            report.append(f"- {ds}: missing in existing outputs, present in temp\n")
            continue
        if not temp_file.exists():
            report.append(f"- {ds}: present in existing outputs, missing in temp\n")
            continue

        # both exist -> load and compare
        try:
            base_df = pd.read_parquet(base_file)
            temp_df = pd.read_parquet(temp_file)
        except Exception as e:
            report.append(f"- {ds}: error reading parquet: {e}\n")
            continue

        r_base, c_base = base_df.shape
        r_temp, c_temp = temp_df.shape
        cols_base = set(base_df.columns)
        cols_temp = set(temp_df.columns)
        cols_only_base = sorted(list(cols_base - cols_temp))
        cols_only_temp = sorted(list(cols_temp - cols_base))

        # date ranges
        def date_range(df):
            if "date" in df.columns:
                try:
                    s = pd.to_datetime(df["date"], errors="coerce").dropna()
                    if not s.empty:
                        return s.min().strftime("%Y-%m-%d"), s.max().strftime("%Y-%m-%d")
                except Exception:
                    return None
            return None

        dr_base = date_range(base_df)
        dr_temp = date_range(temp_df)

        report.append(f"- {ds}: rows existing={r_base}, temp={r_temp}; cols existing={c_base}, temp={c_temp}\n")
        if cols_only_base:
            report.append(f"  - cols only in existing: {cols_only_base[:10]}{'...' if len(cols_only_base)>10 else ''}\n")
        if cols_only_temp:
            report.append(f"  - cols only in temp: {cols_only_temp[:10]}{'...' if len(cols_only_temp)>10 else ''}\n")
        report.append(f"  - date_range existing={dr_base}, temp={dr_temp}\n")
    report.append("\n")

OUT.write_text('\n'.join(report))
print(f"Wrote {OUT}")
