from config import BASE_PATH, DEFAULT_OUTPUT_DIR, PIPELINE_VERSION
from parsing import (
    parse_activities,
    parse_metrics,
    parse_race_predictions,
    parse_training_readiness,
    parse_max_met,
    parse_training_history,
)
import pandas as pd
from pathlib import Path

from table_builders import build_daily_master_table, build_multi_athlete_daily_master
from discover_paths import explore_files
from save_output import save_outputs, save_all_athletes_daily_master

# =========================
# PIPELINE
# =========================
def process_athlete(
    athlete_id,
    raw_data_dir=BASE_PATH,
    output_dir=DEFAULT_OUTPUT_DIR,
    overwrite=True,
):
    files = explore_files(raw_data_dir)

    runs_df = parse_activities(files["activities"], athlete_id)
    metrics_df = parse_metrics(files["metrics"], athlete_id)
    predictions_df = parse_race_predictions(files["race_predictions"], athlete_id)
    readiness_df = parse_training_readiness(files["training_readiness"], athlete_id)
    maxmet_df = parse_max_met(files["max_met"], athlete_id)
    history_df = parse_training_history(files["training_history"], athlete_id)

    daily_master = build_daily_master_table(
        athlete_id=athlete_id,
        runs=runs_df,
        metrics=metrics_df,
        predictions=predictions_df,
        readiness=readiness_df,
        maxmet=maxmet_df,
        history=history_df,
    )

    outputs = {
        "runs": runs_df,
        "metrics": metrics_df,
        "predictions": predictions_df,
        "readiness": readiness_df,
        "maxmet": maxmet_df,
        "history": history_df,
        "daily_master": daily_master,
    }

    save_outputs(
        athlete_id,
        outputs,
        output_dir,
        pipeline_version=PIPELINE_VERSION,
        overwrite=overwrite,
    )

    return daily_master


def refresh_all_athletes_daily_master(output_dir=DEFAULT_OUTPUT_DIR, overwrite=True):
    """Rebuild the persisted panel from validated per-athlete outputs."""
    output_dir = Path(output_dir)
    frames = []
    for athlete_dir in sorted(output_dir.iterdir() if output_dir.exists() else []):
        if not athlete_dir.is_dir():
            continue
        path = athlete_dir / "daily_master.parquet"
        if not path.exists():
            continue
        frame = pd.read_parquet(path)
        ids = set(frame.get("athlete_id", pd.Series(dtype="object")).dropna().astype(str))
        if ids != {athlete_dir.name}:
            raise ValueError(
                f"{path} contains athlete IDs {sorted(ids)}, expected {athlete_dir.name}"
            )
        frames.append(frame)

    combined = build_multi_athlete_daily_master(frames)
    if combined.empty:
        raise RuntimeError(f"No per-athlete daily master files found in {output_dir}")
    save_all_athletes_daily_master(combined, output_dir, overwrite=overwrite)
    return combined


if __name__ == "__main__":
    process_athlete("pablo", BASE_PATH, DEFAULT_OUTPUT_DIR)
