from config import BASE_PATH
from pathlib import Path

# =========================
# DISCOVER PATHS
# =========================
def explore_files(data_raw_dir=BASE_PATH):
    data_raw_dir = Path(data_raw_dir)
    all_files = sorted(data_raw_dir.rglob("*.json"))

    discovered = {
        "activities": [],
        "metrics": [],
        "race_predictions": [],
        "max_met": [],
        "training_readiness": [],
        "training_history": [],
    }

    for file in all_files:
        name = file.name.lower()

        if "summarizedactivities" in name:
            discovered["activities"].append(file)
        elif name.startswith("metrics") and not name.startswith("metricsmaxmetdata"):
            discovered["metrics"].append(file)
        elif name.startswith("runracepredictions"):
            discovered["race_predictions"].append(file)
        elif name.startswith("trainingreadinessdto"):
            discovered["training_readiness"].append(file)
        elif name.startswith("metricsmaxmetdata"):
            discovered["max_met"].append(file)
        elif name.startswith("traininghistory"):
            discovered["training_history"].append(file)

    return discovered