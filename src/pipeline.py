from config import BASE_PATH, DEFAULT_OUTPUT_DIR, PIPELINE_VERSION
from parsing import (
    parse_activities,
    parse_metrics,
    parse_race_predictions,
    parse_training_readiness,
    parse_max_met,
    parse_training_history,
)
from table_builders import build_daily_master_table
from discover_paths import explore_files
from save_output import save_outputs

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


if __name__ == "__main__":
    process_athlete("pablo", BASE_PATH, DEFAULT_OUTPUT_DIR)
