import ipaddress
import re
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException

from ..config import PROJECT_ROOT
from ..espidf_service import idf_command_and_env, run_idf
from ..schemas import FirmwareFlashRequest, RemoteCameraRequest, WifiConfigUpdate

router = APIRouter(prefix="/api/firmware", tags=["firmware"])

FIRMWARE_PROJECTS = {
    "inference_classification": {
        "label": "Inference firmware",
        "path": PROJECT_ROOT / "firmware" / "inference_classification",
        "app_bin": "inference_classification.bin",
        "needs_model": False,
    },
    "capture_upload": {
        "label": "Capture upload firmware",
        "path": PROJECT_ROOT / "firmware" / "capture_upload",
        "app_bin": "capture_upload.bin",
        "needs_model": False,
    },
}

FLASH_TARGETS = {
    "inference_full": {
        "label": "Inference firmware full image",
        "firmware": "inference_classification",
        "files": [
            ("0x0", "build/bootloader/bootloader.bin"),
            ("0x8000", "build/partition_table/partition-table.bin"),
            ("0x10000", "build/inference_classification.bin"),
        ],
    },
    "inference_app": {
        "label": "Inference app only",
        "firmware": "inference_classification",
        "files": [("0x10000", "build/inference_classification.bin")],
    },
    "capture_full": {
        "label": "Capture upload firmware full image",
        "firmware": "capture_upload",
        "files": [
            ("0x0", "build/bootloader/bootloader.bin"),
            ("0x8000", "build/partition_table/partition-table.bin"),
            ("0x10000", "build/capture_upload.bin"),
        ],
    },
    "capture_app": {
        "label": "Capture upload app only",
        "firmware": "capture_upload",
        "files": [("0x10000", "build/capture_upload.bin")],
    },
}

CAPTURE_APP_CONFIG = PROJECT_ROOT / "firmware" / "capture_upload" / "main" / "app_config.h"
DEFINE_PATTERN = re.compile(r'^\s*#define\s+(WIFI_SSID|WIFI_PASSWORD|SERVER_UPLOAD_URL|DEVICE_ID)\s+"(.*)"\s*$')
NETSH_SSID_PATTERN = re.compile(r"^\s*SSID\s+\d+\s*:\s*(.+?)\s*$")
NETSH_CURRENT_SSID_PATTERN = re.compile(r"^\s*SSID\s*:\s*(.+?)\s*$")
CAMERA_READY_MARKER = "ESP32-S3 camera is ready"
GOT_IP_PATTERN = re.compile(r"got ip:\s*(\d+\.\d+\.\d+\.\d+)", re.IGNORECASE)
REMOTE_STARTED_PATTERN = re.compile(r"remote control server started", re.IGNORECASE)
REMOTE_CAMERA_PORT = 8080


def _private_ipv4(value: str) -> ipaddress.IPv4Address | None:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv4Address) and address.is_private and not address.is_loopback:
        return address
    return None


def _candidate_camera_networks() -> list[ipaddress.IPv4Network]:
    networks: list[ipaddress.IPv4Network] = []
    seen = set()

    def add_network(address: ipaddress.IPv4Address) -> None:
        network = ipaddress.ip_network(f"{address}/24", strict=False)
        if network not in seen:
            seen.add(network)
            networks.append(network)

    values = _read_app_config_values()
    upload_url = values.get("SERVER_UPLOAD_URL", "")
    hostname = urlparse(upload_url).hostname
    address = _private_ipv4(hostname or "")
    if address:
        add_network(address)

    try:
        host_name = socket.gethostname()
        for item in socket.getaddrinfo(host_name, None, socket.AF_INET):
            address = _private_ipv4(item[4][0])
            if address:
                add_network(address)
    except socket.gaierror:
        pass

    return networks


def _probe_camera_host(ip: str, timeout: float = 0.35) -> dict | None:
    try:
        with socket.create_connection((ip, REMOTE_CAMERA_PORT), timeout=timeout) as sock:
            sock.settimeout(timeout)
            request = f"GET / HTTP/1.0\r\nHost: {ip}:{REMOTE_CAMERA_PORT}\r\nConnection: close\r\n\r\n"
            sock.sendall(request.encode("ascii"))
            chunks = []
            while True:
                chunk = sock.recv(512)
                if not chunk:
                    break
                chunks.append(chunk)
                if sum(len(item) for item in chunks) >= 2048:
                    break
            response = b"".join(chunks).decode("utf-8", errors="replace")
    except OSError:
        return None
    if CAMERA_READY_MARKER not in response:
        return None
    return {
        "ip": ip,
        "url": f"http://{ip}:{REMOTE_CAMERA_PORT}",
        "port": REMOTE_CAMERA_PORT,
        "response": response.split("\r\n\r\n", 1)[-1].strip()[:200],
    }


