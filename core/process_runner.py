import asyncio
import os
import sys
import time
import subprocess
import psutil
from collections import deque
from pathlib import Path
from typing import Dict, Any, Optional, List, Set
from fastapi import WebSocket

class ProcessRunner:
    def __init__(self, max_log_history: int = 2500):
        self.max_log_history = max_log_history
        self.logs: deque = deque(maxlen=max_log_history)
        self.current_process: Optional[asyncio.subprocess.Process] = None
        self.current_pid: Optional[int] = None
        self.current_job_info: Optional[Dict[str, Any]] = None
        self.status: str = "idle"  # idle, running, completed, error, stopped
        self.active_websockets: Set[WebSocket] = set()
        self._task: Optional[asyncio.Task] = None

    async def connect_ws(self, ws: WebSocket):
        await ws.accept()
        self.active_websockets.add(ws)
        # Send current status and backlog
        await ws.send_json({
            "type": "init",
            "status": self.status,
            "job": self.current_job_info,
            "logs": list(self.logs)
        })

    def disconnect_ws(self, ws: WebSocket):
        self.active_websockets.discard(ws)

    async def broadcast(self, message: Dict[str, Any]):
        dead_ws = set()
        for ws in self.active_websockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead_ws.add(ws)
        for ws in dead_ws:
            self.active_websockets.discard(ws)

    def log(self, line: str, stream: str = "stdout"):
        entry = {
            "timestamp": time.strftime("%H:%M:%S"),
            "line": line.rstrip("\r\n"),
            "stream": stream
        }
        self.logs.append(entry)
        # Schedule broadcast
        asyncio.create_task(self.broadcast({"type": "log", "entry": entry}))

    def clear_logs(self):
        self.logs.clear()
        asyncio.create_task(self.broadcast({"type": "clear_logs"}))

def resolve_python_runtime(cwd: Optional[str] = None) -> str:
    """Find the optimal Python environment for pipeline execution.
    Prioritizes project venvs and ComfyUI PyTorch/CUDA environments over global python."""
    if cwd:
        p_dir = Path(cwd)
        # Check direct project venvs (e.g. .venv, venv, .venv_vibevoice)
        for venv_name in [".venv", "venv", ".venv_vibevoice"]:
            py_cand = p_dir / venv_name / "Scripts" / "python.exe"
            if py_cand.exists():
                return str(py_cand.resolve())

    # ComfyUI shared AI venv with PyTorch, CUDA, Whisper, Torchvision
    comfy_py = Path(r"C:\Users\User\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe")
    if comfy_py.exists():
        return str(comfy_py.resolve())

    # Fallback to server Python binary (ensure python.exe instead of pythonw.exe)
    curr = Path(sys.executable)
    if curr.stem.lower() == "pythonw":
        py_cand = curr.parent / "python.exe"
        if py_cand.exists():
            return str(py_cand.resolve())
    return str(curr.resolve())

