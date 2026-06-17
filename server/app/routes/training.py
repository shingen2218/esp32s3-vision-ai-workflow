import subprocess
import sys
import json
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..config import MODEL_DIR, PROJECT_ROOT
from ..espidf_service import idf_command_and_env, run_idf
from ..schemas import FirmwareBuildRequest, FirmwareFlashRequest, ModelExportRequest, TrainingStartRequest

router = APIRouter(prefix="/api/training", tags=["training"])
TRAINING_PROCESSES: dict[str, subprocess.Popen] = {}
EPOCH_PATTERN = re.compile(r"Epoch\s+(\d+)/(\d+)")
METRIC_PATTERN = re.compile(r"(accuracy|loss|val_accuracy|val_loss):\s*([0-9.]+)")
AI_MODEL_PARTITION_OFFSET = "0x310000"
AI_MODEL_PARTITION_SIZE = 0x300000


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
    try:
        data = json.loads(run_info_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


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


def _resolve_dataset_for_model(model_dir: Path, request_dataset_path: str | None) -> Path:
    if request_dataset_path:
        dataset_path = (PROJECT_ROOT / request_dataset_path).resolve()
    else:
        run_info = _read_run_info(model_dir)
        dataset_value = run_info.get("dataset_path") or run_info.get("dataset_path_relative")
        if not dataset_value:
            raise HTTPException(
                status_code=400,
                detail="dataset path is not known. Select a dataset before exporting TFLite.",
            )
        dataset_path = Path(dataset_value)
        if not dataset_path.is_absolute():
            dataset_path = (PROJECT_ROOT / dataset_path).resolve()
    if not (dataset_path / "dataset_info.json").exists():
        raise HTTPException(status_code=400, detail=f"dataset_info.json not found: {dataset_path}")
    return dataset_path


def _run_command(command: list[str], timeout: int, failure_message: str) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": failure_message,
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            },
        )
    return completed