def _read_camera_ip_from_monitor(port: str, firmware_dir: Path, timeout: int = 14) -> dict:
    idf_prefix, idf_env = idf_command_and_env()
    if len(idf_prefix) < 1:
        raise HTTPException(status_code=500, detail="ESP-IDF Python was not found")
    serial_reader = r"""
import re
import sys
import time

import serial

port = sys.argv[1]
timeout = float(sys.argv[2])
pattern = re.compile(r"got ip:\s*(\d+\.\d+\.\d+\.\d+)", re.IGNORECASE)
started = time.monotonic()
output = []

try:
    ser = serial.Serial(port, 115200, timeout=0.2)
except Exception as exc:
    print(f"SERIAL_OPEN_ERROR: {exc}")
    sys.exit(2)

try:
    # Reset through the USB serial control lines so boot logs include the Wi-Fi IP.
    ser.dtr = False
    ser.rts = True
    time.sleep(0.12)
    ser.rts = False
    time.sleep(0.12)

    found_ip = None
    while time.monotonic() - started < timeout:
        chunk = ser.read(512)
        if not chunk:
            continue
        text = chunk.decode("utf-8", errors="replace")
        output.append(text)
        joined = "".join(output)
        match = pattern.search(joined)
        if match and not found_ip:
            found_ip = match.group(1)
            print("GOT_IP:" + found_ip)
        if found_ip and "remote control server started" in joined:
            break
finally:
    try:
        ser.dtr = False
        ser.rts = False
    except Exception:
        pass
    ser.close()

print("".join(output)[-4000:])
"""
    command = [idf_prefix[0], "-c", serial_reader, port, str(timeout)]
    completed = subprocess.run(
        command,
        cwd=firmware_dir,
        text=True,
        capture_output=True,
        timeout=timeout + 5,
        env=idf_env,
    )
    output = (completed.stdout or "") + (completed.stderr or "")

    match = re.search(r"GOT_IP:(\d+\.\d+\.\d+\.\d+)", output) or GOT_IP_PATTERN.search(output or "")
    if not match:
        return {
            "found": False,
            "ip": None,
            "url": None,
            "stdout": (output or "")[-4000:],
            "command": " ".join(command),
            "returncode": completed.returncode,
        }
    ip = match.group(1)
    return {
        "found": True,
        "ip": ip,
        "url": f"http://{ip}:{REMOTE_CAMERA_PORT}",
        "port": REMOTE_CAMERA_PORT,
        "stdout": (output or "")[-4000:],
        "command": " ".join(command),
    }


def _escape_c_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _read_app_config_values() -> dict[str, str]:
    values = {
        "WIFI_SSID": "",
        "WIFI_PASSWORD": "",
        "SERVER_UPLOAD_URL": "",
        "DEVICE_ID": "",
    }
    if not CAPTURE_APP_CONFIG.exists():
        return values
    for line in CAPTURE_APP_CONFIG.read_text(encoding="utf-8", errors="replace").splitlines():
        match = DEFINE_PATTERN.match(line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def _write_app_config_values(values: dict[str, str]) -> None:
    CAPTURE_APP_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    CAPTURE_APP_CONFIG.write_text(
        (
            "#pragma once\n\n"
            f'#define WIFI_SSID "{_escape_c_string(values["WIFI_SSID"])}"\n'
            f'#define WIFI_PASSWORD "{_escape_c_string(values["WIFI_PASSWORD"])}"\n'
            f'#define SERVER_UPLOAD_URL "{_escape_c_string(values["SERVER_UPLOAD_URL"])}"\n'
            f'#define DEVICE_ID "{_escape_c_string(values["DEVICE_ID"])}"\n'
        ),
        encoding="utf-8",
    )


def _file_info(path: Path) -> dict:
    exists = path.exists()
    try:
        relative = str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        relative = str(path)
    return {
        "path": relative,
        "exists": exists,
        "size": path.stat().st_size if exists else None,
        "modified_at": path.stat().st_mtime if exists else None,
    }


def _serial_ports() -> list[dict]:
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        (
            "$ports = @(Get-CimInstance Win32_SerialPort | "
            "Select-Object @{Name='DeviceID';Expression={$_.DeviceID}},@{Name='Name';Expression={$_.Name}}); "
            "if ($ports.Count -eq 0) { "
            "$ports = [System.IO.Ports.SerialPort]::GetPortNames() | "
            "ForEach-Object { [pscustomobject]@{ DeviceID = $_; Name = $_ } } "
            "} "
            "$ports | ConvertTo-Json -Compress"
        ),
    ]
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, timeout=20)
    ports = []
    if completed.returncode == 0 and completed.stdout.strip():
        import json

        data = json.loads(completed.stdout)
        rows = data if isinstance(data, list) else [data]
        for row in rows:
            if row.get("DeviceID"):
                ports.append({"port": row["DeviceID"], "name": row.get("Name") or row["DeviceID"]})
    return ports


