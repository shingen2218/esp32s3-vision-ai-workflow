from io import BytesIO
from pathlib import Path
import sys
import time

from fastapi.testclient import TestClient
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from server.app.main import app


RUN_ID = str(int(time.time()))
LABEL_SCREW = f"screw_smoke_{RUN_ID}"
LABEL_METAL = f"metal_smoke_{RUN_ID}"
LABEL_DEFAULT_LIKE = f"target_smoke_{RUN_ID}"


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


def upload_image(client: TestClient, filename: str, color: tuple[int, int, int]) -> tuple[int, str]:
    response = client.post(
        "/api/images/upload",
        data={"device_id": "label_smoke_test"},
        files={"image": (filename, create_dummy_jpeg(color), "image/jpeg")},
    )
    response.raise_for_status()
    data = response.json()
    return data["image_id"], data["filename"]


def main() -> int:
    client = TestClient(app)

    try:
        for label in [LABEL_SCREW, LABEL_METAL, LABEL_DEFAULT_LIKE]:
            response = client.post("/api/labels", json={"name": label})
            response.raise_for_status()
        ok("Created smoke labels")
    except Exception as exc:
        return fail("Could not create labels", str(exc))

    try:
        image1_id, image1_filename = upload_image(client, "label_smoke_1.jpg", (210, 50, 50))
        image2_id, image2_filename = upload_image(client, "label_smoke_2.jpg", (50, 80, 210))
        ok("Uploaded two dummy images")
    except Exception as exc:
        return fail("Could not upload dummy images", str(exc))

    try:
        response = client.post(
            f"/api/images/{image1_id}/labels",
            json={"label_names": [LABEL_SCREW]},
        )
        response.raise_for_status()
        response = client.post(
            f"/api/images/{image1_id}/labels",
            json={"label_names": [LABEL_METAL]},
        )
        response.raise_for_status()
        if response.json().get("labels", []) != [LABEL_METAL]:
            return fail("Image 1 label was not replaced correctly", str(response.json()))

        response = client.post(
            f"/api/images/{image2_id}/labels",
            json={"label_names": [LABEL_SCREW]},
        )
        response.raise_for_status()
        if LABEL_SCREW not in response.json().get("labels", []):
            return fail("Image 2 screw label was not set", str(response.json()))
        ok("Applied one label per image")
    except Exception as exc:
        return fail("Could not apply image labels", str(exc))

    try:
        response = client.get("/api/images", params={"limit": 50})
        response.raise_for_status()
        images = response.json().get("images", [])
        image1 = next(image for image in images if image["id"] == image1_id)
        image2 = next(image for image in images if image["id"] == image2_id)
        if image1.get("labels", []) != [LABEL_METAL] or image2.get("labels", []) != [LABEL_SCREW]:
            return fail("Image list did not include labels arrays", str([image1, image2]))
        ok("Image list returns labels arrays")
    except Exception as exc:
        return fail("Image list labels check failed", str(exc))

    try:
        response = client.get("/api/labels")
        response.raise_for_status()
        labels = {item["name"]: item["count"] for item in response.json().get("labels", [])}
        if labels.get(LABEL_SCREW) != 1:
            return fail(f"{LABEL_SCREW} count is not 1", str(labels.get(LABEL_SCREW)))
        if labels.get(LABEL_METAL) != 1:
            return fail(f"{LABEL_METAL} count is not 1", str(labels.get(LABEL_METAL)))
        ok("Label counts are correct")
    except Exception as exc:
        return fail("Label count check failed", str(exc))

    try:
        response = client.delete(f"/api/images/{image1_id}/labels/{LABEL_METAL}")
        response.raise_for_status()
        if LABEL_METAL in response.json().get("labels", []):
            return fail("Metal label was not removed from image 1", str(response.json()))
        ok("Removed one label from one image")
    except Exception as exc:
        return fail("Could not remove image label", str(exc))

    try:
        response = client.get("/api/images/export/multilabel.csv")
        response.raise_for_status()
        csv_text = response.text
        header = csv_text.splitlines()[0]
        for expected in ["filename", "label", LABEL_SCREW, LABEL_METAL]:
            if expected not in header:
                return fail(f"CSV header missing {expected}", header)
        rows = [line for line in csv_text.splitlines() if image1_filename in line or image2_filename in line]
        if len(rows) != 2:
            return fail("CSV did not include both smoke images", "\n".join(rows))
        screw_index = header.split(",").index(LABEL_SCREW)
        metal_index = header.split(",").index(LABEL_METAL)
        for row in rows:
            cells = row.split(",")
            if image1_filename in row and (cells[screw_index] != "0" or cells[metal_index] != "0"):
                return fail("CSV should show image 1 as unknown after label removal", row)
            if image2_filename in row and (cells[screw_index] != "1" or cells[metal_index] != "0"):
                return fail("CSV should show image 2 as screw only", row)
        ok("Label CSV contains one-hot dynamic label columns")
    except Exception as exc:
        return fail("CSV check failed", str(exc))

    try:
        response = client.delete(f"/api/labels/{LABEL_SCREW}")
        response.raise_for_status()
        if not response.json().get("ok"):
            return fail("Delete label API returned ok=false", str(response.json()))

        response = client.get("/api/images", params={"limit": 50})
        response.raise_for_status()
        images = response.json().get("images", [])
        affected = [image for image in images if image["id"] in [image1_id, image2_id]]
        if any(LABEL_SCREW in image.get("labels", []) for image in affected):
            return fail("Deleted label is still attached to an image", str(affected))

        response = client.get("/api/labels")
        response.raise_for_status()
        label_names = [item["name"] for item in response.json().get("labels", [])]
        if LABEL_SCREW in label_names:
            return fail("Deleted label is still in label palette", str(label_names))

        response = client.get("/api/images/export/multilabel.csv")
        response.raise_for_status()
        header = response.text.splitlines()[0]
        if LABEL_SCREW in header:
            return fail("Deleted label is still in CSV header", header)
        ok("Deleted label was removed from images, palette, and CSV")
    except Exception as exc:
        return fail("Delete label check failed", str(exc))

    try:
        response = client.delete(f"/api/labels/{LABEL_DEFAULT_LIKE}")
        response.raise_for_status()
        response = client.get("/api/labels")
        response.raise_for_status()
        label_names = [item["name"] for item in response.json().get("labels", [])]
        if LABEL_DEFAULT_LIKE in label_names:
            return fail("Deleted default-like label was recreated", str(label_names))
        ok("Deleted default-like label was not recreated")
    except Exception as exc:
        return fail("Default-like label delete check failed", str(exc))

    try:
        response = client.delete("/api/labels/unknown")
        if response.status_code != 400:
            return fail("unknown label delete should be rejected", f"status={response.status_code}")
        response = client.get("/api/labels")
        response.raise_for_status()
        label_names = [item["name"] for item in response.json().get("labels", [])]
        if "unknown" not in label_names:
            return fail("unknown label disappeared from label list", str(label_names))
        ok("unknown label is protected")
    except Exception as exc:
        return fail("Protected unknown label check failed", str(exc))

    print("\nLabel smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
