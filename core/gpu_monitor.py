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

def check_comfyui(url: str = "http://127.0.0.1:8188") -> Dict[str, Any]:
    try:
        resp = requests.get(f"{url.rstrip('/')}/system_stats", timeout=1.5)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "online": True,
                "url": url,
                "devices": data.get("devices", [])
            }
    except Exception:
        pass
    return {
        "online": False,
        "url": url,
        "devices": []
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
