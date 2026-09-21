"""
KCT Studio System Tray Controller & Boot Auto-Launcher
Runs the FastAPI server silently in background on boot with a system tray icon.
Allows Start, Stop, Restart, Open Dashboard, and Boot Auto-Start toggle from Windows System Tray.
"""
import sys
import os
import time
import json
import socket
import logging
import ctypes
import threading
import subprocess
import webbrowser
from pathlib import Path
import winreg
from ctypes import wintypes

import psutil
import pystray
from PIL import Image, ImageDraw

REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
REG_APP_NAME = "KCTStudioPipeline"
MUTEX_NAME = "Local\\KCTStudioTrayAppMutex"


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ('cb', wintypes.DWORD),
        ('lpReserved', wintypes.LPWSTR),
        ('lpDesktop', wintypes.LPWSTR),
        ('lpTitle', wintypes.LPWSTR),
        ('dwX', wintypes.DWORD),
        ('dwY', wintypes.DWORD),
        ('dwXSize', wintypes.DWORD),
        ('dwYSize', wintypes.DWORD),
        ('dwXCountChars', wintypes.DWORD),
        ('dwYCountChars', wintypes.DWORD),
        ('dwFillAttribute', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('wShowWindow', wintypes.WORD),
        ('cbReserved2', wintypes.WORD),
        ('lpReserved2', ctypes.c_void_p),
        ('hStdInput', wintypes.HANDLE),
        ('hStdOutput', wintypes.HANDLE),
        ('hStdError', wintypes.HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ('hProcess', wintypes.HANDLE),
        ('hThread', wintypes.HANDLE),
        ('dwProcessId', wintypes.DWORD),
        ('dwThreadId', wintypes.DWORD),
    ]


def ensure_interactive_desktop():
    """
    Ensure the tray app runs on the interactive WinSta0\\Default desktop
    so its tray icon can attach to Explorer.exe (Shell_TrayWnd).
    If running in a separate isolated desktop, relaunches itself on Default.
    """
    if sys.platform != "win32":
        return

    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        h_desk = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
        buf = ctypes.create_unicode_buffer(256)
        user32.GetUserObjectInformationW(h_desk, 2, buf, 256, None)
        cur_desk = buf.value.strip().lower()

        if cur_desk != "default":
            py = Path(sys.executable)
            pyw = py.parent / "pythonw.exe"
            exe = str(pyw) if pyw.exists() else str(py)
            script = str(Path(__file__).resolve())
            cmd = f'"{exe}" "{script}"'
            for arg in sys.argv[1:]:
                cmd += f' "{arg}"'

            si = STARTUPINFOW()
            si.cb = ctypes.sizeof(STARTUPINFOW)
            si.lpDesktop = "WinSta0\\Default"
            pi = PROCESS_INFORMATION()

            CREATE_NO_WINDOW = 0x08000000
            res = kernel32.CreateProcessW(
                None, cmd, None, None, False, CREATE_NO_WINDOW, None, None,
                ctypes.byref(si), ctypes.byref(pi)
            )
            if res:
                kernel32.CloseHandle(pi.hProcess)
                kernel32.CloseHandle(pi.hThread)
            sys.exit(0)
    except Exception:
        pass


def terminate_stale_instances():
    """Terminates any other running tray_app.py instances (except this process)."""
    current_pid = os.getpid()
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if proc.info['pid'] == current_pid:
            continue
        try:
            name = (proc.info['name'] or '').lower()
            if 'python' in name:
                cmdline = ' '.join(proc.info['cmdline'] or [])
                if 'tray_app.py' in cmdline:
                    proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    time.sleep(0.5)


def setup_logging(log_file: Path):
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    def excepthook(exc_type, exc_value, exc_traceback):
        logging.error("Uncaught exception:", exc_info=(exc_type, exc_value, exc_traceback))
        sys.__excepthook__(exc_type, exc_value, exc_traceback)

    sys.excepthook = excepthook


class KCTStudioTrayApp:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent
        self.app_py = self.base_dir / "app.py"
        self.log_dir = self.base_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.server_log = self.log_dir / "server.log"
        self.tray_log = self.log_dir / "tray.log"

        self.server_process = None
        self.server_status = "checking"  # "running", "stopped", "starting", "stopping"

        # Load configuration
        self.port, self.scheme, self.dashboard_url = self._get_server_config()

        # Generate dynamic tray icons (Online: Green dot, Offline: Red dot, Starting: Amber dot)
        self.icon_online, self.icon_offline, self.icon_starting = self._generate_icons()

        # Initialize pystray Icon
        self.icon = pystray.Icon(
            name="KCTStudio",
            icon=self.icon_starting,
            title="KCT Studio - Initializing...",
            menu=self._build_menu()
        )

    def _get_server_config(self):
        port = 7860
        ssl_enabled = True
        cfg_file = self.base_dir / "config.json"
        if cfg_file.exists():
            try:
                data = json.loads(cfg_file.read_text(encoding="utf-8"))
                srv = data.get("server", {})
                port = srv.get("port", 7860)
                ssl_enabled = srv.get("ssl_enabled", True)
            except Exception:
                pass
        scheme = "https" if ssl_enabled else "http"
        return port, scheme, f"{scheme}://127.0.0.1:{port}"

    def _generate_icons(self):
        fav = self.base_dir / "static" / "favicon.png"
        if fav.exists():
            try:
                base = Image.open(fav).convert("RGBA").resize((64, 64), Image.Resampling.LANCZOS)
            except Exception:
                base = self._create_fallback_icon()
        else:
            base = self._create_fallback_icon()

        # Online Icon (Vibrant Green Status Dot)
        online = base.copy()
        d_on = ImageDraw.Draw(online)
        d_on.ellipse((38, 38, 62, 62), fill=(16, 185, 129, 255), outline=(10, 12, 16, 255), width=2)

        # Offline Icon (Subtle Muted / Red Status Dot)
        offline = base.copy()
        gray = offline.convert("L").convert("RGBA")
        offline = Image.blend(offline, gray, 0.45)
        d_off = ImageDraw.Draw(offline)
        d_off.ellipse((38, 38, 62, 62), fill=(239, 68, 68, 255), outline=(10, 12, 16, 255), width=2)

        # Starting Icon (Amber Status Dot)
        starting = base.copy()
        d_start = ImageDraw.Draw(starting)
        d_start.ellipse((38, 38, 62, 62), fill=(245, 158, 11, 255), outline=(10, 12, 16, 255), width=2)

        return online, offline, starting

    def _create_fallback_icon(self):
        img = Image.new("RGBA", (64, 64), (18, 22, 32, 255))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((4, 4, 60, 60), radius=12, fill=(24, 30, 44, 255), outline=(255, 230, 20, 255), width=3)
        d.text((20, 16), "K", fill=(255, 230, 20, 255))
        return img

    def is_server_listening(self) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.6)
        try:
            s.connect(("127.0.0.1", self.port))
            s.close()
            return True
        except Exception:
            return False

    def is_startup_enabled(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ) as key:
                val, _ = winreg.QueryValueEx(key, REG_APP_NAME)
                return bool(val)
        except Exception:
            return False

    def toggle_startup(self, icon=None, item=None):
        currently_enabled = self.is_startup_enabled()
        new_state = not currently_enabled
        self.set_startup_enabled(new_state)
        if self.icon:
            self.icon.update_menu()
            if new_state:
                self.icon.notify("KCT Studio will automatically start when Windows boots.", "Auto-Start Enabled")
            else:
                self.icon.notify("KCT Studio auto-start on boot has been disabled.", "Auto-Start Disabled")

    def set_startup_enabled(self, enable: bool):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE) as key:
                if enable:
                    py = Path(sys.executable)
                    pyw = py.parent / "pythonw.exe"
                    exe = str(pyw) if pyw.exists() else str(py)
                    script = str(Path(__file__).resolve())
                    cmd = f'"{exe}" "{script}"'
                    winreg.SetValueEx(key, REG_APP_NAME, 0, winreg.REG_SZ, cmd)
                    logging.info("Registered startup command in registry: %s", cmd)
                else:
                    try:
                        winreg.DeleteValue(key, REG_APP_NAME)
                        logging.info("Removed startup command from registry.")
                    except FileNotFoundError:
                        pass
        except Exception as e:
            logging.error(f"Registry startup configuration error: {e}")

    def start_server(self, notify=True):
        if self.is_server_listening():
            self._update_state("running")
            return

        self._update_state("starting")
        logging.info("Launching backend server (app.py)...")

        def _launch():
            try:
                py = Path(sys.executable)
                pyw = py.parent / "pythonw.exe"
                exe = str(pyw) if pyw.exists() else str(py)

                with open(self.server_log, "a", encoding="utf-8") as out:
                    out.write(f"\n=== [SERVER LAUNCHED BY TRAY] {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                    out.flush()
                    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                    self.server_process = subprocess.Popen(
                        [exe, str(self.app_py)],
                        cwd=str(self.base_dir),
                        stdin=subprocess.DEVNULL,
                        stdout=out,
                        stderr=out,
                        creationflags=creationflags
                    )

                # Wait up to 30 seconds for port to open
                for _ in range(60):
                    time.sleep(0.5)
                    if self.is_server_listening():
                        self._update_state("running")
                        logging.info("Backend server is listening at %s", self.dashboard_url)
                        if notify and self.icon:
                            self.icon.notify(f"Server is online at {self.dashboard_url}", "KCT Studio Online")
                        return
                    if self.server_process.poll() is not None:
                        logging.error("Server process exited unexpectedly with code %s", self.server_process.returncode)
                        break

                self._update_state("stopped")
                logging.warning("Server start timed out.")
            except Exception as e:
                self._update_state("stopped")
                logging.error("Failed to start server: %s", e, exc_info=True)
                if self.icon:
                    self.icon.notify(f"Failed to start server: {e}", "Server Error")

        threading.Thread(target=_launch, daemon=True).start()

    def stop_server(self, notify=True):
        self._update_state("stopping")
        logging.info("Stopping backend server...")

        def _terminate():
            # 1. Terminate tracked subprocess
            if self.server_process and self.server_process.poll() is None:
                try:
                    self.server_process.terminate()
                    self.server_process.wait(timeout=2)
                except Exception:
                    try:
                        self.server_process.kill()
                    except Exception:
                        pass

            # 2. Free port 7860 forcefully if anything is still listening
            self._free_port(self.port)
            self.server_process = None
            self._update_state("stopped")
            logging.info("Backend server stopped.")
            if notify and self.icon:
                self.icon.notify("KCT Studio Server has stopped. Port freed.", "Server Stopped")

        threading.Thread(target=_terminate, daemon=True).start()

    def restart_server(self):
        def _restart():
            self.stop_server(notify=False)
            time.sleep(1.5)
            self.start_server(notify=True)

        threading.Thread(target=_restart, daemon=True).start()

    def _free_port(self, port: int):
        current_pid = os.getpid()
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['pid'] == current_pid:
                continue
            try:
                conns = getattr(proc, 'net_connections', proc.connections)('inet')
                for conn in conns:
                    if conn.laddr.port == port:
                        logging.info("Killing process PID %s (%s) holding port %s", proc.info['pid'], proc.info['name'], port)
                        proc.kill()
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        time.sleep(0.5)

    def open_dashboard(self, icon=None, item=None):
        if not self.is_server_listening():
            self.start_server(notify=True)
            time.sleep(1.2)
        webbrowser.open(self.dashboard_url)

    def view_logs(self, icon=None, item=None):
        if self.server_log.exists():
            subprocess.Popen(["notepad.exe", str(self.server_log.resolve())])
        elif self.tray_log.exists():
            subprocess.Popen(["notepad.exe", str(self.tray_log.resolve())])
        else:
            if self.icon:
                self.icon.notify("No server log file found yet.", "Server Logs")

    def open_folder(self, icon=None, item=None):
        os.startfile(str(self.base_dir))

    def _update_state(self, state):
        self.server_status = state
        if not self.icon:
            return

        if state == "running":
            self.icon.icon = self.icon_online
            self.icon.title = f"KCT Studio - Running ({self.dashboard_url})"
        elif state == "starting":
            self.icon.icon = self.icon_starting
            self.icon.title = "KCT Studio - Starting server..."
        elif state == "stopping":
            self.icon.icon = self.icon_starting
            self.icon.title = "KCT Studio - Stopping server..."
        else:
            self.icon.icon = self.icon_offline
            self.icon.title = "KCT Studio - Stopped"

        self.icon.update_menu()

    def _monitor_loop(self):
        """Background health checker that keeps tray icon synchronized."""
        while True:
            time.sleep(2.5)
            if self.server_status not in ("starting", "stopping"):
                listening = self.is_server_listening()
                current = "running" if listening else "stopped"
                if current != self.server_status:
                    self._update_state(current)

    def _build_menu(self):
        return pystray.Menu(
            pystray.MenuItem(
                lambda item: f"KCT Studio: {'● Online (:7860)' if self.server_status == 'running' else '○ Offline' if self.server_status == 'stopped' else '⏳ Starting...'}",
                lambda: None,
                enabled=False
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "🌐 Open Dashboard",
                self.open_dashboard,
                default=True
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "▶ Start Server",
                lambda icon, item: self.start_server(notify=True),
                enabled=lambda item: self.server_status == "stopped"
            ),
            pystray.MenuItem(
                "⏹ Stop Server",
                lambda icon, item: self.stop_server(notify=True),
                enabled=lambda item: self.server_status == "running"
            ),
            pystray.MenuItem(
                "🔄 Restart Server",
                lambda icon, item: self.restart_server(),
                enabled=lambda item: self.server_status == "running"
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "🚀 Start with Windows Boot",
                self.toggle_startup,
                checked=lambda item: self.is_startup_enabled()
            ),
            pystray.MenuItem(
                "📄 View Server Logs",
                self.view_logs
            ),
            pystray.MenuItem(
                "📂 Open Project Directory",
                self.open_folder
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "❌ Exit Tray & Server",
                self.exit_app
            )
        )

    def exit_app(self, icon=None, item=None):
        logging.info("Exiting KCT Studio Tray App...")
        if self.server_status == "running":
            self.stop_server(notify=False)
            time.sleep(1)
        if self.icon:
            self.icon.stop()
        sys.exit(0)

    def _on_ready(self, icon):
        """Called by pystray once the Win32 window and event loop are established."""
        icon.visible = True
        logging.info("Tray icon is now visible in Windows notification area.")

        if not self.is_server_listening():
            self.start_server(notify=True)
        else:
            self._update_state("running")

        monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        monitor_thread.start()

    def run(self):
        logging.info("Tray app run called.")
        # Auto-enable startup in Windows registry on first run if not already set
        if not self.is_startup_enabled():
            self.set_startup_enabled(True)

        # Run tray message loop (setup callback sets visible=True and starts monitoring)
        self.icon.run(setup=self._on_ready)


def check_single_instance(allow_replace=False):
    """Ensure only one instance of the tray app runs at a time."""
    if allow_replace:
        terminate_stale_instances()

    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        if allow_replace:
            terminate_stale_instances()
            mutex = ctypes.windll.kernel32.CreateMutexW(None, False, MUTEX_NAME)
            return mutex
        # Bring dashboard to front and exit
        _, _, dashboard_url = KCTStudioTrayApp()._get_server_config()
        webbrowser.open(dashboard_url)
        sys.exit(0)
    return mutex


if __name__ == "__main__":
    setup_logging(Path(__file__).resolve().parent / "logs" / "tray.log")

    if "--install-startup" in sys.argv:
        app = KCTStudioTrayApp()
        app.set_startup_enabled(True)
        print("KCT Studio registered to start on Windows boot.")
        sys.exit(0)

    if "--uninstall-startup" in sys.argv:
        app = KCTStudioTrayApp()
        app.set_startup_enabled(False)
        print("KCT Studio boot startup registration removed.")
        sys.exit(0)

    # Make sure we are attached to the interactive Default desktop
    ensure_interactive_desktop()

    allow_replace = ("--restart" in sys.argv or "--force" in sys.argv)
    _mutex = check_single_instance(allow_replace=allow_replace)

    tray = KCTStudioTrayApp()
    tray.run()
