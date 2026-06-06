from io import BytesIO
from pathlib import Path
import shutil
import sys
import time

from fastapi.testclient import TestClient
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.app.main import app


RUN_ID = str(int(time.time()))
LABEL_A = f"review_a_{RUN_ID}"
LABEL_B = f"review_b_{RUN_ID}"
DATASET_NAME = f"test_review_smoke_{RUN_ID}"
DATASET_PATH = ROOT / "data" / "exported" / DATASET_NAME


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str, detail: str | None = None) -> int:
    print(f"[NG] {message}")
    if detail:
        print(f"     {detail}")
    return 1


def create_dummy_jpeg(color: tuple[int, int, int]) -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", (320, 240), color=color)
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def upload_and_label(client: TestClient, filename: str, label: str, color: tuple[int, int, int]) -> tuple[int, str]:
    response = client.post(
        "/api/images/upload",
        data={"device_id": "test_review_smoke"},
        files={"image": (filename, create_dummy_jpeg(color), "image/jpeg")},
    )
    response.raise_for_status()
    data = response.json()
    image_id = data["image_id"]
    client.post(f"/api/images/{image_id}/label", json={"label": label}).raise_for_status()
    return image_id, data["filename"]


def main() -> int:
    if DATASET_PATH.exists():
        shutil.rmtree(DATASET_PATH)

    client = TestClient(app)
    try:
        train_a_id, train_a_filename = upload_and_label(client, "train_a.jpg", LABEL_A, (210, 40, 40))
        train_b_id, train_b_filename = upload_and_label(client, "train_b.jpg", LABEL_B, (40, 40, 210))
        test_id, test_filename = upload_and_label(client, "reserved_test.jpg", "test", (180, 80, 80))
        ok("Uploaded and labeled train/test images")
    except Exception as exc:
        return fail("Could not prepare images", str(exc))

    try:
        response = client.post(
            "/api/images/batch/test-reserve",
            json={"image_ids": [test_id], "reserved_for_test": True},
        )
        response.raise_for_status()
        data = response.json()
        if not data.get("ok") or data.get("updated_count") != 1:
            return fail("Could not mark image with fixed test label", str(data))
        ok("Marked one image with fixed test label")
    except Exception as exc:
        return fail("Fixed test label API failed", str(exc))

    try:
        response = client.post(
            "/api/datasets/export",
            json={
                "dataset_name": DATASET_NAME,
                "train_ratio": 1.0,
                "val_ratio": 0.0,
                "test_ratio": 0.0,
                "image_size": 96,
            },
        )
        response.raise_for_status()
        if not response.json().get("ok"):
            return fail("Dataset export returned ok=false", str(response.json()))
        ok("Exported dataset with fixed test label image in review_test")
    except Exception as exc:
        return fail("Dataset export failed", str(exc))

    exported_files = [path.name for path in DATASET_PATH.rglob("*.jpg")]
    if train_a_filename not in exported_files or train_b_filename not in exported_files:
        return fail("Training images were not exported", str(exported_files))
    if test_filename not in exported_files:
        return fail("fixed test label image was not exported", str(exported_files))
    test_output = DATASET_PATH / "review_test" / test_filename
    train_test_output = DATASET_PATH / "train" / LABEL_A / test_filename
    if not test_output.exists():
        return fail("fixed test label image was not exported to review_test", str(test_output))
    if train_test_output.exists():
        return fail("fixed test label image was incorrectly exported to train", str(train_test_output))

    info = (DATASET_PATH / "dataset_info.json").read_text(encoding="utf-8")
    if '"review_test_count"' not in info:
        return fail("dataset_info.json does not record review_test_count", info)
    ok("fixed test label image is exported only to review_test")

    print("\nTest review smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
