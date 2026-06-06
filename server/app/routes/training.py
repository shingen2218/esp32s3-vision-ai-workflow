import subprocess
import sys
import json
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..config import MODEL_DIR, PROJECT_ROOT
from ..schemas import TrainingStartRequest

router = APIRouter(prefix="/api/training", tags=["training"])
TRAINING_PROCESSES: dict[str, subprocess.Popen] = {}
EPOCH_PATTERN = re.compile(r"Epoch\s+(\d+)/(\d+)")
METRIC_PATTERN = re.compile(r"(accuracy|loss|val_accuracy|val_loss):\s*([0-9.]+)")


def _count_training_images(dataset_path: Path) -> int:
    train_path = dataset_path / "train"
    if not train_path.exists():
        return 0
    return sum(1 for path in train_path.rglob("*") if path.suffix.lower() in {".bmp", ".gif", ".jpeg", ".jpg", ".png"})


def _read_log_tail_and_progress(log_path: Path) -> tuple[str, int | None, int | None]:
    if not log_path.exists():
        return "", None, None
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    current_epoch = None
    total_epochs = None
    for line in lines:
        match = EPOCH_PATTERN.search(line)
        if match:
            current_epoch = int(match.group(1))
            total_epochs = int(match.group(2))
    return "\n".join(lines[-80:]), current_epoch, total_epochs


def _read_run_info(model_dir: Path) -> dict:
    run_info_path = model_dir / "run_info.json"
    if not run_info_path.exists():
        return {}


