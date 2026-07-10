# Device Capability Inference

This report/tooling infers device capabilities by scanning processed athlete datasets and looking
for indicative columns (e.g., `heartRate`, `power`, `latitude`). It produces a JSON and Markdown
report in `data_reports/device_capability_report.*`.

Usage:

python src/tools/device_capability.py --processed-roots data_processed_temp data_processed/athletes --output-dir data_reports

The inference is heuristic and should be refined by mapping device model IDs to known capability sets.
