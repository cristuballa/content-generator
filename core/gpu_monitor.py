import sys
import subprocess
import shutil
import psutil
import requests
from typing import Dict, Any, List

def get_gpu_stats() -> List[Dict[str, Any]]:
    gpus = []
    if not shutil.which("nvidia-smi"):
        return gpus
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=index,name,memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu",
            "--format=csv,noheader,nounits"
        ]
        creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=3, creationflags=creationflags)
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 7:
                total = int(parts[2])
                used = int(parts[3])
                pct = round((used / total * 100), 1) if total > 0 else 0
                gpus.append({
                    "index": int(parts[0]),
                    "name": parts[1],
                    "total_mb": total,
                    "used_mb": used,
                    "free_mb": int(parts[4]),
                    "percent": pct,
                    "temperature": int(parts[5]),
                    "utilization": int(parts[6])
                })
    except Exception as e:
        print(f"[GPU Monitor] Failed to query nvidia-smi: {e}")
    return gpus

import socket
import time
from urllib.parse import urlparse

# In-memory status cache for graceful debouncing
_last_comfy_state = {
    "online": False,
    "busy": False,
    "status": "offline",
    "last_seen": 0,
    "devices": []
}

def _is_port_listening(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        res = s.connect_ex((host, port))
        s.close()
        return res == 0
    except Exception:
        return False

def _is_comfy_process_running() -> bool:
    try:
        for proc in psutil.process_iter(['name', 'cmdline']):
            name = (proc.info.get('name') or '').lower()
            if 'python' in name:
                cmdline = ' '.join(proc.info.get('cmdline') or [])
                if 'main.py' in cmdline and ('8188' in cmdline or 'ComfyUI' in cmdline):
                    return True
    except Exception:
        pass
    return False

def check_comfyui(url: str = "http://127.0.0.1:8188") -> Dict[str, Any]:
    global _last_comfy_state
    now = time.time()

    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8188

    port_open = _is_port_listening(host, port)
    proc_running = _is_comfy_process_running() if not port_open else True

    if not port_open and not proc_running:
        # Check grace period (within 4 seconds of being active to prevent flickers during heavy CUDA sync)
        if now - _last_comfy_state["last_seen"] < 4.0 and _last_comfy_state["online"]:
            return {
                "online": True,
                "busy": True,
                "status": "busy",
                "url": url,
                "devices": _last_comfy_state["devices"]
            }
        _last_comfy_state["online"] = False
        _last_comfy_state["busy"] = False
        _last_comfy_state["status"] = "offline"
        return {
            "online": False,
            "busy": False,
            "status": "offline",
            "url": url,
            "devices": []
        }

    # Port is open or process is alive
    _last_comfy_state["last_seen"] = now
    is_busy = False
    devices = _last_comfy_state.get("devices", [])

    # Try HTTP check with short timeout to detect if busy or idle
    base_url = url.rstrip('/')
    try:
        # Check /prompt endpoint for active queue/generation
        resp = requests.get(f"{base_url}/prompt", timeout=1.0)
        if resp.status_code == 200:
            p_data = resp.json()
            remaining = p_data.get("exec_info", {}).get("queue_remaining", 0)
            if remaining > 0:
                is_busy = True
    except requests.exceptions.Timeout:
        # Timeout during HTTP call when port is open strongly indicates heavy GPU/GIL load
        is_busy = True
    except Exception:
        pass

    # Query system stats if not already busy
    if not is_busy:
        try:
            resp_stats = requests.get(f"{base_url}/system_stats", timeout=1.0)
            if resp_stats.status_code == 200:
                s_data = resp_stats.json()
                devices = s_data.get("devices", devices)
        except requests.exceptions.Timeout:
            is_busy = True
        except Exception:
            pass

    _last_comfy_state.update({
        "online": True,
        "busy": is_busy,
        "status": "busy" if is_busy else "online",
        "devices": devices
    })

    return {
        "online": True,
        "busy": is_busy,
        "status": "busy" if is_busy else "online",
        "url": url,
        "devices": devices
    }

def get_system_stats(comfyui_url: str = "http://127.0.0.1:8188") -> Dict[str, Any]:
    mem = psutil.virtual_memory()
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_total_gb": round(mem.total / (1024**3), 2),
        "ram_used_gb": round(mem.used / (1024**3), 2),
        "ram_percent": mem.percent,
        "gpus": get_gpu_stats(),
        "comfyui": check_comfyui(comfyui_url)
    }
