import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timezone
from config import PIPELINE_VERSION

# =========================
# SAVING
# =========================
def _safe_date_range(df, date_col="date"):
    if df is None or df.empty or date_col not in df.columns:
        return None

    dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
    if dates.empty:
        return None

    return {
        "start": dates.min().strftime("%Y-%m-%d"),
        "end": dates.max().strftime("%Y-%m-%d"),
    }


def _make_parquet_safe(df):
    """Convert nested Garmin JSON columns to strings before parquet writes."""
    df = df.copy()

    for col in df.columns:
        if df[col].dtype != "object":
            continue

        has_nested = df[col].map(lambda x: isinstance(x, (dict, list))).any()
        if not has_nested:
            continue

        df[col] = df[col].map(
            lambda x: json.dumps(x)
            if isinstance(x, (dict, list)) and len(x) > 0
            else (None if isinstance(x, (dict, list)) else x)
        )

    return df


def save_outputs(athlete_id, outputs, output_dir, pipeline_version=PIPELINE_VERSION, overwrite=True):
    output_dir = Path(output_dir)
    athlete_output_dir = output_dir / str(athlete_id)
    athlete_output_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "athlete_id": athlete_id,
        "pipeline_version": pipeline_version,
        "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(athlete_output_dir),
        "datasets": {},
    }

    for dataset_name, df in outputs.items():
        if df is None:
            metadata["datasets"][dataset_name] = {
                "saved": False,
                "reason": "DataFrame is None",
            }
            print(f"Skipped {dataset_name}: DataFrame is None")
            continue

        if not isinstance(df, pd.DataFrame):
            metadata["datasets"][dataset_name] = {
                "saved": False,
                "reason": "Object is not a DataFrame",
            }
            print(f"Skipped {dataset_name}: Object not a DataFrame: {type(df)}")
            continue

        if df.empty:
            metadata["datasets"][dataset_name] = {
                "saved": False,
                "reason": "DataFrame is empty",
            }
            print(f"Skipped {dataset_name}: DataFrame is empty")
            continue

        output_path = athlete_output_dir / f"{dataset_name}.parquet"
        if output_path.exists() and not overwrite:
            raise FileExistsError(f"{output_path} already exists and overwrite=False")

        df_to_save = _make_parquet_safe(df)
        df_to_save.to_parquet(output_path, index=False)

        metadata["datasets"][dataset_name] = {
            "saved": True,
            "file": str(output_path),
            "rows": len(df_to_save),
            "columns": len(df_to_save.columns),
            "column_names": list(df_to_save.columns),
            "date_range": _safe_date_range(df_to_save),
        }

        print(f"Saved {dataset_name}: {len(df_to_save)} rows x {len(df_to_save.columns)} columns")

    metadata_path = athlete_output_dir / "metadata.json"
    if metadata_path.exists() and not overwrite:
        raise FileExistsError(f"{metadata_path} already exists and overwrite=False")

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=4)

    print(f"Saved metadata: {metadata_path}")
    return metadata