def _target_info(target_id: str) -> dict:
    target = FLASH_TARGETS[target_id]
    project = FIRMWARE_PROJECTS[target["firmware"]]
    firmware_dir = project["path"]
    files = []
    ready = True
    for address, relative_path in target["files"]:
        path = firmware_dir / relative_path
        info = _file_info(path)
        info["address"] = address
        info["relative_file"] = relative_path
        files.append(info)
        ready = ready and info["exists"]
    return {
        "id": target_id,
        "label": target["label"],
        "firmware": target["firmware"],
        "ready_to_flash": ready,
        "files": files,
    }


@router.get("/serial-ports")
def list_serial_ports():
    return {"ok": True, "ports": _serial_ports(), "stderr": ""}


@router.get("/wifi-config")
def read_wifi_config():
    values = _read_app_config_values()
    return {
        "ok": True,
        "config_path": str(CAPTURE_APP_CONFIG.relative_to(PROJECT_ROOT)),
        "ssid": values["WIFI_SSID"],
        "password": values["WIFI_PASSWORD"],
        "server_upload_url": values["SERVER_UPLOAD_URL"],
        "device_id": values["DEVICE_ID"],
        "password_set": bool(values["WIFI_PASSWORD"]),
    }


@router.get("/wifi-networks")
def list_wifi_networks():
    ssids = []
    seen = set()

    def add_ssid(ssid: str) -> None:
        ssid = ssid.strip()
        if ssid and ssid not in seen:
            seen.add(ssid)
            ssids.append(ssid)

    networks = subprocess.run(
        ["netsh", "wlan", "show", "networks"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=20,
    )
    if networks.returncode == 0:
        for line in networks.stdout.splitlines():
            match = NETSH_SSID_PATTERN.match(line)
            if match:
                add_ssid(match.group(1))

    interfaces = subprocess.run(
        ["netsh", "wlan", "show", "interfaces"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        timeout=20,
    )
    if interfaces.returncode == 0:
        for line in interfaces.stdout.splitlines():
            match = NETSH_CURRENT_SSID_PATTERN.match(line)
            if match and "BSSID" not in line:
                add_ssid(match.group(1))

    if not ssids:
        current = _read_app_config_values()["WIFI_SSID"]
        add_ssid(current)

    return {
        "ok": True,
        "ssids": ssids,
        "stderr": (networks.stderr + interfaces.stderr)[-1000:],
    }


@router.get("/discover-camera")
def discover_camera():
    networks = _candidate_camera_networks()
    if not networks:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "No private IPv4 network candidates were found.",
                "hint": "Make sure the Server URL uses the PC LAN IP, for example http://192.168.x.x:8000/api/images/upload.",
            },
        )

    hosts = []
    for network in networks:
        hosts.extend(str(host) for host in network.hosts())

    checked = 0
    with ThreadPoolExecutor(max_workers=96) as executor:
        future_to_ip = {executor.submit(_probe_camera_host, ip): ip for ip in hosts}
        for future in as_completed(future_to_ip):
            checked += 1
            result = future.result()
            if result:
                return {
                    "ok": True,
                    "found": True,
                    "camera": result,
                    "networks": [str(network) for network in networks],
                    "checked": checked,
                }

    return {
        "ok": True,
        "found": False,
        "camera": None,
        "networks": [str(network) for network in networks],
        "checked": checked,
        "message": "ESP32-S3 camera was not found on the scanned LAN ranges.",
    }


@router.get("/camera-ip-from-monitor")
def camera_ip_from_monitor(port: str):
    port = port.strip().upper()
    if not re.fullmatch(r"COM\d{1,3}", port):
        raise HTTPException(status_code=400, detail="port must look like COM5")
    firmware_dir = FIRMWARE_PROJECTS["capture_upload"]["path"]
    result = _read_camera_ip_from_monitor(port, firmware_dir, timeout=18)
    return {
        "ok": True,
        "found": result["found"],
        "camera": {"ip": result["ip"], "url": result["url"], "port": result.get("port")} if result["found"] else None,
        "monitor": result,
    }


