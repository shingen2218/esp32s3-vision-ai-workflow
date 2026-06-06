import csv
from io import StringIO

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from ..config import RAW_IMAGE_DIR
from ..database import get_db
from ..image_store import image_url, save_uploaded_image
from ..label_store import (
    add_labels_to_existing,
    all_label_names,
    ensure_labels,
    labels_status,
    parse_labels,
    remove_labels_from_existing,
    serialize_labels,
)
from ..schemas import BatchLabelUpdate, BatchTestReserveUpdate, ImageLabelsUpdate, LabelUpdate

router = APIRouter(prefix="/api/images", tags=["images"])


@router.post("/upload")
async def upload_image(
    image: UploadFile = File(...),
    device_id: str = Form(...),
    captured_at: str | None = Form(default=None),
):
    if not image.filename:
        raise HTTPException(status_code=400, detail="image file is required")
    return await save_uploaded_image(image, device_id, captured_at)


@router.get("")
def list_images(label: str | None = None, status: str | None = None, limit: int = 100):
    query = "SELECT id, filename, label, status, device_id, captured_at, uploaded_at, width, height, reserved_for_test FROM images"
    filters = []
    params: list[object] = []
    if status:
        filters.append("status = ?")
        params.append(status)
    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " ORDER BY id DESC LIMIT ?"
    params.append(500 if label else min(limit, 500))

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    images = []
    for row in rows:
        labels = parse_labels(row["label"])
        if label and label not in labels:
            continue
        item = dict(row)
        item["labels"] = labels
        item["reserved_for_test"] = bool(row["reserved_for_test"])
        item["url"] = image_url(row["filename"])
        images.append(item)
        if len(images) >= min(limit, 500):
            break
    return {"images": images}


@router.delete("/unknown")
@router.post("/delete-unknown")
def delete_unknown_images():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, filename, label, status FROM images WHERE status = 'unlabeled' OR label = 'unknown'"
        ).fetchall()
        deleted_files = 0
        for row in rows:
            path = RAW_IMAGE_DIR / row["filename"]
            if path.exists():
                path.unlink()
                deleted_files += 1
            conn.execute("DELETE FROM images WHERE id = ?", (row["id"],))
    return {"ok": True, "deleted_images": len(rows), "deleted_files": deleted_files}


def _labels_from_batch_update(update: BatchLabelUpdate) -> list[str]:
    if update.label:
        return parse_labels(update.label)
    if update.label_names:
        return parse_labels(update.label_names)
    raise HTTPException(status_code=400, detail="label or label_names is required")


def _labels_from_image_update(update: ImageLabelsUpdate) -> list[str]:
    if update.label:
        return parse_labels(update.label)
    if update.label_names:
        return parse_labels(update.label_names)
    raise HTTPException(status_code=400, detail="label or label_names is required")


@router.post("/batch-label")
@router.post("/batch/labels")
def update_labels(update: BatchLabelUpdate):
    label_names = _labels_from_batch_update(update)
    placeholders = ",".join("?" for _ in update.image_ids)
    with get_db() as conn:
        ensure_labels(conn, label_names)
        rows = conn.execute(
            f"SELECT id, label FROM images WHERE id IN ({placeholders})",
            update.image_ids,
        ).fetchall()
        for row in rows:
            labels = add_labels_to_existing(row["label"], label_names)
            reserved_for_test = 1 if labels == ["test"] else 0
            conn.execute(
                "UPDATE images SET label = ?, status = ?, reserved_for_test = ? WHERE id = ?",
                (serialize_labels(labels), labels_status(labels), reserved_for_test, row["id"]),
            )
        updated_count = len(rows)
    return {
        "ok": True,
        "image_ids": update.image_ids,
        "label": ",".join(label_names),
        "labels": label_names,
        "updated_count": updated_count,
    }