def _c_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _write_model_labels_header(labels_path: Path, output_path: Path) -> list[str]:
    if not labels_path.exists():
        raise HTTPException(status_code=400, detail=f"labels.txt not found: {labels_path}")
    labels = [line.strip() for line in labels_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not labels:
        raise HTTPException(status_code=400, detail=f"labels.txt has no labels: {labels_path}")
    rows = "\n".join(f'    "{_c_string(label)}",' for label in labels)
    output_path.write_text(
        (
            "#pragma once\n\n"
            "#ifdef __cplusplus\n"
            'extern "C" {\n'
            "#endif\n\n"
            f"#define MODEL_LABEL_COUNT {len(labels)}\n\n"
            f"static const char *const MODEL_LABELS[MODEL_LABEL_COUNT] = {{\n{rows}\n}};\n\n"
            "#ifdef __cplusplus\n"
            "}\n"
            "#endif\n"
        ),
        encoding="utf-8",
    )
    return labels


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
                "has_float32_tflite": (model_dir / "model_float32.tflite").exists(),
                "has_int8_tflite": (model_dir / "model_int8.tflite").exists(),
                "has_c_array": (model_dir / "model_data.cc").exists() and (model_dir / "model_data.h").exists(),
                "has_ai_model_package": (model_dir / "ai_model.bin").exists(),
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


@router.post("/{run_id}/export-tflite")
def export_tflite(run_id: str, request: ModelExportRequest | None = None):
    model_dir = MODEL_DIR / run_id
    model_path = model_dir / "model.keras"
    if not model_path.exists():
        raise HTTPException(status_code=400, detail=f"model.keras not found for run_id: {run_id}")
    dataset_path = _resolve_dataset_for_model(model_dir, request.dataset_path if request else None)
    command = [
        sys.executable,
        str(PROJECT_ROOT / "trainer" / "export_tflite.py"),
        "--model",
        str(model_path),
        "--dataset",
        str(dataset_path),
        "--out-dir",
        str(model_dir),
        "--quiet-tf-log",
    ]
    completed = _run_command(command, timeout=600, failure_message="TFLite export failed")
    float_path = model_dir / "model_float32.tflite"
    int8_path = model_dir / "model_int8.tflite"
    return {
        "ok": True,
        "run_id": run_id,
        "dataset": str(dataset_path),
        "model_float32_tflite": str(float_path),
        "model_int8_tflite": str(int8_path),
        "model_float32_size": float_path.stat().st_size if float_path.exists() else None,
        "model_int8_size": int8_path.stat().st_size if int8_path.exists() else None,
        "stdout": completed.stdout[-2000:],
        "stderr": completed.stderr[-2000:],
    }


@router.post("/{run_id}/export-c-array")
def export_c_array(run_id: str):
    model_dir = MODEL_DIR / run_id
    int8_path = model_dir / "model_int8.tflite"
    if not int8_path.exists():
        raise HTTPException(status_code=400, detail=f"model_int8.tflite not found for run_id: {run_id}")
    model_cc = model_dir / "model_data.cc"
    model_h = model_dir / "model_data.h"
    labels_path = model_dir / "labels.txt"
    firmware_main = PROJECT_ROOT / "firmware" / "inference_classification" / "main"
    firmware_cc = firmware_main / "model_data.cc"
    firmware_h = firmware_main / "model_data.h"
    firmware_labels_h = firmware_main / "model_labels.h"
    command = [
        sys.executable,
        str(PROJECT_ROOT / "tools" / "convert_tflite_to_c_array.py"),
        "--input",
        str(int8_path),
        "--cc",
        str(model_cc),
        "--header",
        str(model_h),
    ]
    completed = _run_command(command, timeout=120, failure_message="C array export failed")
    firmware_main.mkdir(parents=True, exist_ok=True)
    firmware_cc.write_text(model_cc.read_text(encoding="utf-8"), encoding="utf-8")
    firmware_h.write_text(model_h.read_text(encoding="utf-8"), encoding="utf-8")
    labels = _write_model_labels_header(labels_path, firmware_labels_h)
    return {
        "ok": True,
        "run_id": run_id,
        "labels": labels,
        "model_data_cc": str(model_cc),
        "model_data_h": str(model_h),
        "firmware_model_data_cc": str(firmware_cc),
        "firmware_model_data_h": str(firmware_h),
        "firmware_model_labels_h": str(firmware_labels_h),
        "model_data_cc_size": model_cc.stat().st_size,
        "model_data_h_size": model_h.stat().st_size,
        "stdout": completed.stdout[-2000:],
        "stderr": completed.stderr[-2000:],
    }


@router.post("/{run_id}/export-ai-model-package")
def export_ai_model_package(run_id: str):
    model_dir = MODEL_DIR / run_id
    int8_path = model_dir / "model_int8.tflite"
    labels_path = model_dir / "labels.txt"
    if not int8_path.exists():
        raise HTTPException(status_code=400, detail=f"model_int8.tflite not found for run_id: {run_id}")
    if not labels_path.exists():
        raise HTTPException(status_code=400, detail=f"labels.txt not found for run_id: {run_id}")

    package_path = model_dir / "ai_model.bin"
    command = [
        sys.executable,
        str(PROJECT_ROOT / "tools" / "build_ai_model_package.py"),
        "--model",
        str(int8_path),
        "--labels",
        str(labels_path),
        "--output",
        str(package_path),
    ]
    completed = _run_command(command, timeout=120, failure_message="AI model package export failed")
    package_size = package_path.stat().st_size if package_path.exists() else 0
    if package_size <= 0:
        raise HTTPException(status_code=500, detail="ai_model.bin was not created")
    if package_size > AI_MODEL_PARTITION_SIZE:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "ai_model.bin is larger than the ai_model partition",
                "package_size": package_size,
                "partition_size": AI_MODEL_PARTITION_SIZE,
            },
        )
    return {
        "ok": True,
        "run_id": run_id,
        "ai_model_bin": str(package_path),
        "ai_model_size": package_size,
        "partition_offset": AI_MODEL_PARTITION_OFFSET,
        "partition_size": AI_MODEL_PARTITION_SIZE,
        "stdout": completed.stdout[-2000:],
        "stderr": completed.stderr[-2000:],
    }