@router.get("/camera-url")
def camera_url(port: str | None = None):
    firmware_dir = FIRMWARE_PROJECTS["capture_upload"]["path"]
    ports_to_try = []
    if port:
        candidate = port.strip().upper()
        if not re.fullmatch(r"COM\d{1,3}", candidate):
            raise HTTPException(status_code=400, detail="port must look like COM5")
        ports_to_try.append({"port": candidate, "name": candidate})
    else:
        ports_to_try = _serial_ports()

    monitor_results = []
    for item in ports_to_try:
        candidate = item["port"].strip().upper()
        result = _read_camera_ip_from_monitor(candidate, firmware_dir, timeout=18)
        monitor_results.append({"port": candidate, "result": result})
        if result["found"]:
            return {
                "ok": True,
                "found": True,
                "source": "monitor",
                "port": candidate,
                "camera": {"ip": result["ip"], "url": result["url"], "port": result.get("port")},
                "monitor": result,
                "tried_ports": [entry["port"] for entry in monitor_results],
            }

    discovery = discover_camera()
    if discovery.get("found") and discovery.get("camera"):
        return {
            "ok": True,
            "found": True,
            "source": "lan-scan",
            "port": None,
            "camera": discovery["camera"],
            "monitor_results": monitor_results,
            "discovery": discovery,
            "tried_ports": [entry["port"] for entry in monitor_results],
        }

    return {
        "ok": True,
        "found": False,
        "camera": None,
        "monitor_results": monitor_results,
        "discovery": discovery,
        "tried_ports": [entry["port"] for entry in monitor_results],
        "message": "ESP32-S3 camera URL was not found from serial monitor or LAN scan.",
    }


@router.post("/remote-capture")
def remote_capture(request: RemoteCameraRequest):
    base_url = request.base_url.strip().rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=400, detail="base_url must look like http://192.168.11.57:8080")

    capture_url = f"{base_url}/capture"
    try:
        http_request = Request(capture_url, method="GET", headers={"User-Agent": "esp32s3-vision-workflow"})
        with urlopen(http_request, timeout=18) as response:
            body = response.read(4096).decode("utf-8", errors="replace")
            status = response.status
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "failed to call ESP32-S3 /capture",
                "url": capture_url,
                "error": str(exc),
                "hint": "Check that capture_upload firmware is running and the ESP32-S3 URL is reachable from this PC.",
            },
        ) from exc

    if status < 200 or status >= 300:
        raise HTTPException(
            status_code=502,
            detail={"message": "ESP32-S3 /capture returned an error", "url": capture_url, "status": status, "body": body},
        )

    return {"ok": True, "url": capture_url, "status": status, "body": body}


@router.post("/wifi-config")
def update_wifi_config(request: WifiConfigUpdate):
    values = _read_app_config_values()
    values["WIFI_SSID"] = request.ssid.strip()
    if request.password is not None and request.password != "":
        values["WIFI_PASSWORD"] = request.password
    values["SERVER_UPLOAD_URL"] = request.server_upload_url.strip()
    values["DEVICE_ID"] = request.device_id.strip()
    _write_app_config_values(values)
    return {
        "ok": True,
        "config_path": str(CAPTURE_APP_CONFIG.relative_to(PROJECT_ROOT)),
        "ssid": values["WIFI_SSID"],
        "password": values["WIFI_PASSWORD"],
        "server_upload_url": values["SERVER_UPLOAD_URL"],
        "device_id": values["DEVICE_ID"],
        "password_set": bool(values["WIFI_PASSWORD"]),
        "message": "Wi-Fi config saved. Build and write capture_upload firmware to apply it.",
    }


@router.get("/inference/artifacts")
def inference_artifacts():
    return firmware_artifacts("inference_classification")


@router.get("/artifacts")
def all_firmware_artifacts():
    return {
        "ok": True,
        "firmwares": [
            firmware_artifacts(name)["firmware"]
            for name in FIRMWARE_PROJECTS
        ],
        "flash_targets": [_target_info(target_id) for target_id in FLASH_TARGETS],
    }


