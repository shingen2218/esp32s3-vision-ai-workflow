import os
import shutil
import subprocess
from pathlib import Path

from fastapi import HTTPException


def idf_command_and_env() -> tuple[list[str], dict[str, str]]:
    env = os.environ.copy()
    idf_py = shutil.which("idf.py", path=env.get("PATH"))
    if idf_py:
        return [idf_py], env

    idf_path = Path("C:/Espressif/frameworks/esp-idf-v5.4.4")
    idf_python_env = Path("C:/Espressif/python_env/idf5.4_py3.11_env")
    idf_python = idf_python_env / "Scripts" / "python.exe"
    idf_py_script = idf_path / "tools" / "idf.py"
    if not idf_python.exists() or not idf_py_script.exists():
        raise HTTPException(
            status_code=500,
            detail={
                "message": "idf.py was not found",
                "hint": "Start the FastAPI server from an ESP-IDF PowerShell, or install ESP-IDF v5.4.4 in C:/Espressif.",
            },
        )

    tool_paths = [
        "C:/Espressif/tools/cmake/3.30.2/bin",
        "C:/Espressif/tools/ninja/1.12.1",
        "C:/Espressif/tools/xtensa-esp-elf/esp-14.2.0_20260121/xtensa-esp-elf/bin",
        "C:/Espressif/tools/riscv32-esp-elf/esp-14.2.0_20260121/riscv32-esp-elf/bin",
    ]
    env["IDF_PATH"] = str(idf_path)
    env["IDF_PYTHON_ENV_PATH"] = str(idf_python_env)
    env["IDF_TARGET"] = "esp32s3"
    env["ESP_ROM_ELF_DIR"] = "C:/Espressif/tools/esp-rom-elfs"
    env["PATH"] = os.pathsep.join(tool_paths + [env.get("PATH", "")])
    return [str(idf_python), str(idf_py_script)], env


def run_idf(
    firmware_dir: Path,
    args: list[str],
    timeout: int = 900,
    failure_message: str = "ESP-IDF command failed",
) -> subprocess.CompletedProcess[str]:
    idf_prefix, idf_env = idf_command_and_env()
    try:
        completed = subprocess.run(
            idf_prefix + args,
            cwd=firmware_dir,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=idf_env,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "idf.py was not found",
                "hint": "Start the FastAPI server from an ESP-IDF PowerShell, then try again.",
            },
        ) from exc
    if completed.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "message": failure_message,
                "command": " ".join(idf_prefix + args),
                "returncode": completed.returncode,
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            },
        )
    return completed
