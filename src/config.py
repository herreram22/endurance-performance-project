from pathlib import Path
import logging

# =========================
# CONFIG
# =========================
BASE_PATH = Path.cwd() / "data_raw"
DEFAULT_OUTPUT_DIR = Path.cwd() / "data_processed/athletes"
PIPELINE_VERSION = "0.1.0"
LOG_LEVEL = logging.INFO

# Configure basic logging for the package (can be overridden by app)
logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s %(levelname)s %(name)s: %(message)s')
# Toggle to enforce canonical schema fields on save (production)
ENFORCE_SCHEMA = True

# Ordered filename patterns mapping to discovery keys. Each tuple is
# (regex pattern, discovery_key). Patterns are evaluated in order; the
# first match wins. Use (?i) for case-insensitive matching.
FILE_PATTERNS = [
	# More specific first
	(r"(?i)metricsmaxmetdata|maxmet", "max_met"),
	(r"(?i)activityvo2max|vo2max", "max_met"),
	(r"(?i)runracepredictions|race.*predictions|eventracetimeprojections|race.*projections", "race_predictions"),
	(r"(?i)summarizedactivities|summarizedactivitiesexport", "activities"),
	(r"(?i)trainingreadinessdto|trainingreadiness", "training_readiness"),
	(r"(?i)traininghistory|traininghistory", "training_history"),
	(r"(?i)metricsacutetrainingload|metrics.*acutetraining|acutetraining", "metrics"),
	(r"(?i)metricsheataltitudeacclimation|heataltitude|heat.*acclimation", "metrics"),
	(r"(?i)metrics", "metrics"),
]
