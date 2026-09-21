# KCT Studio - AI Content Generation Pipeline

[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6.svg?logo=windows&logoColor=white)](https://microsoft.com/windows)
[![ComfyUI](https://img.shields.io/badge/ComfyUI-Integration-orange.svg)](https://github.com/comfyanonymous/ComfyUI)

**KCT Studio (v2.0)** is an automated multi-project AI video generation pipeline and management dashboard designed for high-throughput social video production (YouTube, Facebook, TikTok, X, Instagram). It provides a full web interface, live hardware telemetry, real-time streaming console, and a Windows System Tray background service that starts automatically on boot.

---

## Features

- **Multi-Project Management**: Switch seamlessly between Manhwa Cinema Lab, Bible Hidden Secrets Revealed, and other content channels.
- **Dynamic CLI Command Builder**: Formats execution commands with automatic `--episode`, `--from`, `--to`, chapter detection, and `--adz` parameter handling.
- **Live Terminal Console**: Streaming WebSocket log output with ANSI colors, execution timer, and stop/terminate controls.
- **Social Media Tracking**: Visual publish badges (FB, YouTube, TikTok, X, Instagram) and toggleable status flags persisted per episode.
- **Windows System Tray Controller**:
  - Run silently in the background with zero console flash.
  - One-click Start, Stop, Restart, and Dashboard launch.
  - Optional automatic startup on Windows boot via `HKCU` registry.
- **Hardware Telemetry**: Real-time GPU VRAM, load, temperature monitoring, and ComfyUI server connectivity indicators.
- **Local & LAN HTTPS**: Built-in SSL certificate manager with one-click Windows root trust installation.

---

## Quick Start

### 1. Installation
```powershell
git clone <repo-url>
cd AI-Content-Generation-Pipeline
pip install -r requirements.txt
```

### 2. Trust SSL Certificate (Optional but recommended)
```powershell
.\install_certificate.bat
```

### 3. Launching KCT Studio

#### Run in Background with System Tray (Recommended)
```powershell
.\start_tray.bat
```
*(Or run `install_startup.bat` to have it start automatically every time your PC boots.)*

#### Run in Interactive Terminal
```powershell
.\run.bat
```

Open your browser to: [**https://127.0.0.1:7860/**](https://127.0.0.1:7860/)

---

## Documentation

Full documentation is available in the [`docs/`](docs/index.md) directory:

- [**Architecture Overview**](docs/architecture.md) — Architectural layout, data flow, and core module breakdown.
- [**Getting Started Guide**](docs/getting_started.md) — Prerequisites, environment setup, and launch options.
- [**System Tray & Boot Startup**](docs/system_tray_and_startup.md) — Win32 tray app, single-instance mutex, and silent execution.
- [**API Reference**](docs/api_reference.md) — REST endpoints, WebSocket schema, and payload formats.
- [**Frontend Guide**](docs/frontend_guide.md) — Interface features, command builder, and social media tracking.
- [**Troubleshooting & FAQ**](docs/troubleshooting.md) — Windows async fixes, silent subprocess execution, and port handling.

---

## Project Structure

```text
├── app.py                      # FastAPI server & HTTP/WebSocket endpoints
├── tray_app.py                 # Windows System Tray controller
├── config.json                 # Studio projects & configuration
├── requirements.txt            # Python dependencies
├── core/                       # Core pipeline libraries
│   ├── asset_manager.py        # Video asset scanner & ffprobe metadata
│   ├── cert_manager.py         # Self-signed SSL certificate manager
│   ├── config.py               # JSON configuration manager
│   ├── gpu_monitor.py          # GPU VRAM & telemetry monitor
│   ├── process_runner.py       # Asynchronous process runner & WS broadcaster
│   ├── project_scanner.py      # Project structure & chapter scanner
│   └── social_dispatcher.py    # Social media dispatch & status persistence
├── static/                     # Web dashboard frontend (HTML/CSS/JS)
├── docs/                       # Technical documentation
└── data/                       # Local media catalog persistence
```

---

## License

Proprietary / Internal — KCT Studio Video Pipeline.
