from io import BytesIO
from pathlib import Path
import shutil
import sys

from fastapi.testclient import TestClient
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.app.main import app


DATASET_NAME = "smoke_test_dataset"
DATASET_PATH = ROOT / "data" / "exported" / DATASET_NAME


def ok(message: str) -> None:
    print(f"[OK] {message}")


def fail(message: str, detail: str | None = None) -> int:
    print(f"[NG] {message}")
    if detail:
        print(f"     {detail}")
    return 1


def create_dummy_jpeg() -> bytes:
    buffer = BytesIO()
    image = Image.new("RGB", (320, 240), color=(30, 120, 180))
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def main() -> int:
    if DATASET_PATH.exists():
        shutil.rmtree(DATASET_PATH)

    try:
        jpeg_bytes = create_dummy_jpeg()
        ok("Created dummy JPEG")
    except Exception as exc:
        return fail("Could not create dummy JPEG", str(exc))

    client = TestClient(app)

    try:
        upload_response = client.post(
            "/api/images/upload",
            data={"device_id": "smoke_test_device", "captured_at": "2026-05-29T00:00:00Z"},
            files={"image": ("smoke.jpg", jpeg_bytes, "image/jpeg")},
        )
        upload_response.raise_for_status()
        upload_data = upload_response.json()
        image_id = upload_data["image_id"]
        ok("Uploaded image")
    except Exception as exc:
        return fail("Image upload API failed", str(exc))

    try:
        list_response = client.get("/api/images", params={"limit": 20})
        list_response.raise_for_status()
        images = list_response.json().get("images", [])
        if not any(image["id"] == image_id for image in images):
            return fail("Uploaded image was not returned by /api/images")
        ok("Listed images")
    except Exception as exc:
        return fail("Image list API failed", str(exc))

    try:
        label_response = client.post(f"/api/images/{image_id}/label", json={"label": "target"})
        label_response.raise_for_status()
        if label_response.json().get("label") != "target":
            return fail("Label update response did not contain target")
        ok("Updated label")
    except Exception as exc:
        return fail("Label update API failed", str(exc))

    try:
        batch_response = client.post(
            "/api/images/batch-label",
            json={"image_ids": [image_id], "label": "target"},
        )
        batch_response.raise_for_status()
        batch_data = batch_response.json()
        if batch_data.get("updated_count") != 1:
            return fail("Batch label response did not update one image", str(batch_data))
        ok("Updated batch label")
    except Exception as exc:
        return fail("Batch label API failed", str(exc))

    try:
        csv_response = client.get("/api/images/export/multilabel.csv")
        csv_response.raise_for_status()
        csv_text = csv_response.text
        header = csv_text.splitlines()[0]
        for expected in ["filename", "label", "target"]:
            if expected not in header:
                return fail(f"Label CSV header was missing {expected}", header)
        if upload_data["filename"] not in csv_text:
            return fail("Uploaded image was not included in label CSV")
        ok("Exported label CSV")
    except Exception as exc:
        return fail("Label CSV export API failed", str(exc))

    try:
        export_response = client.post(
            "/api/datasets/export",
            json={
                "dataset_name": DATASET_NAME,
                "train_ratio": 0.7,
                "val_ratio": 0.2,
                "test_ratio": 0.1,
                "image_size": 96,
            },
        )
        export_response.raise_for_status()
        export_data = export_response.json()
        if not export_data.get("ok"):
            return fail("Dataset export returned ok=false", str(export_data))
        ok("Exported dataset")
    except Exception as exc:
        return fail("Dataset export API failed", str(exc))

    if not DATASET_PATH.exists():
        return fail("smoke_test_dataset was not created", str(DATASET_PATH))

    expected_image = DATASET_PATH / "train" / "target"
    if not expected_image.exists() or not any(expected_image.glob("*.jpg")):
        return fail("smoke_test_dataset has no train/target JPEG output", str(expected_image))

    ok("smoke_test_dataset exists")
    print("\nSmoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