@router.post("/{run_id}/prepare-inference-firmware")
def prepare_inference_firmware(run_id: str, request: ModelExportRequest | None = None):
    tflite_result = export_tflite(run_id, request)
    package_result = export_ai_model_package(run_id)
    return {
        "ok": True,
        "run_id": run_id,
        "steps": {
            "export_tflite": tflite_result,
            "export_ai_model_package": package_result,
        },
        "message": "ai_model.bin is ready to write",
    }


@router.post("/build-unified-camera-ai-firmware")
def build_unified_camera_ai_firmware(request: FirmwareBuildRequest | None = None):
    firmware_dir = PROJECT_ROOT / "firmware" / "capture_upload"
    commands = []
    if request and request.clean:
        commands.append(["fullclean"])
    commands.append(["build"])
    last_stdout = ""
    last_stderr = ""
    for args in commands:
        completed = run_idf(
            firmware_dir,
            args,
            timeout=900,
            failure_message=f"ESP-IDF command failed: {' '.join(args)}",
        )
        last_stdout = completed.stdout
        last_stderr = completed.stderr
    return {
        "ok": True,
        "firmware": str(firmware_dir),
        "message": "unified camera AI firmware build passed",
        "stdout": last_stdout[-4000:],
        "stderr": last_stderr[-4000:],
    }


@router.post("/build-inference-firmware")
def build_inference_firmware(request: FirmwareBuildRequest | None = None):
    firmware_dir = PROJECT_ROOT / "firmware" / "inference_classification"
    commands = []
    if request and request.clean:
        commands.append(["fullclean"])
    commands.append(["build"])
    last_stdout = ""
    last_stderr = ""
    for args in commands:
        completed = run_idf(
            firmware_dir,
            args,
            timeout=900,
            failure_message=f"ESP-IDF command failed: {' '.join(args)}",
        )
        last_stdout = completed.stdout
        last_stderr = completed.stderr
    return {
        "ok": True,
        "firmware": str(firmware_dir),
        "message": "inference firmware build passed",
        "stdout": last_stdout[-4000:],
        "stderr": last_stderr[-4000:],
    }


@router.post("/{run_id}/flash-ai-model")
def flash_ai_model(run_id: str, request: FirmwareFlashRequest):
    port = request.port.strip().upper()
    if not re.fullmatch(r"COM\d{1,3}", port):
        raise HTTPException(status_code=400, detail="port must look like COM5")

    model_dir = MODEL_DIR / run_id
    package_path = model_dir / "ai_model.bin"
    if not package_path.exists():
        export_ai_model_package(run_id)
    if not package_path.exists():
        raise HTTPException(status_code=400, detail=f"ai_model.bin not found for run_id: {run_id}")
    package_size = package_path.stat().st_size
    if package_size > AI_MODEL_PARTITION_SIZE:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "ai_model.bin is larger than the ai_model partition",
                "package_size": package_size,
                "partition_size": AI_MODEL_PARTITION_SIZE,
            },
        )

    idf_prefix, idf_env = idf_command_and_env()
    python_exe = idf_prefix[0] if idf_prefix and Path(idf_prefix[0]).name.lower().startswith("python") else sys.executable
    command = [
        python_exe,
        "-m",
        "esptool",
        "--chip",
        "esp32s3",
        "-p",
        port,
        "-b",
        "460800",
        "--before",
        "default_reset",
        "--after",
        "hard_reset",
        "write_flash",
        "--flash_mode",
        "dio",
        "--flash_freq",
        "80m",
        "--flash_size",
        "8MB",
        AI_MODEL_PARTITION_OFFSET,
        str(package_path),
    ]
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=300,
        env=idf_env,
    )
    if completed.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "failed to flash ai_model partition",
                "command": " ".join(command),
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            },
        )
    return {
        "ok": True,
        "run_id": run_id,
        "port": port,
        "partition": "ai_model",
        "offset": AI_MODEL_PARTITION_OFFSET,
        "ai_model_bin": str(package_path),
        "ai_model_size": package_size,
        "message": "ai_model partition flashed",
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


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