def firmware_artifacts(firmware_name: str):
    project = FIRMWARE_PROJECTS.get(firmware_name)
    if not project:
        raise HTTPException(status_code=400, detail=f"unknown firmware: {firmware_name}")
    firmware_dir = project["path"]
    build_dir = firmware_dir / "build"
    files = {
        "bootloader_bin": _file_info(build_dir / "bootloader" / "bootloader.bin"),
        "partition_table_bin": _file_info(build_dir / "partition_table" / "partition-table.bin"),
        "app_bin": _file_info(build_dir / project["app_bin"]),
    }
    if project["needs_model"]:
        files["model_data_cc"] = _file_info(firmware_dir / "main" / "model_data.cc")
        files["model_data_h"] = _file_info(firmware_dir / "main" / "model_data.h")
    ready_to_flash = all(item["exists"] for item in files.values())
    return {
        "ok": True,
        "ready_to_flash": ready_to_flash,
        "files": files,
        "firmware": {
            "name": firmware_name,
            "label": project["label"],
            "path": str(firmware_dir.relative_to(PROJECT_ROOT)),
            "ready_to_flash": ready_to_flash,
            "files": files,
        },
    }


def _build_firmware_if_needed(firmware_name: str) -> dict:
    project = FIRMWARE_PROJECTS.get(firmware_name)
    if not project:
        raise HTTPException(status_code=400, detail=f"unknown firmware: {firmware_name}")
    firmware_dir = project["path"]
    if project["needs_model"]:
        model_cc = firmware_dir / "main" / "model_data.cc"
        model_h = firmware_dir / "main" / "model_data.h"
        if not model_cc.exists() or not model_h.exists():
            raise HTTPException(
                status_code=400,
                detail="model_data.cc/h are missing. Run Prepare ESP32-S3 firmware first.",
            )
    build = run_idf(
        firmware_dir,
        ["build"],
        timeout=900,
        failure_message=f"failed to build {firmware_name}",
    )
    return {
        "build_stdout": build.stdout[-2000:],
        "build_stderr": build.stderr[-2000:],
    }


@router.post("/inference/flash")
def flash_inference_firmware(request: FirmwareFlashRequest):
    port = request.port.strip().upper()
    if not re.fullmatch(r"COM\d{1,3}", port):
        raise HTTPException(status_code=400, detail="port must look like COM5")
    firmware_name = request.firmware
    project = FIRMWARE_PROJECTS.get(firmware_name)
    if not project:
        raise HTTPException(status_code=400, detail=f"unknown firmware: {firmware_name}")
    artifacts = firmware_artifacts(firmware_name)
    if not artifacts["ready_to_flash"]:
        _build_firmware_if_needed(firmware_name)
        artifacts = firmware_artifacts(firmware_name)
    if not artifacts["ready_to_flash"]:
        raise HTTPException(status_code=400, detail=f"{firmware_name} artifacts are still missing after build.")

    firmware_dir = project["path"]
    completed = run_idf(
        firmware_dir,
        ["-p", port, "flash"],
        timeout=300,
        failure_message=f"failed to flash {firmware_name} to {port}",
    )
    return {
        "ok": True,
        "port": port,
        "firmware": firmware_name,
        "message": f"{firmware_name} flashed",
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }


@router.post("/flash-selected")
def flash_selected_files(request: FirmwareFlashRequest):
    port = request.port.strip().upper()
    if not re.fullmatch(r"COM\d{1,3}", port):
        raise HTTPException(status_code=400, detail="port must look like COM5")
    target_id = request.target or "inference_full"
    target = FLASH_TARGETS.get(target_id)
    if not target:
        raise HTTPException(status_code=400, detail=f"unknown flash target: {target_id}")

    project = FIRMWARE_PROJECTS[target["firmware"]]
    firmware_dir = project["path"]

    build_result = None
    target_info = _target_info(target_id)
    if request.force_build or not target_info["ready_to_flash"]:
        build_result = _build_firmware_if_needed(target["firmware"])
        target_info = _target_info(target_id)
    if not target_info["ready_to_flash"]:
        raise HTTPException(status_code=400, detail=f"selected files are still missing after build: {target_id}")

    flash_target = "app-flash" if target_id.endswith("_app") else "flash"
    completed = run_idf(
        firmware_dir,
        ["-p", port, flash_target],
        timeout=300,
        failure_message=f"failed to flash {target_info['label']} to {port}",
    )
    camera = None
    if target["firmware"] == "capture_upload":
        camera = _read_camera_ip_from_monitor(port, firmware_dir)
    return {
        "ok": True,
        "port": port,
        "target": target_info,
        "camera": camera,
        "build": build_result,
        "force_build": request.force_build,
        "message": f"flashed {target_info['label']} to {port}",
        "stdout": completed.stdout[-4000:],
        "stderr": completed.stderr[-4000:],
    }
