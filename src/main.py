"""Command-line entry point for batch Garmin athlete processing.

The CLI accepts either a raw-data root containing one directory per anonymized
athlete or a single extracted athlete directory. Directory basenames are the
authoritative athlete IDs; no identity is inferred from Garmin file contents.
Each athlete is processed independently, failures are collected, and the
combined panel is published only after every requested athlete succeeds.

Typical usage::

    python -m src.main --input-dir data_raw \
        --output-dir data_processed/athletes
"""

import argparse
from pathlib import Path

from config import BASE_PATH, DEFAULT_OUTPUT_DIR
from pipeline import process_athlete, refresh_all_athletes_daily_master


def discover_athlete_dirs(raw_data_dir):
    """Resolve a raw-data root into deterministic athlete directories.

    Args:
        raw_data_dir (pathlib.Path | str): Root containing athlete subdirectories
            or a single athlete directory containing files directly.

    Returns:
        list[pathlib.Path]: Sorted athlete directories. When no subdirectories
        exist, the input directory is treated as one athlete.

    Raises:
        FileNotFoundError: If the input path does not exist.
        ValueError: If the input path is a file.
    """
    raw_data_dir = Path(raw_data_dir)
    if not raw_data_dir.exists():
        raise FileNotFoundError(f"Input path does not exist: {raw_data_dir}")

    if raw_data_dir.is_file():
        raise ValueError(f"Input path must be a directory, not a file: {raw_data_dir}")

    subdirs = [path for path in sorted(raw_data_dir.iterdir()) if path.is_dir()]
    if subdirs:
        return subdirs

    return [raw_data_dir]


def parse_args():
    """Parse production pipeline command-line arguments.

    Returns:
        argparse.Namespace: Input/output paths, optional athlete filter, and
        overwrite policy.
    """
    parser = argparse.ArgumentParser(
        description="Run the athlete data pipeline for one or more athlete directories."
    )
    parser.add_argument(
        "--input-dir",
        default=BASE_PATH,
        help="Path to the raw data root or a single athlete raw directory."
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Path where processed athlete outputs will be written."
    )
    parser.add_argument(
        "--athlete-ids",
        nargs="*",
        default=None,
        help="Optional athlete directory names to process from the input root. If omitted, all athlete subdirectories will be processed."
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Do not overwrite existing output files."
    )
    return parser.parse_args()


def main():
    """Process requested athletes and publish the combined daily panel.

    Raises:
        RuntimeError: If no athlete directories match or any athlete fails.

    Side Effects:
        Prints progress, writes athlete outputs, and refreshes the combined
        dataset once after a successful batch.
    """
    args = parse_args()

    input_dir = Path(args.input_dir).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    overwrite = not args.no_overwrite

    athlete_dirs = discover_athlete_dirs(input_dir)
    if args.athlete_ids:
        athlete_dirs = [d for d in athlete_dirs if d.name in args.athlete_ids]

    if not athlete_dirs:
        raise RuntimeError(f"No athlete directories found in {input_dir}")

    print(f"Found {len(athlete_dirs)} athlete directories to process:")
    failures = []
    for athlete_dir in athlete_dirs:
        print(f" - {athlete_dir.name}")

    for athlete_dir in athlete_dirs:
        athlete_id = athlete_dir.name
        print(f"\nProcessing athlete {athlete_id} from {athlete_dir}")
        try:
            process_athlete(
                athlete_id=athlete_id,
                raw_data_dir=athlete_dir,
                output_dir=output_dir,
                overwrite=overwrite,
                refresh_combined=False,
            )
        except Exception as error:
            print(f"Error processing {athlete_id}: {error}")
            failures.append((athlete_id, str(error)))

    if failures:
        failed_ids = ", ".join(athlete_id for athlete_id, _ in failures)
        raise RuntimeError(
            f"Processing failed for {len(failures)} athlete(s): {failed_ids}"
        )

    refresh_all_athletes_daily_master(output_dir, overwrite=overwrite)


if __name__ == "__main__":
    main()