@router.delete("/batch/labels")
def delete_batch_labels(update: BatchLabelUpdate):
    label_names = _labels_from_batch_update(update)
    placeholders = ",".join("?" for _ in update.image_ids)
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT id, label FROM images WHERE id IN ({placeholders})",
            update.image_ids,
        ).fetchall()
        for row in rows:
            labels = remove_labels_from_existing(row["label"], label_names)
            conn.execute(
                "UPDATE images SET label = ?, status = ? WHERE id = ?",
                (serialize_labels(labels), labels_status(labels), row["id"]),
            )
    return {"ok": True, "image_ids": update.image_ids, "labels": label_names, "updated_count": len(rows)}


@router.post("/batch/test-reserve")
def update_test_reserve(update: BatchTestReserveUpdate):
    placeholders = ",".join("?" for _ in update.image_ids)
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT id FROM images WHERE id IN ({placeholders})",
            update.image_ids,
        ).fetchall()
        if update.reserved_for_test:
            conn.execute(
                f"UPDATE images SET label = 'test', status = 'labeled', reserved_for_test = 1 WHERE id IN ({placeholders})",
                update.image_ids,
            )
        else:
            conn.execute(
                f"UPDATE images SET label = 'unknown', status = 'unlabeled', reserved_for_test = 0 WHERE id IN ({placeholders})",
                update.image_ids,
            )
    return {
        "ok": True,
        "image_ids": update.image_ids,
        "reserved_for_test": update.reserved_for_test,
        "updated_count": len(rows),
    }


@router.get("/export/multilabel.csv")
def export_multilabel_csv():
    output = StringIO()

    with get_db() as conn:
        classes = all_label_names(conn)
        rows = conn.execute(
            "SELECT id, filename, label FROM images ORDER BY id"
        ).fetchall()

    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(["image_id", "filename", "label", *classes])

    for row in rows:
        active_labels = [label for label in parse_labels(row["label"]) if label != "unknown"]
        label = active_labels[0] if active_labels else "unknown"
        writer.writerow(
            [
                row["id"],
                row["filename"],
                label,
                *[1 if class_name == label else 0 for class_name in classes],
            ]
        )

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="label_dataset.csv"'},
    )


@router.get("/{image_id}/labels")
def get_image_labels(image_id: int):
    with get_db() as conn:
        row = conn.execute("SELECT label FROM images WHERE id = ?", (image_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="image not found")
    return {"image_id": image_id, "labels": parse_labels(row["label"])}


@router.post("/{image_id}/labels")
def add_image_labels(image_id: int, update: ImageLabelsUpdate):
    label_names = _labels_from_image_update(update)
    with get_db() as conn:
        row = conn.execute("SELECT label FROM images WHERE id = ?", (image_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="image not found")
        ensure_labels(conn, label_names)
        labels = add_labels_to_existing(row["label"], label_names)
        reserved_for_test = 1 if labels == ["test"] else 0
        conn.execute(
            "UPDATE images SET label = ?, status = ?, reserved_for_test = ? WHERE id = ?",
            (serialize_labels(labels), labels_status(labels), reserved_for_test, image_id),
        )
    return {"ok": True, "image_id": image_id, "labels": labels}


@router.delete("/{image_id}/labels/{label_name}")
def delete_image_label(image_id: int, label_name: str):
    with get_db() as conn:
        row = conn.execute("SELECT label FROM images WHERE id = ?", (image_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="image not found")
        labels = remove_labels_from_existing(row["label"], [label_name])
        conn.execute(
            "UPDATE images SET label = ?, status = ? WHERE id = ?",
            (serialize_labels(labels), labels_status(labels), image_id),
        )
    return {"ok": True, "image_id": image_id, "labels": labels}


@router.post("/{image_id}/label")
def update_label(image_id: int, update: LabelUpdate):
    labels = parse_labels(update.label)
    with get_db() as conn:
        ensure_labels(conn, labels)
        labels = add_labels_to_existing("", labels)
        reserved_for_test = 1 if labels == ["test"] else 0
        cursor = conn.execute(
            "UPDATE images SET label = ?, status = ?, reserved_for_test = ? WHERE id = ?",
            (serialize_labels(labels), labels_status(labels), reserved_for_test, image_id),
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="image not found")
    return {"ok": True, "image_id": image_id, "label": serialize_labels(labels), "labels": labels}
