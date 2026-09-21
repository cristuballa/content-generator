# Troubleshooting & FAQs

This document covers known issues, debugging steps, and solutions for running KCT Studio on Windows.

---

## 1. Command Prompt / CMD Shell Flashing Periodically

### Cause
When a background Python script running under `pythonw.exe` executes a console program (such as `nvidia-smi`, `ffprobe`, or `ffmpeg`) without setting Windows process creation flags, Windows automatically allocates a new `cmd.exe` / `conhost.exe` window for each call. If telemetry polls every few seconds, this causes a black shell window to repeatedly flash on screen.

### Solution
In all Python `subprocess.run()`, `subprocess.Popen()`, and `asyncio.create_subprocess_exec()` calls, include `creationflags=subprocess.CREATE_NO_WINDOW`:

```python
import sys
import subprocess

creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
subprocess.run(["nvidia-smi", ...], creationflags=creationflags)
```
*(All subprocess calls across `core/` have been updated with this fix.)*

---

## 2. System Tray Icon Not Showing in Taskbar

### Possible Causes
1. **Hidden in Overflow**: In Windows 11, new tray icons are collapsed into the `^` overflow menu. Click the `^` icon next to the system clock to locate the KCT Studio icon.
2. **Desktop Station Mismatch**: If started from a headless runner or isolated desktop station, the icon attaches to that invisible session. `tray_app.py` has built-in desktop detection (`ensure_interactive_desktop`) to redirect itself to `WinSta0\Default`.
3. **Stale Process Holding Mutex**: Run `start_tray.bat` which passes `--restart` to automatically clean up orphaned processes and re-register the tray icon.

---

## 3. SSL / HTTPS Browser Certificate Warnings

### Symptom
Browser displays `NET::ERR_CERT_AUTHORITY_INVALID` or "Your connection isn't private".

### Solution
1. Run `install_certificate.bat` in the project root.
2. This invokes `trust_cert.ps1`, which imports `certs/cert.crt` into Windows `Cert:\CurrentUser\Root`.
3. Restart your browser (Chrome/Edge/Brave). The connection will now show a secure padlock.

---

## 4. Windows Asyncio `WinError 10054` in Server Logs

### Symptom
Server logs contain `ConnectionResetError: [WinError 10054] An existing connection was forcibly closed by the remote host`.

### Solution
This occurs when a browser tab abruptly disconnects or reloads an active WebSocket / HTTP connection. `app.py` includes a custom lifespan exception handler and monkey-patched Proactor transport to safely silence this harmless Windows socket reset without polluting the logs.

---

## 5. Port 7860 Already in Use

### Solution
Both `app.py` and `tray_app.py` feature automated port checking via `psutil`. Any stale process occupying port 7860 is automatically terminated when launching the server. To manually check and terminate port 7860:
```powershell
Get-NetTCPConnection -LocalPort 7860 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
```
