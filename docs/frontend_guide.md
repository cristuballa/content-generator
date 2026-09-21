# Studio Frontend Guide

The KCT Studio interface is designed for rapid video production, execution monitoring, and social media posting status tracking.

---

## 1. Top Navigation Bar

- **Studio Branding**: KCT Studio version indicator and active project selector.
- **Hardware Telemetry Bar**:
  - Live GPU VRAM meter and temperature readout (`NVIDIA RTX A2000 Laptop GPU: 918 / 4096 MB (22.4%) 52°C`).
  - ComfyUI connectivity badge (`Online :8188` or `Offline`).

---

## 2. Left Sidebar: Episode & Reel Browser

- **Episode Cards**:
  - Displays episode number, name, and folder.
  - **Social Media Icons**: Badges for **Facebook**, **YouTube**, **TikTok**, **X (Twitter)**, and **Instagram**.
    - Colored/highlighted when published to that platform.
    - Dimmed/gray when not yet published.
- **Active Selection**: Clicking any card populates the central command form.

---

## 3. Center Form: Dynamic Command Builder

- **Command Dropdown**: Available CLI actions (`generate_reel`, `generate_chapter`, `combine_chapters`, etc.).
- **Episode Selection**: Selected by default (`--episode <id>`).
- **From / To Range Inputs**:
  - By default blank.
  - When values are entered (e.g. From `81`, To `82`), the `--episode` flag is automatically superseded by `--from 81 --to 82`.
- **Chapter Dropdown**:
  - Displays `--None--` when the project has no chapters.
  - Automatically lists available chapters (e.g. `Chapter_1`, `Chapter_2`) when present in the project structure.
- **Adz Checkbox**: Optional `--adz` flag for advertising/sponsored segments.
- **Metadata Viewer**:
  - Clickable icon/link (`Open Metadata in Notepad`) to view the video's metadata JSON file.
- **Social Media Toggle Checkboxes**:
  - Individual checkboxes for Facebook, YouTube, TikTok, X, and Instagram.
  - Clicking any checkbox immediately saves the post state to `data/media_catalog.json` and updates the badge on the episode card.

---

## 4. Bottom Console: Live Streaming Terminal

- **Real-time Output**: Connected via WebSocket to stream Python execution logs live.
- **Scrollable & Max-Height Constrained**:
  - Fixed maximum height to prevent pushing the UI off-screen.
  - Smooth vertical scrolling with auto-scroll lock.
  - ANSI color rendering for clear error and warning highlights.
- **Execution Controls**:
  - **Run Command (▶)**: Launches the assembled CLI command.
  - **Stop (⏹)**: Terminates the running process tree cleanly and releases GPU memory.
  - **Clear Console**: Clears log buffer in the browser view.
