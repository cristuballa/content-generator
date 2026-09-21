# Getting Started

This guide explains how to install, configure, and launch KCT Studio.

---

## 1. System Requirements

- **Operating System**: Windows 10 or Windows 11 (64-bit)
- **Python**: Python 3.10, 3.11, or 3.12 (with `python.exe` and `pythonw.exe` in `PATH`)
- **NVIDIA GPU**: RTX 20-series, 30-series, 40-series, or Professional A-series GPU with updated NVIDIA Game Ready or Studio Drivers
- **Media Tools**: `ffmpeg` and `ffprobe` installed and available in system `PATH`
- **ComfyUI**: Installed and accessible at `http://127.0.0.1:8188` (default)

---

## 2. Installation

1. **Clone or navigate to the repository directory**:
   ```powershell
   cd C:\Projects\AI-Content-Generation-Pipeline
   ```

2. **Install Python dependencies**:
   ```powershell
   pip install -r requirements.txt
   ```

3. **Trust Local SSL Certificate** *(Recommended for HTTPS without browser security warnings)*:
   Double-click `install_certificate.bat` or run:
   ```powershell
   .\install_certificate.bat
   ```
   This automatically generates and registers a trusted certificate for `localhost` and your LAN IP into Windows `Cert:\CurrentUser\Root`.

---

## 3. Configuration (`config.json`)

Configure your server and pipeline projects in `config.json`:

```json
{
  "server": {
    "host": "0.0.0.0",
    "port": 7860,
    "ssl_enabled": true
  },
  "comfyui": {
    "url": "http://127.0.0.1:8188"
  },
  "active_project_path": "E:\\Projects\\Bible Hidden Secrets Revealed",
  "projects": [
    {
      "name": "Bible Hidden Secrets Revealed",
      "path": "E:\\Projects\\Bible Hidden Secrets Revealed",
      "type": "documentary"
    },
    {
      "name": "Manhwa Cinema Lab",
      "path": "E:\\Projects\\Manhwa Cinema Lab",
      "type": "manhwa"
    }
  ]
}
```

---

## 4. Running the Application

### Option A: System Tray & Background Service (Recommended)
Double-click `start_tray.bat` or run:
```powershell
.\start_tray.bat
```
- Starts the FastAPI backend silently in the background.
- Places the KCT Studio icon in your Windows Taskbar System Tray (click `^` if hidden).
- Automatically launches your browser at `https://127.0.0.1:7860/`.

### Option B: Automatic Startup on Windows Boot
Double-click `install_startup.bat`:
```powershell
.\install_startup.bat
```
- Registers KCT Studio to start automatically whenever Windows boots via `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
- Runs completely windowless with zero console flash.

### Option C: Foreground Terminal Mode (For debugging)
```powershell
.\run.bat
# or
python app.py
```
- Starts the server with live console output displayed directly in your PowerShell terminal.
