from fastapi import APIRouter, HTTPException

from ..database import get_db
from ..label_store import (
    all_label_names,
    ensure_labels,
    label_counts,
    normalize_label_name,
    parse_labels,
    PROTECTED_LABELS,
    serialize_labels,
)
from ..schemas import LabelCreateRequest

router = APIRouter(prefix="/api/labels", tags=["labels"])


@router.get("")
def list_labels():
    with get_db() as conn:
        counts = label_counts(conn)
    labels = [{"name": name, "count": counts.get(name, 0)} for name in sorted(counts)]
    return {
        "labels": labels,
        "classes": [label["name"] for label in labels],
    }


@router.post("")
def create_label(request: LabelCreateRequest):
    name = normalize_label_name(request.name)
    if not name:
        raise HTTPException(status_code=400, detail="label name is required")
    with get_db() as conn:
        ensure_labels(conn, [name])
        counts = label_counts(conn)
    return {"ok": True, "label": {"name": name, "count": counts.get(name, 0)}}


@router.delete("/{label_name}")
def delete_label(label_name: str):
    name = normalize_label_name(label_name)
    if not name:
        raise HTTPException(status_code=400, detail="label name is required")
    if name in PROTECTED_LABELS:
        raise HTTPException(status_code=400, detail=f"{name} is a protected label")
    with get_db() as conn:
        rows = conn.execute("SELECT id, label FROM images").fetchall()
        for row in rows:
            labels = [label for label in parse_labels(row["label"]) if label != name]
            conn.execute(
                "UPDATE images SET label = ?, status = ? WHERE id = ?",
                (
                    serialize_labels(labels),
                    "labeled" if [label for label in labels if label != "unknown"] else "unlabeled",
                    row["id"],
                ),
            )
        conn.execute("DELETE FROM labels WHERE name = ?", (name,))
        names = all_label_names(conn)
    return {"ok": True, "deleted": name, "labels": names}
