import json

from fastapi import APIRouter, HTTPException

from ..config import EXPORTED_DIR
from ..dataset_service import export_classification_dataset
from ..schemas import DatasetExportRequest

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.get("")
def list_datasets():
    datasets = []
    for dataset_dir in sorted(EXPORTED_DIR.iterdir() if EXPORTED_DIR.exists() else []):
        if not dataset_dir.is_dir():
            continue
        info_path = dataset_dir / "dataset_info.json"
        if not info_path.exists():
            continue
        try:
            info = json.loads(info_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            info = {}
        datasets.append(
            {
                "name": dataset_dir.name,
                "path": str(dataset_dir.relative_to(EXPORTED_DIR.parent.parent)),
                "dataset_type": info.get("dataset_type", "classification"),
                "classes": info.get("classes", []),
                "image_size": info.get("image_size"),
                "train_count": info.get("train_count", 0),
                "val_count": info.get("val_count", 0),
                "test_count": info.get("test_count", 0),
                "excluded_unknown_count": info.get("excluded_unknown_count", 0),
                "excluded_reserved_test_count": info.get("excluded_reserved_test_count", 0),
            }
        )
    return {"datasets": datasets}


@router.post("/export")
def export_dataset(request: DatasetExportRequest):
    try:
        dataset_path = export_classification_dataset(
            dataset_name=request.dataset_name,
            train_ratio=request.train_ratio,
            val_ratio=request.val_ratio,
            test_ratio=request.test_ratio,
            image_size=request.image_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "dataset_path": str(dataset_path)}