def _parse_training_history(log_path: Path) -> list[dict]:
    if not log_path.exists():
        return []
    history = []
    current_epoch = None
    total_epochs = None
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        epoch_match = EPOCH_PATTERN.search(line)
        if epoch_match:
            current_epoch = int(epoch_match.group(1))
            total_epochs = int(epoch_match.group(2))
            continue
        metrics = {name: float(value) for name, value in METRIC_PATTERN.findall(line)}
        if current_epoch is not None and metrics:
            history.append({"epoch": current_epoch, "total_epochs": total_epochs, **metrics})
            current_epoch = None
    return history
    try:
        data = json.loads(run_info_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


@router.get("/models")
def list_models():
    models = []
    model_dirs = []
    for path in MODEL_DIR.iterdir() if MODEL_DIR.exists() else []:
        if path.is_dir():
            model_dirs.append(path)
    for model_dir in sorted(model_dirs, key=lambda path: path.stat().st_mtime, reverse=True):
        if not model_dir.is_dir():
            continue
        model_path = model_dir / "model.keras"
        labels_path = model_dir / "labels.txt"
        if not model_path.exists():
            continue
        run_info = _read_run_info(model_dir) or {}
        labels = []
        if labels_path.exists():
            labels = [line.strip() for line in labels_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        try:
            model_dir_relative = str(model_dir.relative_to(PROJECT_ROOT))
        except ValueError:
            model_dir_relative = str(model_dir)
        models.append(
            {
                "run_id": model_dir.name,
                "path": model_dir_relative,
                "dataset_path": run_info.get("dataset_path"),
                "dataset_path_relative": run_info.get("dataset_path_relative"),
                "epochs": run_info.get("epochs"),
                "batch_size": run_info.get("batch_size"),
                "model_type": run_info.get("model_type"),
                "labels": labels,
                "created_at": datetime.fromtimestamp(model_dir.stat().st_mtime).isoformat(),
            }
        )
    return {"models": models}


@router.post("/start")
def start_training(request: TrainingStartRequest):
    dataset_path = (PROJECT_ROOT / request.dataset_path).resolve()
    if not dataset_path.exists():
        raise HTTPException(status_code=400, detail=f"dataset path does not exist: {request.dataset_path}")
    image_count = _count_training_images(dataset_path)
    if image_count == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                f"dataset has no training images: {request.dataset_path}. "
                "Label images first, then export a dataset before starting training."
            ),
        )

    run_id = "train_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = MODEL_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "train.log"
    (out_dir / "run_info.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "dataset_path": str(dataset_path),
                "dataset_path_relative": str(dataset_path.relative_to(PROJECT_ROOT)),
                "epochs": request.epochs,
                "batch_size": request.batch_size,
                "model_type": request.model_type,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    command = [
        sys.executable,
        "-u",
        str(PROJECT_ROOT / "trainer" / "train_classifier.py"),
        "--dataset",
        str(dataset_path),
        "--epochs",
        str(request.epochs),
        "--batch-size",
        str(request.batch_size),
        "--out-dir",
        str(out_dir),
    ]
    log_file = log_path.open("w", encoding="utf-8")
    process = subprocess.Popen(command, cwd=PROJECT_ROOT, text=True, stdout=log_file, stderr=subprocess.STDOUT)
    TRAINING_PROCESSES[run_id] = process
    return {"ok": True, "run_id": run_id, "log_path": str(log_path), "status": "running"}


@router.get("/{run_id}/status")
def read_training_status(run_id: str):
    log_path = MODEL_DIR / run_id / "train.log"
    process = TRAINING_PROCESSES.get(run_id)
    if process is None:
        if (MODEL_DIR / run_id / "model.keras").exists():
            status = "completed"
            returncode = 0
        elif log_path.exists():
            status = "unknown"
            returncode = None
        else:
            return {"ok": False, "status": "missing", "returncode": None}
    else:
        returncode = process.poll()
        if returncode is None:
            status = "running"
        elif returncode == 0:
            status = "completed"
        else:
            status = "failed"
            TRAINING_PROCESSES.pop(run_id, None)

    log_tail, current_epoch, total_epochs = _read_log_tail_and_progress(log_path)
    return {
        "ok": status in {"running", "completed"},
        "status": status,
        "returncode": returncode,
        "current_epoch": current_epoch,
        "total_epochs": total_epochs,
        "log_tail": log_tail,
    }


@router.get("/{run_id}/log")
def read_training_log(run_id: str):
    log_path = MODEL_DIR / run_id / "train.log"
    if not log_path.exists():
        return {"ok": False, "log": ""}
    return {"ok": True, "log": log_path.read_text(encoding="utf-8", errors="replace")}


@router.get("/{run_id}/history")
def read_training_history(run_id: str):
    model_dir = MODEL_DIR / run_id
    log_path = model_dir / "train.log"
    if not log_path.exists():
        return {"ok": False, "history": []}
    history = _parse_training_history(log_path)
    final = history[-1] if history else None
    return {"ok": True, "run_id": run_id, "history": history, "final": final}


@router.post("/{run_id}/test-reserved-images")
def test_reserved_images(run_id: str, limit: int = 50):
    model_dir = MODEL_DIR / run_id
    if not (model_dir / "model.keras").exists():
        raise HTTPException(status_code=400, detail=f"model.keras not found for run_id: {run_id}")
    command = [
        sys.executable,
        str(PROJECT_ROOT / "trainer" / "test_reserved_images.py"),
        "--model-dir",
        str(model_dir),
        "--limit",
        str(limit),
        "--quiet-tf-log",
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    if completed.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "reserved test image prediction failed",
                "stdout": completed.stdout[-2000:],
                "stderr": completed.stderr[-2000:],
            },
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail={"message": "prediction output was not JSON", "stdout": completed.stdout[-2000:]},
        ) from exc


@router.post("/{run_id}/test-dataset")
def test_dataset(run_id: str, dataset_path: str | None = None, limit: int = 100):
    model_dir = MODEL_DIR / run_id
    if not (model_dir / "model.keras").exists():
        raise HTTPException(status_code=400, detail=f"model.keras not found for run_id: {run_id}")
    if dataset_path:
        resolved_dataset_path = (PROJECT_ROOT / dataset_path).resolve()
    else:
        run_info = _read_run_info(model_dir)
        if not run_info:
            raise HTTPException(status_code=400, detail=f"run_info.json not found for run_id: {run_id}")
        resolved_dataset_path = Path(run_info["dataset_path"])
    if not (resolved_dataset_path / "dataset_info.json").exists():
        raise HTTPException(status_code=400, detail=f"dataset_info.json not found: {resolved_dataset_path}")
    command = [
        sys.executable,
        str(PROJECT_ROOT / "trainer" / "test_dataset.py"),
        "--model-dir",
        str(model_dir),
        "--dataset",
        str(resolved_dataset_path),
        "--limit",
        str(limit),
        "--quiet-tf-log",
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=180,
    )
    if completed.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "dataset test prediction failed",
                "stdout": completed.stdout[-2000:],
                "stderr": completed.stderr[-2000:],
            },
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail={"message": "prediction output was not JSON", "stdout": completed.stdout[-2000:]},
        ) from exc
