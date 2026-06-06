import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.app.dataset_service import export_classification_dataset


def main() -> None:
    parser = argparse.ArgumentParser(description="Export labeled images into a classification dataset.")
    parser.add_argument("--name", default="dataset_v001")
    parser.add_argument("--train-ratio", type=float, default=0.7)
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--test-ratio", type=float, default=0.1)
    parser.add_argument("--image-size", type=int, default=96)
    args = parser.parse_args()

    path = export_classification_dataset(
        dataset_name=args.name,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        image_size=args.image_size,
    )
    print(path)


if __name__ == "__main__":
    main()
