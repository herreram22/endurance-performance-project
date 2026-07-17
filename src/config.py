"""Central configuration for the production Garmin processing pipeline.

This module defines repository-relative input/output defaults, schema enforcement,
logging, and the ordered filename rules used by :mod:`discover_paths`. It accepts
no runtime input and exposes constants consumed by discovery, orchestration, and
persistence modules.

Filename rules are ordered because several Garmin export names contain the broad
word ``Metrics``. Specific datasets must win before the generic metrics fallback
to avoid routing MaxMet or race-prediction records to the wrong parser.
"""

from pathlib import Path
import logging

BASE_PATH = Path.cwd() / "data_raw"
DEFAULT_OUTPUT_DIR = Path.cwd() / "data_processed/athletes"
PIPELINE_VERSION = "0.1.0"
LOG_LEVEL = logging.INFO

# Applications can override this root logger configuration before importing the
# pipeline. INFO keeps routine batch progress visible without parser internals.
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

# Production saves reject datasets that do not meet dataset-specific contracts.
ENFORCE_SCHEMA = True

# Ordered filename patterns mapping to discovery keys. Each tuple is
# (regex pattern, discovery_key). Patterns are evaluated in order; the
# first match wins. Use (?i) for case-insensitive matching.
FILE_PATTERNS = [
    (r"(?i)metricsmaxmetdata|maxmet", "max_met"),
    (r"(?i)activityvo2max|vo2max", "max_met"),
    (
        r"(?i)runracepredictions|race.*predictions|"
        r"eventracetimeprojections|race.*projections",
        "race_predictions",
    ),
    (r"(?i)summarizedactivities|summarizedactivitiesexport", "activities"),
    (r"(?i)trainingreadinessdto|trainingreadiness", "training_readiness"),
    (r"(?i)traininghistory|traininghistory", "training_history"),
    (
        r"(?i)metricsacutetrainingload|metrics.*acutetraining|acutetraining",
        "metrics",
    ),
    (
        r"(?i)metricsheataltitudeacclimation|heataltitude|heat.*acclimation",
        "metrics",
    ),
    # Broad fallback must remain last; otherwise it captures MaxMet and other
    # more specific exports whose filenames also contain "Metrics".
    (r"(?i)metrics", "metrics"),
]
