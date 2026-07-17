"""Discover and classify supported Garmin JSON exports for one athlete.

This is the first production pipeline stage. :func:`explore_files` recursively
scans an extracted Garmin export directory, assigns supported JSON files to
parser buckets using ordered filename rules, and keeps all remaining files in an
``unmatched`` bucket for auditability.

Inputs are filesystem directories containing extracted Garmin JSON files.
Outputs are path lists consumed directly by :mod:`parsing`. Classification is
deliberately conservative: profile biometrics and nested health-status files are
not flat daily analytical records and remain unmatched to protect both schema
integrity and participant privacy.

Dependencies:
    ``config.FILE_PATTERNS`` supplies the ordered filename rules. The JSON
    standard library supports content-based fallback classification.
"""

from config import BASE_PATH, FILE_PATTERNS
from pathlib import Path
import re
import json

UNSUPPORTED_PROFILE_PATTERNS = (
    re.compile(r"(?i)biometrics"),
    re.compile(r"(?i)healthstatusdata"),
)

# =========================
# DISCOVER PATHS
# =========================
def explore_files(data_raw_dir=BASE_PATH):
    """Classify JSON files found below an extracted athlete export directory.

    Args:
        data_raw_dir (pathlib.Path | str): Athlete-specific raw directory to
            scan recursively. Defaults to the configured raw-data root.

    Returns:
        dict[str, list[pathlib.Path]]: Parser buckets named ``activities``,
        ``metrics``, ``race_predictions``, ``max_met``,
        ``training_readiness``, and ``training_history``, plus ``unmatched``.
        Paths are sorted before classification, making parser concatenation and
        duplicate-resolution order deterministic.

    Notes:
        Garmin export packaging and filenames vary by account and device
        generation. Filename patterns are the primary contract; a lightweight
        content inspection recovers supported files with unfamiliar names.
        Invalid, empty, or unreadable JSON remains unmatched rather than being
        silently discarded.
    """
    data_raw_dir = Path(data_raw_dir)
    all_files = sorted(data_raw_dir.rglob("*.json"))

    # Initialize buckets including an 'unmatched' bucket for diagnostics
    discovered = {
        "activities": [],
        "metrics": [],
        "race_predictions": [],
        "max_met": [],
        "training_readiness": [],
        "training_history": [],
        "unmatched": [],
    }

    # Compile patterns once
    compiled = [(re.compile(pat), key) for pat, key in FILE_PATTERNS]

    for file in all_files:
        name = file.name
        # Profile biometrics and nested health-status exports are not flat daily
        # metric records. Keep them in unmatched diagnostics instead of sending
        # identifying/profile data to the analytical metrics parser.
        if any(pattern.search(name) for pattern in UNSUPPORTED_PROFILE_PATTERNS):
            discovered["unmatched"].append(file)
            continue

        matched = False
        for pattern, key in compiled:
            if pattern.search(name):
                # Ensure target key exists in discovered (future-proofing)
                if key not in discovered:
                    discovered[key] = []
                discovered[key].append(file)
                matched = True
                break

        if not matched:
            discovered["unmatched"].append(file)

    # Content-based fallback for unmatched files: inspect first JSON record
    for file in list(discovered["unmatched"]):
        if any(pattern.search(file.name) for pattern in UNSUPPORTED_PROFILE_PATTERNS):
            continue
        try:
            # Read a small portion to avoid large I/O; fall back to full load
            with open(file, "r") as f:
                raw = f.read(8192)
                try:
                    data = json.loads(raw)
                except Exception:
                    # try full load
                    f.seek(0)
                    data = json.load(f)

            # Normalize to a list of records
            if isinstance(data, dict):
                # some files are wrapped: e.g., {"summarizedActivitiesExport": [...]}
                if "summarizedActivitiesExport" in data and isinstance(data["summarizedActivitiesExport"], list):
                    # treat as activities
                    discovered["activities"].append(file)
                    discovered["unmatched"].remove(file)
                    continue
                # convert single-record dict to list for inspection
                sample = data
            elif isinstance(data, list) and len(data) > 0:
                sample = data[0]
            else:
                sample = None

            if isinstance(sample, dict):
                keys = set(sample.keys())
                # heuristic checks
                if {"raceTime5K", "raceTime10K"}.intersection(keys) or any(k.lower().find("race")!=-1 for k in keys):
                    discovered["race_predictions"].append(file)
                    discovered["unmatched"].remove(file)
                    continue
                if "calendarDate" in keys and any(k.lower().find("metric")!=-1 or k.lower().find("vo2")!=-1 or k.lower().find("maxmet")!=-1 for k in keys):
                    discovered["metrics"].append(file)
                    discovered["unmatched"].remove(file)
                    continue
                if "calendarDate" in keys and any(k.lower().find("history")!=-1 or k.lower().find("sport")!=-1 for k in keys):
                    discovered["training_history"].append(file)
                    discovered["unmatched"].remove(file)
                    continue
                if "hydration" in " ".join(k.lower() for k in keys):
                    # leave as unmatched but tag perhaps; for now keep unmatched
                    continue
        except Exception:
            # if content-based inference fails, keep file in unmatched for manual review
            continue

    return discovered
