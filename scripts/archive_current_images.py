from pathlib import Path
import shutil
import sqlite3
import sys
from datetime import datetime


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
METADATA_DB = ROOT / "data" / "metadata" / "images.sqlite3"
ARCHIVE_DIR = ROOT / "data" / "archived"


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str, detail: str | None = None) -> int:
    print(f"[NG] {message}")
    if detail:
        print(f"     {detail}")
    return 1


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_raw_dir = ARCHIVE_DIR / f"raw_{timestamp}"
    archive_db_path = ARCHIVE_DIR / f"images_{timestamp}.sqlite3"
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive_raw_dir.mkdir(parents=True, exist_ok=True)

    if not RAW_DIR.exists():
        return fail("data/raw does not exist", str(RAW_DIR))

    image_files = sorted(RAW_DIR.glob("*.jpg"))
    for image_file in image_files:
        shutil.move(str(image_file), archive_raw_dir / image_file.name)
    ok(f"Archived {len(image_files)} raw JPEG files to {archive_raw_dir}")

    if METADATA_DB.exists():
        shutil.copy2(METADATA_DB, archive_db_path)
        with sqlite3.connect(METADATA_DB) as conn:
            conn.execute("DELETE FROM images")
            conn.commit()
        ok(f"Backed up metadata DB to {archive_db_path}")
        ok("Cleared images table")
    else:
        ok("Metadata DB does not exist yet")

    print("\nCurrent images were archived. New captures will start from an empty image list.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
