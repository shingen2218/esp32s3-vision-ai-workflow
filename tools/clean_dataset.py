import argparse
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Remove an exported dataset directory.")
    parser.add_argument("dataset_path", type=Path)
    args = parser.parse_args()
    if args.dataset_path.exists():
        shutil.rmtree(args.dataset_path)
        print(f"removed {args.dataset_path}")


if __name__ == "__main__":
    main()
