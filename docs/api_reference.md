# API Reference

FastAPI REST and WebSocket endpoints provided by KCT Studio (`app.py`).

---

## 1. System & Configuration

### `GET /api/config`
Returns active configuration loaded from `config.json`.

**Response (200 OK):**
```json
{
  "server": { "host": "0.0.0.0", "port": 7860, "ssl_enabled": true },
  "comfyui": { "url": "http://127.0.0.1:8188" },
  "active_project_path": "E:\\Projects\\Bible Hidden Secrets Revealed",
  "projects": [...]
}
```

### `GET /api/system/stats`
Real-time GPU and system telemetry. Queried periodically by frontend.

**Response (200 OK):**
```json
{
  "cpu_percent": 18.5,
  "ram_total_gb": 32.0,
  "ram_used_gb": 21.4,
  "ram_percent": 66.8,
  "gpus": [
    {
      "index": 0,
      "name": "NVIDIA RTX A2000 Laptop GPU",
      "total_mb": 4096,
      "used_mb": 918,
      "free_mb": 3178,
      "percent": 22.4,
      "temperature": 52,
      "utilization": 10
    }
  ],
  "comfyui": {
    "online": true,
    "url": "http://127.0.0.1:8188",
    "devices": [...]
  }
}
```

---

## 2. Projects & Episodes

### `GET /api/projects`
Lists all configured projects with active flags.

### `POST /api/projects/active`
Switches the currently active studio project.

**Request Body:**
```json
{
  "path": "E:\\Projects\\Manhwa Cinema Lab"
}
```

### `GET /api/episodes`
Scans and returns discovered episodes, reels, chapters, and available commands for the active project.

**Response (200 OK):**
```json
{
  "project_name": "Manhwa Cinema Lab",
  "project_type": "manhwa",
  "episodes": [
    {
      "id": "reel76",
      "name": "Reel 76",
      "folder": "76_the_first_death...",
      "chapters": ["Chapter_1", "Chapter_2"],
      "has_meta": true,
      "posted": {
        "facebook": true,
        "youtube": false,
        "tiktok": false,
        "x": false,
        "instagram": false
      }
    }
  ],
  "commands": [
    { "id": "generate_reel", "name": "Generate Reel", "script": "generate_reel_76.py" },
    { "id": "generate_chapter", "name": "Generate Chapter", "script": "generate_chapter.py" }
  ]
}
```

---

## 3. Execution & Process Runner

### `POST /api/run`
Spawns a generation script as an asynchronous background subprocess.

**Request Body:**
```json
{
  "command_id": "generate_reel",
  "episode": "81",
  "from_num": "81",
  "to_num": "82",
  "chapter": "Chapter_1",
  "adz": true
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "job": {
    "command": "python generate_reel.py --from 81 --to 82 --chapter Chapter_1 --adz",
    "pid": 14280,
    "status": "running",
    "start_time": 1726915200.0
  }
}
```

### `POST /api/stop`
Gracefully terminates the active generation job and process tree.

### `GET /api/status`
Returns current execution status (`idle`, `running`, `completed`, `error`, `stopped`).

---

## 4. WebSocket Terminal Streaming

### `WS /ws/logs`
Subscribes to real-time console output. Upon connection, re-plays buffered history and streams new lines as they occur.

**Message Format (JSON):**
```json
{
  "type": "log",
  "stream": "stdout",
  "line": "[Ready] Image exists: images/reel76_dyn_1.png"
}
```

---

## 5. Media & Social Dispatch

### `POST /api/assets/open_metadata`
Opens or loads a video's metadata file for in-app viewing, editing, or external Notepad launch.

### `POST /api/social/publish`
Dispatches social media publication across active platforms (YouTube, Facebook, Instagram, TikTok, X) and triggers the automation webhook.

**Request Body:**
```json
{
  "rel_path": "chapter_1/slideshow/chapter_1_full.mp4",
  "platforms": ["youtube", "facebook", "instagram", "tiktok", "x"],
  "title": "Solo Leveling Episode 1 Recap",
  "description": "Full story recap...",
  "tags": ["anime", "manhwa"]
}
```

### `GET /api/social/config`
Returns the active social media configuration, including target platform enable flags, dry-run mode, and webhook settings.

### `POST /api/social/config`
Updates social media configuration presets, target platforms, and webhook authorization headers.

### `POST /api/social/test_webhook`
Tests connectivity to the configured or supplied webhook URL, returning HTTP status code, latency (ms), and response preview.

**Request Body:**
```json
{
  "webhook_url": "https://n8n.yourdomain.com/webhook/kct-social-publish",
  "auth_header": "Bearer secret_token_xyz"
}
```

### `GET /api/social/template/n8n`
Downloads the official pre-built n8n social media distribution workflow JSON.

---

## 6. Video Posting Calendar Planner

### `GET /calendar`
Serves the full-screen standalone Video Posting Calendar Planner webpage.

### `GET /api/calendar/schedule`
Returns scheduled, posted, and queued videos with optional filtering by `project_path`, `month`, `year`, or `status`.

### `POST /api/calendar/schedule`
Enqueues an approved video for posting. Strictly validates the **1 post per account per day** rule across all target platforms.

**Request Body:**
```json
{
  "project_path": "E:\\Projects\\BHRS-Youtube",
  "video_rel_path": "reels/75_the_jewish_feasts_are_a_timeline/75_final_reel.mp4",
  "scheduled_date": "2026-09-24",
  "scheduled_time": "18:00",
  "platforms": ["youtube", "facebook", "instagram", "tiktok", "x"],
  "title": "The Jewish Feasts Are a Timeline"
}
```

### `PUT /api/calendar/schedule/{post_id}`
Reschedules a queued post to a new date or time.

### `DELETE /api/calendar/schedule/{post_id}`
Cancels and removes a scheduled post from the calendar.

### `POST /api/calendar/schedule/{post_id}/post_now`
Triggers immediate dispatch of a scheduled post ahead of its queue time.

### `POST /api/calendar/auto_schedule`
Scans approved unposted videos for the project and sequences them into consecutive future calendar days at the project's default posting time.

### `GET /api/calendar/next_slot`
Calculates the earliest upcoming available date & time slot that is free for the specified platforms.

