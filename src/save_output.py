import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timezone
from config import PIPELINE_VERSION
import json
from pathlib import Path as _Path
from helpers import apply_field_mapping
import logging
import os
import re
import tempfile

logger = logging.getLogger(__name__)

ATHLETE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
DATASET_REQUIRED_COLUMNS = {
    "runs": {"athlete_id", "date", "activity_id"},
    "metrics": {"athlete_id", "date"},
    "predictions": {"athlete_id", "date"},
    "readiness": {"athlete_id", "date"},
    "maxmet": {"athlete_id", "date"},
    "history": {"athlete_id", "date"},
    "daily_master": {
        "athlete_id", "date", "total_distance_km", "total_duration_minutes"
    },
}
ALL_ATHLETES_DAILY_MASTER_FILE = "all_athletes_daily_master.parquet"
ALL_ATHLETES_METADATA_FILE = "all_athletes_daily_master.metadata.json"


def _validate_athlete_id(athlete_id):
    value = str(athlete_id)
    if not ATHLETE_ID_PATTERN.fullmatch(value) or value in {".", ".."}:
        raise ValueError(
            "athlete_id must contain only letters, numbers, dots, underscores, "
            "or hyphens and may not contain path separators"
        )
    return value


def _validate_dataset(dataset_name, df, athlete_id):
    required = DATASET_REQUIRED_COLUMNS.get(dataset_name, {"athlete_id"})
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Missing required columns {missing} in dataset {dataset_name}")

    ids = set(df["athlete_id"].dropna().astype(str).unique())
    if ids != {athlete_id}:
        raise ValueError(
            f"Dataset {dataset_name} contains unexpected athlete IDs: {sorted(ids)}"
        )

    if "date" in required:
        dates = pd.to_datetime(df["date"], errors="coerce")
        if dates.isna().any():
            raise ValueError(f"Dataset {dataset_name} contains null or invalid dates")
        if dates.duplicated().any() and dataset_name == "daily_master":
            raise ValueError("Dataset daily_master contains duplicate athlete-day rows")


def _atomic_write_parquet(df, output_path):
    fd, temp_name = tempfile.mkstemp(
        dir=output_path.parent, prefix=f".{output_path.name}.", suffix=".tmp"
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        df.to_parquet(temp_path, index=False)
        os.replace(temp_path, output_path)
    finally:
        temp_path.unlink(missing_ok=True)


def _atomic_write_json(payload, output_path):
    fd, temp_name = tempfile.mkstemp(
        dir=output_path.parent, prefix=f".{output_path.name}.", suffix=".tmp"
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(payload, handle, indent=4)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, output_path)
    finally:
        temp_path.unlink(missing_ok=True)

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

        # Only infer dates for explicitly date-named columns. Broad inference on
        # every object column is noisy and can corrupt identifiers or labels.
        col_lower = col.lower()
        if col_lower == "date" or col_lower.endswith("_date"):
            df[col] = pd.to_datetime(df[col], errors="coerce")
            continue

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
    athlete_id = _validate_athlete_id(athlete_id)
    output_dir = Path(output_dir)
    athlete_output_dir = output_dir / str(athlete_id)
    athlete_output_dir.mkdir(parents=True, exist_ok=True)

    metadata = {
        "athlete_id": athlete_id,
        "pipeline_version": pipeline_version,
        "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(athlete_output_dir),
        "schema_version": "1.0",
        "schema": {
            "standardized": True,
            "required_columns_by_dataset": {
                name: sorted(columns) for name, columns in DATASET_REQUIRED_COLUMNS.items()
            },
            "missing_value_strategy": {
                "preserve_nulls": True,
                "coverage_flag": "readiness_available",
                "fallback_for_numeric": "per_athlete_median",
            },
        },
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
            _validate_dataset(dataset_name, df_to_save, athlete_id)
        _atomic_write_parquet(df_to_save, output_path)

        coverage_flag = None
        if "readiness_available" in df_to_save.columns:
            coverage_flag = bool(df_to_save["readiness_available"].any())

        metadata["datasets"][dataset_name] = {
            "saved": True,
            "file": str(output_path),
            "rows": len(df_to_save),
            "columns": len(df_to_save.columns),
            "column_names": list(df_to_save.columns),
            "date_range": _safe_date_range(df_to_save),
            "missing_value_strategy": {
                "preserve_nulls": True,
                "coverage_flag": "readiness_available" if "readiness_available" in df_to_save.columns else None,
            },
            "coverage_flag": coverage_flag,
            "missing_fraction": round(float(df_to_save.isna().mean().mean()), 6) if not df_to_save.empty else 0.0,
        }

        print(f"Saved {dataset_name}: {len(df_to_save)} rows x {len(df_to_save.columns)} columns")

    metadata_path = athlete_output_dir / "metadata.json"
    if metadata_path.exists() and not overwrite:
        raise FileExistsError(f"{metadata_path} already exists and overwrite=False")

    _atomic_write_json(metadata, metadata_path)

    print(f"Saved metadata: {metadata_path}")
    return metadata


def save_all_athletes_daily_master(df, output_dir, overwrite=True):
    """Validate and atomically publish the cross-athlete daily panel."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / ALL_ATHLETES_DAILY_MASTER_FILE
    metadata_path = output_dir / ALL_ATHLETES_METADATA_FILE

    if not isinstance(df, pd.DataFrame) or df.empty:
        raise ValueError("Combined daily master must be a non-empty DataFrame")

    required = DATASET_REQUIRED_COLUMNS["daily_master"]
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"Combined daily master is missing required columns: {missing}")

    combined = _make_parquet_safe(df)
    combined["athlete_id"] = combined["athlete_id"].astype(str)
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce").dt.normalize()
    if combined[["athlete_id", "date"]].isna().any().any():
        raise ValueError("Combined daily master contains null athlete IDs or dates")
    if combined.duplicated(["athlete_id", "date"]).any():
        raise ValueError("Combined daily master contains duplicate athlete-day rows")

    combined = combined.sort_values(["athlete_id", "date"]).reset_index(drop=True)
    if not overwrite and (output_path.exists() or metadata_path.exists()):
        raise FileExistsError("Combined daily master already exists and overwrite=False")

    _atomic_write_parquet(combined, output_path)
    metadata = {
        "pipeline_version": PIPELINE_VERSION,
        "schema_version": "1.0",
        "processed_at_utc": datetime.now(timezone.utc).isoformat(),
        "file": str(output_path),
        "rows": len(combined),
        "athlete_count": int(combined["athlete_id"].nunique()),
        "athlete_ids": sorted(combined["athlete_id"].unique().tolist()),
        "date_range": _safe_date_range(combined),
        "columns": list(combined.columns),
    }
    _atomic_write_json(metadata, metadata_path)
    print(
        f"Saved combined daily master: {len(combined)} rows for "
        f"{metadata['athlete_count']} athlete(s)"
    )
    return metadata
