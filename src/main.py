import argparse
from pathlib import Path

from config import BASE_PATH, DEFAULT_OUTPUT_DIR
from pipeline import process_athlete


def discover_athlete_dirs(raw_data_dir):
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
            )
        except Exception as error:
            print(f"Error processing {athlete_id}: {error}")


if __name__ == "__main__":
    main()
