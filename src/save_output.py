import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timezone
from config import PIPELINE_VERSION
import json
from pathlib import Path as _Path
from helpers import apply_field_mapping
import logging

logger = logging.getLogger(__name__)

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
        # Only inspect object columns
        if df[col].dtype != "object":
            continue

        # Try to coerce date-like string columns to datetimes to avoid
        # pyarrow conversion errors when writing parquet.
        try:
            parsed_dates = pd.to_datetime(df[col], errors="coerce")
            if parsed_dates.notna().mean() > 0.8:
                df[col] = parsed_dates
                continue
        except Exception:
            pass

        # If column contains nested dict/list objects, convert them to JSON strings
        has_nested = df[col].map(lambda x: isinstance(x, (dict, list))).any()
        if not has_nested:
            continue

        df[col] = df[col].map(
            lambda x: json.dumps(x)
            if isinstance(x, (dict, list)) and len(x) > 0
            else (None if isinstance(x, (dict, list)) else x)
        )

    return df


def _force_parse_timestamps(df):
    # Ensure common timestamp-like columns are datetimes to avoid parquet conversion errors
    timestamp_keys = [
        "timestamp",
        "timestampGMT",
        "timestampGmt",
        "timestampLocal",
        "persistedTimestampGMT",
        "start_time",
        "beginTimestamp",
    ]
    for key in list(df.columns):
        if key in timestamp_keys or key.lower().endswith("timestamp") or key.lower().startswith("timestamp"):
            try:
                # handle numeric epoch seconds or milliseconds
                col = df[key]
                if pd.api.types.is_numeric_dtype(col):
                    mx = pd.to_numeric(col, errors="coerce").dropna()
                    if not mx.empty:
                        maxv = mx.max()
                        if maxv > 10 ** 12:
                            df[key] = pd.to_datetime(col, unit="ms", errors="coerce")
                        elif maxv > 10 ** 9:
                            df[key] = pd.to_datetime(col, unit="s", errors="coerce")
                        else:
                            df[key] = pd.to_datetime(col, errors="coerce")
                    else:
                        df[key] = pd.to_datetime(col, errors="coerce")
                else:
                    df[key] = pd.to_datetime(df[key], errors="coerce")
            except Exception:
                logger.debug("Failed to coerce timestamp column %s", key, exc_info=True)
    return df


def _ensure_canonical_columns(df):
    """Ensure canonical columns exist by copying from known source variants.

    Uses `src/schema/field_mappings.json` to create canonical columns when a
    mapped source column exists but canonical name is missing.
    """
    try:
        mapping_path = Path(__file__).parent / "schema" / "field_mappings.json"
        if not mapping_path.exists():
            return df
        mapping = json.loads(mapping_path.read_text())
    except Exception:
        return df

    df = df.copy()
    cols = df.columns
    # For each mapping src->dst, if src exists and dst does not, create dst
    for src, dst in mapping.items():
        if src in cols and dst not in cols:
            df[dst] = df[src]
        # Also attempt lowercase matches for variants
        elif src.lower() in [c.lower() for c in cols] and dst not in cols:
            match = [c for c in cols if c.lower() == src.lower()][0]
            df[dst] = df[match]

    return df


from config import ENFORCE_SCHEMA


def save_outputs(athlete_id, outputs, output_dir, pipeline_version=PIPELINE_VERSION, overwrite=True, enforce_schema=None):
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

        # Ensure canonical columns exist where possible
        df = _ensure_canonical_columns(df)
        df_to_save = _make_parquet_safe(df)
        # Force-parse timestamp-like columns to datetimes
        df_to_save = _force_parse_timestamps(df_to_save)
        # Optionally enforce canonical schema
        if enforce_schema is None:
            enforce_schema = ENFORCE_SCHEMA
        if enforce_schema:
            required = {"date", "activity_id", "device_id", "user_id"}
            missing = [r for r in required if r not in [c.lower() for c in df_to_save.columns]]
            if missing:
                raise ValueError(f"Missing required canonical columns: {missing} in dataset {dataset_name}")
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