class ProcessRunner:
    def __init__(self, max_log_history: int = 2500):
        self.max_log_history = max_log_history
        self.logs: deque = deque(maxlen=max_log_history)
        self.current_process: Optional[asyncio.subprocess.Process] = None
        self.current_pid: Optional[int] = None
        self.current_job_info: Optional[Dict[str, Any]] = None
        self.status: str = "idle"  # idle, running, completed, error, stopped
        self.active_websockets: Set[WebSocket] = set()
        self._task: Optional[asyncio.Task] = None

    async def connect_ws(self, ws: WebSocket):
        await ws.accept()
        self.active_websockets.add(ws)
        # Send current status and backlog
        await ws.send_json({
            "type": "init",
            "status": self.status,
            "job": self.current_job_info,
            "logs": list(self.logs)
        })

    def disconnect_ws(self, ws: WebSocket):
        self.active_websockets.discard(ws)

    async def broadcast(self, message: Dict[str, Any]):
        dead_ws = set()
        for ws in self.active_websockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead_ws.add(ws)
        for ws in dead_ws:
            self.active_websockets.discard(ws)

    def log(self, line: str, stream: str = "stdout"):
        entry = {
            "timestamp": time.strftime("%H:%M:%S"),
            "line": line.rstrip("\r\n"),
            "stream": stream
        }
        self.logs.append(entry)
        # Schedule broadcast
        asyncio.create_task(self.broadcast({"type": "log", "entry": entry}))

    def clear_logs(self):
        self.logs.clear()
        asyncio.create_task(self.broadcast({"type": "clear_logs"}))

    async def run_script(self, script_path: str, cwd: str, args: List[str] = None, python_exe: Optional[str] = None) -> Dict[str, Any]:
        if self.status == "running":
            return {"success": False, "error": "A process is already running. Please stop it first."}

        python_bin = python_exe or resolve_python_runtime(cwd)
        args = args or []
        script_name = Path(script_path).name
        cmd = [python_bin, "-u", str(script_path)] + args

        self.status = "running"
        self.current_job_info = {
            "script": script_name,
            "script_path": str(script_path),
            "python_exe": python_bin,
            "cwd": cwd,
            "args": args,
            "cmd_display": f"python {script_name} {' '.join(args)}".strip(),
            "start_time": time.time()
        }

        self.log(f"=== [PROCESS START] {time.strftime('%Y-%m-%d %H:%M:%S')} ===", stream="system")
        self.log(f"Working Directory: {cwd}", stream="system")
        self.log(f"Python Runtime:    {python_bin}", stream="system")
        self.log(f"Command:           {self.current_job_info['cmd_display']}", stream="system")
        self.log("=" * 60, stream="system")

        await self.broadcast({
            "type": "status",
            "status": self.status,
            "job": self.current_job_info
        })

        self._task = asyncio.create_task(self._execute_subprocess(cmd, cwd))
        return {"success": True, "job": self.current_job_info}

    async def _execute_subprocess(self, cmd: List[str], cwd: str):
        try:
            # Set unbuffered env
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"

            # Inject runner_hooks via PYTHONPATH to automatically suppress popup shell windows in all descendants
            hooks_dir = str((Path(__file__).parent / "runner_hooks").resolve())
            orig_pp = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = f"{hooks_dir};{orig_pp}" if orig_pp else hooks_dir

            # Ensure Python scripts directory and project root are in PATH
            py_bin = Path(cmd[0])
            if py_bin.exists():
                py_scripts = py_bin.parent
                orig_path = env.get("PATH", "")
                env["PATH"] = f"{py_scripts};{py_scripts.parent};{cwd};{orig_path}"

            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            self.current_process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                creationflags=creationflags
            )
            self.current_pid = self.current_process.pid
            if self.current_job_info:
                self.current_job_info["pid"] = self.current_pid
                await self.broadcast({"type": "pid", "pid": self.current_pid})

            async def read_stream(stream, stream_name):
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    decoded = line.decode("utf-8", errors="replace")
                    self.log(decoded, stream=stream_name)

            await asyncio.gather(
                read_stream(self.current_process.stdout, "stdout"),
                read_stream(self.current_process.stderr, "stderr")
            )

            exit_code = await self.current_process.wait()
            duration = round(time.time() - self.current_job_info["start_time"], 1)

            if self.status != "stopped":
                if exit_code == 0:
                    self.status = "completed"
                    self.log(f"=== [PROCESS COMPLETED SUCCESSFULLY] Exit Code: 0 | Duration: {duration}s ===", stream="system")
                else:
                    self.status = "error"
                    self.log(f"=== [PROCESS FAILED] Exit Code: {exit_code} | Duration: {duration}s ===", stream="error")

        except asyncio.CancelledError:
            self.status = "stopped"
            self.log("=== [PROCESS ABORTED BY USER] ===", stream="system")
        except Exception as e:
            self.status = "error"
            self.log(f"=== [PROCESS EXECUTION ERROR]: {e} ===", stream="error")
        finally:
            self.current_process = None
            self.current_pid = None
            await self.broadcast({
                "type": "status",
                "status": self.status,
                "job": self.current_job_info
            })

    async def stop(self) -> Dict[str, Any]:
        if self.status != "running" or not self.current_pid:
            return {"success": False, "message": "No process currently running."}

        pid = self.current_pid
        self.status = "stopped"
        self.log(f"!!! [STOP REQUEST RECEIVED] Terminating process tree for PID {pid}... !!!", stream="system")

        killed_count = 0
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            for child in children:
                try:
                    child.kill()
                    killed_count += 1
                except Exception:
                    pass
            parent.kill()
            killed_count += 1
        except psutil.NoSuchProcess:
            pass
        except Exception as e:
            self.log(f"psutil termination exception: {e}, falling back to taskkill", stream="system")
            try:
                creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, creationflags=creationflags)
            except Exception:
                pass

        if self._task and not self._task.done():
            self._task.cancel()

        self.current_process = None
        self.current_pid = None
        self.log(f"!!! [PROCESS STOPPED] Killed {killed_count} process(es) safely. GPU & file locks released. !!!", stream="system")

        await self.broadcast({
            "type": "status",
            "status": "stopped",
            "job": self.current_job_info
        })
        return {"success": True, "killed_processes": killed_count}

process_runner = ProcessRunner()
