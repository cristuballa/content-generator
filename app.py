import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

import sys
import json
import time
import re
import asyncio
import mimetypes
import subprocess
import shlex
from pathlib import Path
from typing import Dict, Any, List, Optional

# Ensure stdout and stderr are available when running under pythonw.exe
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.config import config_manager
from core.gpu_monitor import get_system_stats
from core.project_scanner import ProjectScanner
from core.process_runner import process_runner
from core.asset_manager import asset_manager
from core.social_dispatcher import social_dispatcher
from core.cert_manager import cert_manager
from core.calendar_manager import calendar_manager
from core.story_map_manager import story_map_manager
from core.meta_uploader import meta_uploader
from core.youtube_uploader import youtube_uploader
from core.threads_uploader import threads_uploader
from core.tiktok_uploader import tiktok_uploader
from core.oauth_bridge_5678 import ensure_oauth_bridge, get_oauth_bridge_status

# ----------------- Windows Asyncio & Logging Fixes -----------------
# Fix 1: Windows ProactorEventLoop WinError 10054 on client disconnect
if sys.platform == "win32":
    import asyncio.proactor_events
    _orig_call_connection_lost = asyncio.proactor_events._ProactorBasePipeTransport._call_connection_lost

    def _silenced_call_connection_lost(self, exc):
        try:
            _orig_call_connection_lost(self, exc)
        except (ConnectionResetError, OSError):
            # Remote client abruptly closed connection (WinError 10054). Clean up transport safely.
            try:
                if hasattr(self, "_sock") and self._sock is not None:
                    self._sock.close()
                    self._sock = None
                if hasattr(self, "_server") and self._server is not None:
                    self._server._detach()
                    self._server = None
                self._called_connection_lost = True
            except Exception:
                pass

    asyncio.proactor_events._ProactorBasePipeTransport._call_connection_lost = _silenced_call_connection_lost

# Fix 2: Filter out repetitive telemetry poll logs (/api/system/stats) from console
class TelemetryFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/api/system/stats" not in record.getMessage()

logging.getLogger("uvicorn.access").addFilter(TelemetryFilter())

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Attach TelemetryFilter to uvicorn.access logger and all handlers
    access_logger = logging.getLogger("uvicorn.access")
    access_logger.addFilter(TelemetryFilter())
    for handler in access_logger.handlers:
        handler.addFilter(TelemetryFilter())

    # 2. Suppress Windows ProactorEventLoop WinError 10054 callback errors
    if sys.platform == "win32":
        try:
            loop = asyncio.get_running_loop()
            orig_handler = loop.get_exception_handler()

            def win_exception_handler(current_loop, context):
                exc = context.get("exception")
                if isinstance(exc, (ConnectionResetError, OSError)) and getattr(exc, "winerror", None) == 10054:
                    return  # Suppress harmless Windows connection reset
                msg = str(context.get("message", ""))
                exc_str = str(exc) if exc else ""
                if "WinError 10054" in msg or "WinError 10054" in exc_str:
                    return
                if orig_handler:
                    orig_handler(current_loop, context)
                else:
                    current_loop.default_exception_handler(context)

            loop.set_exception_handler(win_exception_handler)
        except Exception:
            pass

    # 3. Start the OAuth callback bridge (server.oauth_callback_port, 5678 by default) for YouTube & Threads sign-in
    from core.oauth_bridge_5678 import start_oauth_bridge, stop_oauth_bridge
    start_oauth_bridge()

    scheduler_task = None
    async def scheduler_loop():
        while True:
            try:
                await asyncio.sleep(30)
                await calendar_manager.execute_due_posts(social_dispatcher)
                # Links comment on scheduled YouTube/Facebook posts that have just gone live
                await social_dispatcher.post_due_comments()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"[Scheduler] Error executing due posts: {e}")

    try:
        scheduler_task = asyncio.create_task(scheduler_loop())
    except Exception as e:
        logging.warning(f"Could not start calendar scheduler task: {e}")

    yield

    stop_oauth_bridge()
    if scheduler_task:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass

app = FastAPI(
    title="KCT Studio - AI Video Pipeline Dashboard",
    description="Studio management interface for multi-project automated AI video pipelines",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def no_cache_static_and_root(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path == "/" or path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# ----------------- Request Models -----------------
class SelectProjectRequest(BaseModel):
    path: str

class AddProjectRequest(BaseModel):
    name: str
    path: str
    type: str = "custom"
    social_platforms: Optional[Dict[str, bool]] = None
    platforms: Optional[Dict[str, bool]] = None

class RunPipelineRequest(BaseModel):
    script_name: Optional[str] = None
    script_rel_path: Optional[str] = None
    args: List[str] = []
    command_str: Optional[str] = None
    custom_command: Optional[str] = None

class AssetStatusRequest(BaseModel):
    rel_path: str
    status: str  # approved, rejected, pending
    notes: Optional[str] = None
    auto_publish: Optional[bool] = None

class AssetHideRequest(BaseModel):
    rel_path: str
    hidden: Optional[bool] = None

class AssetRegenerateRequest(BaseModel):
    rel_path: str

class AssetSocialToggleRequest(BaseModel):
    rel_path: str
    platform: str
    posted: bool
    details: Optional[Dict[str, Any]] = None

class GeneratorRunRequest(BaseModel):
    week: int
    type: str  # "long_form", "reel", "story", "all_reels", "all_stories", "all_week", "regen_thumbnail", "combine_ad"
    target_num: Optional[int] = None
    ad_variant: Optional[int] = 1
    regen_thumb: Optional[bool] = False

class AssetSocialBatchRequest(BaseModel):
    rel_path: str
    platforms: Dict[str, bool]

class OpenMetadataRequest(BaseModel):
    rel_path: str
    launch_external: Optional[bool] = False

class SaveMetadataRequest(BaseModel):
    rel_path: str
    content: str

class SocialPublishRequest(BaseModel):
    rel_path: str
    platforms: Optional[List[str]] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    project_path: Optional[str] = None
    force_republish: Optional[bool] = False
    platform_captions: Optional[Dict[str, str]] = None
    pinned_comment: Optional[str] = None

class SocialConfigRequest(BaseModel):
    project_path: Optional[str] = None
    reset_to_default: Optional[bool] = False
    dry_run: Optional[bool] = None
    auto_publish_on_approve: Optional[bool] = None
    auto_schedule_on_approve: Optional[bool] = None
    default_posting_time: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_auth_header: Optional[str] = None
    youtube: Optional[Dict[str, Any]] = None
    facebook: Optional[Dict[str, Any]] = None
    instagram: Optional[Dict[str, Any]] = None
    tiktok: Optional[Dict[str, Any]] = None
    threads: Optional[Dict[str, Any]] = None
    x: Optional[Dict[str, Any]] = None

class SocialTestWebhookRequest(BaseModel):
    webhook_url: Optional[str] = None
    auth_header: Optional[str] = None
    project_path: Optional[str] = None

class CalendarScheduleRequest(BaseModel):
    project_path: Optional[str] = None
    video_rel_path: str
    scheduled_date: Optional[str] = None
    scheduled_time: Optional[str] = None
    platforms: Optional[List[str]] = None
    title: Optional[str] = None
    force: Optional[bool] = False

class CalendarUpdateRequest(BaseModel):
    scheduled_date: str
    scheduled_time: str
    platforms: Optional[List[str]] = None
    force: Optional[bool] = False
    status: Optional[str] = None

class CalendarAutoScheduleRequest(BaseModel):
    project_path: Optional[str] = None

class RemoveProjectRequest(BaseModel):
    path: str

class ToggleHideProjectRequest(BaseModel):
    path: str
    hidden: Optional[bool] = None

class UpdateProjectRequest(BaseModel):
    old_path: str
    name: str
    new_path: str
    type: str = "custom"
    social_platforms: Optional[Dict[str, bool]] = None
    platforms: Optional[Dict[str, bool]] = None

# ----------------- WebSocket Live Terminal -----------------
@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    await process_runner.connect_ws(websocket)
    try:
        while True:
            # Client can send ping or commands over ws
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        process_runner.disconnect_ws(websocket)
    except Exception:
        process_runner.disconnect_ws(websocket)

# ----------------- Project Management APIs -----------------
@app.get("/api/projects")
async def get_projects(include_hidden: bool = Query(False)):
    cfg = config_manager.get_all()
    active_path = config_manager.get_active_project()
    active_norm = str(Path(active_path).resolve()).lower() if active_path else ""
    projects = []
    for p in cfg.get("projects", []):
        is_hidden = p.get("hidden", False)
        if is_hidden and not include_hidden:
            continue
        p_path = Path(p["path"])
        p_norm = str(p_path.resolve()).lower() if p_path.exists() else p["path"].replace("/", "\\").lower()
        projects.append({
            "name": p["name"],
            "path": p["path"],
            "type": p.get("type", "custom"),
            "hidden": is_hidden,
            "exists": p_path.exists(),
            "is_active": p_norm == active_norm,
            "social_platforms": config_manager.get_project_platforms(p["path"])
        })
    return {
        "active_project": active_path,
        "projects": projects
    }

@app.post("/api/projects/select")
async def select_project(req: SelectProjectRequest):
    p = Path(req.path)
    if not p.exists():
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {req.path}")
    
    config_manager.set_active_project(str(p))
    scan_data = await asyncio.to_thread(ProjectScanner.scan_project, str(p))

    # Match friendly display name and project type from configuration
    cfg_projects = config_manager.get_all().get("projects", [])
    p_resolved = p.resolve()
    for cp in cfg_projects:
        try:
            if Path(cp["path"]).resolve() == p_resolved:
                scan_data["name"] = cp["name"]
                scan_data["type"] = cp.get("type", "custom")
                break
        except Exception:
            pass

    scan_data["social_platforms"] = config_manager.get_project_platforms(str(p))
    return {"success": True, "active_project": str(p), "scan": scan_data}

@app.post("/api/projects/add")
async def add_project(req: AddProjectRequest):
    p = Path(req.path)
    if not p.exists():
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {req.path}")
    platforms = req.social_platforms or req.platforms
    new_proj = config_manager.add_project(req.name, str(p), req.type, social_platforms=platforms)
    config_manager.set_active_project(str(p))
    return {
        "success": True,
        "project": new_proj,
        "social_platforms": config_manager.get_project_platforms(str(p))
    }

@app.post("/api/projects/remove")
async def remove_project(req: RemoveProjectRequest):
    """Removes a project from Studio registry. Note: Does NOT delete the folder or assets on disk."""
    success = config_manager.remove_project(req.path)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found in configuration list")
    new_active = config_manager.get_active_project()
    return {"success": True, "message": "Project unlinked from Studio list. Folder and assets remain untouched on disk.", "active_project": new_active}

@app.post("/api/projects/toggle_hide")
async def toggle_hide_project(req: ToggleHideProjectRequest):
    """Toggles project visibility in Studio dropdown. Note: Does NOT delete files on disk."""
    updated = config_manager.toggle_hide_project(req.path, req.hidden)
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    new_active = config_manager.get_active_project()
    return {"success": True, "project": updated, "active_project": new_active}

@app.post("/api/projects/update")
async def update_project(req: UpdateProjectRequest):
    """Updates project display name, folder location directory, type, and enabled social media platforms in config."""
    p = Path(req.new_path)
    if not p.exists():
        raise HTTPException(status_code=400, detail=f"Directory does not exist: {req.new_path}")
    if not p.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {req.new_path}")
    
    platforms = req.social_platforms or req.platforms
    updated = config_manager.update_project(req.old_path, req.name, str(p), req.type, social_platforms=platforms)
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found in configuration list")
    
    return {
        "success": True,
        "message": f"Updated project '{req.name}' path to {req.new_path}",
        "project": updated,
        "social_platforms": config_manager.get_project_platforms(str(p)),
        "active_project": config_manager.get_active_project()
    }

@app.get("/api/projects/scan")
async def scan_active_project():
    active_path = config_manager.get_active_project()
    if not active_path or not Path(active_path).exists():
        return {"valid": False, "error": "No valid active project selected"}
    scan_data = ProjectScanner.scan_project(active_path)
    scan_data["social_platforms"] = config_manager.get_project_platforms(active_path)
    return scan_data

# ----------------- Pipeline Execution APIs -----------------
@app.post("/api/pipeline/run")
async def run_pipeline(req: RunPipelineRequest):
    active_path = config_manager.get_active_project()
    if not active_path or not Path(active_path).exists():
        raise HTTPException(status_code=400, detail="No valid project active")

    base_p = Path(active_path)

    # 1. Check if direct command_str or custom_command was provided
    raw_cmd = req.command_str or req.custom_command
    if raw_cmd and raw_cmd.strip():
        tokens = shlex.split(raw_cmd.strip(), posix=False)
        if not tokens:
            raise HTTPException(status_code=400, detail="Empty command line string")

        # Strip leading python invocation if present
        if tokens[0].lower() in ("python", "python.exe", "pythonw", "pythonw.exe"):
            tokens = tokens[1:]

        if not tokens:
            raise HTTPException(status_code=400, detail="No target script specified in command line")

        script_name = tokens[0]
        args = tokens[1:]
    else:
        script_name = req.script_name or "generate_reel.py"
        args = req.args

    script_path = None

    if req.script_rel_path:
        p = base_p / req.script_rel_path
        if p.exists():
            script_path = p

    if not script_path:
        p = base_p / script_name
        if p.exists():
            script_path = p

    if not script_path and not script_name.endswith(".py"):
        p_py = base_p / f"{script_name}.py"
        if p_py.exists():
            script_path = p_py

    if not script_path:
        candidates = list(base_p.glob(f"*/{script_name}")) + list(base_p.glob(f"*/*/{script_name}"))
        if not candidates and not script_name.endswith(".py"):
            candidates = list(base_p.glob(f"*/{script_name}.py")) + list(base_p.glob(f"*/*/{script_name}.py"))
        if candidates:
            script_path = candidates[0]

    if not script_path or not script_path.exists():
        raise HTTPException(status_code=404, detail=f"Script not found: {script_name}")

    run_cwd = str(script_path.parent) if script_path.parent.exists() else str(base_p)

    res = await process_runner.run_script(
        script_path=str(script_path),
        cwd=run_cwd,
        args=args
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

@app.post("/api/pipeline/stop")
async def stop_pipeline():
    res = await process_runner.stop()
    return res

@app.get("/api/pipeline/status")
async def get_pipeline_status():
    return {
        "status": process_runner.status,
        "job": process_runner.current_job_info,
        "pid": process_runner.current_pid,
        "recent_logs": list(process_runner.logs)[-100:]
    }

@app.post("/api/pipeline/clear_logs")
async def clear_pipeline_logs():
    process_runner.clear_logs()
    return {"success": True}

# ----------------- Asset Catalog & Review APIs -----------------
@app.get("/api/assets")
async def get_assets(
    include_hidden: bool = Query(False),
    filter_type: Optional[str] = Query(None),
    asset_type: Optional[str] = Query(None),
    master_only: bool = Query(False),
    status: Optional[str] = Query(None)
):
    active_path = config_manager.get_active_project()
    if not active_path or not Path(active_path).exists():
        return {"assets": []}

    assets = await asyncio.to_thread(
        asset_manager.scan_assets,
        active_path,
        include_hidden=include_hidden,
        filter_type=filter_type,
        asset_type_filter=asset_type,
        master_only=master_only
    )
    if status and status != "all":
        assets = [a for a in assets if a["status"] == status]
    return {"assets": assets, "total": len(assets)}

@app.post("/api/assets/status")
async def set_asset_status(req: AssetStatusRequest):
    active_path = config_manager.get_active_project()
    if not active_path:
        raise HTTPException(status_code=400, detail="No active project")

    updated = asset_manager.update_asset_status(req.rel_path, req.status, req.notes)

    # Automated social media scheduling or posting upon Approval
    social_result = None
    scheduled_entry = None
    cfg_social = config_manager.get_project_social_config(active_path)
    # Strictly do NOT auto-publish to live feeds on approval unless explicitly requested with auto_publish=True
    auto_pub = req.auto_publish is True
    auto_sched = cfg_social.get("auto_schedule_on_approve", True)

    if req.status == "approved":
        if auto_pub:
            social_result = await social_dispatcher.publish_video(
                project_path_str=active_path,
                video_rel_path=req.rel_path
            )
        elif auto_sched:
            try:
                slot = calendar_manager.find_next_available_slot(active_path)
                scheduled_entry = calendar_manager.schedule_video(
                    project_path=active_path,
                    video_rel_path=req.rel_path,
                    date_str=slot["date"],
                    time_str=slot["time"],
                    title=updated.get("clean_title") or updated.get("filename")
                )
            except Exception as e:
                logging.warning(f"Could not auto-schedule approved video {req.rel_path}: {e}")
    elif req.status in ("pending", "rejected"):
        try:
            calendar_manager.remove_schedule_for_video(active_path, req.rel_path)
        except Exception as e:
            logging.warning(f"Could not remove calendar schedule for unapproved video: {e}")

    return {
        "success": True,
        "asset": updated,
        "social_dispatch": social_result,
        "scheduled_entry": scheduled_entry
    }

@app.post("/api/assets/hide")
async def toggle_asset_hide(req: AssetHideRequest):
    updated = asset_manager.toggle_hidden(req.rel_path, req.hidden)
    return {"success": True, "asset": updated}

@app.post("/api/assets/social_toggle")
async def toggle_asset_social(req: AssetSocialToggleRequest):
    updated = asset_manager.set_social_posted(req.rel_path, req.platform, req.posted, req.details)
    return {"success": True, "asset": updated}

@app.post("/api/assets/social_batch")
async def batch_asset_social(req: AssetSocialBatchRequest):
    updated = asset_manager.update_social_posted_batch(req.rel_path, req.platforms)
    return {"success": True, "asset": updated}

@app.post("/api/assets/open_metadata")
async def open_metadata(req: OpenMetadataRequest):
    active_path = config_manager.get_active_project()
    if not active_path:
        raise HTTPException(status_code=400, detail="No active project")

    meta_path = asset_manager.find_or_create_metadata_file(active_path, req.rel_path)
    if not meta_path or not meta_path.exists():
        raise HTTPException(status_code=404, detail="Metadata file not found and could not be created")

    # Read content for in-app modal viewer & editor
    content = ""
    try:
        content = meta_path.read_text(encoding="utf-8")
    except Exception:
        try:
            content = meta_path.read_text(encoding="cp1252", errors="replace")
        except Exception:
            pass

    resolved_file = str(meta_path.resolve())

    # Try launching editor on OS desktop if explicitly requested
    if req.launch_external:
        try:
            if sys.platform == "win32":
                try:
                    os.startfile(resolved_file)
                except Exception:
                    subprocess.Popen(["notepad.exe", resolved_file], shell=False)
            else:
                subprocess.Popen(["xdg-open", resolved_file], shell=False)
        except Exception as e:
            logging.warning(f"Could not open external editor: {e}")

    return {
        "success": True,
        "file_path": str(meta_path),
        "filename": meta_path.name,
        "content": content
    }

@app.post("/api/assets/save_metadata")
async def save_metadata(req: SaveMetadataRequest):
    active_path = config_manager.get_active_project()
    if not active_path:
        raise HTTPException(status_code=400, detail="No active project")

    meta_path = asset_manager.find_or_create_metadata_file(active_path, req.rel_path)
    try:
        meta_path.write_text(req.content, encoding="utf-8")
        return {
            "success": True,
            "file_path": str(meta_path),
            "filename": meta_path.name
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save metadata file: {str(e)}")

@app.post("/api/assets/reveal_in_explorer")
async def reveal_in_explorer(req: OpenMetadataRequest):
    active_path = config_manager.get_active_project()
    if not active_path:
        raise HTTPException(status_code=400, detail="No active project")

    meta_path = asset_manager.find_or_create_metadata_file(active_path, req.rel_path)
    if sys.platform == "win32":
        try:
            subprocess.Popen(["explorer.exe", f"/select,{str(meta_path.resolve())}"], shell=False)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reveal in explorer: {str(e)}")
    return {"success": True, "file_path": str(meta_path)}

@app.post("/api/assets/regenerate")
async def regenerate_asset(req: AssetRegenerateRequest):
    active_path = config_manager.get_active_project()
    if not active_path:
        raise HTTPException(status_code=400, detail="No active project")

    rel = req.rel_path.replace("\\", "/")
    # Parse chapter number
    import re
    m = re.search(r"chapter[_\s-]?(\d+)", rel, re.IGNORECASE)
    chapter_num = m.group(1) if m else None

    # Choose suitable script
    proj_p = Path(active_path)
    if chapter_num and (proj_p / "generate_video.py").exists():
        script = "generate_video.py"
        args = ["--chapter", chapter_num]
    elif chapter_num and (proj_p / "generate_chapter.py").exists():
        script = "generate_chapter.py"
        args = ["--chapter", chapter_num]
    elif "final" in rel.lower() and (proj_p / "combine_all_videos.py").exists():
        script = "combine_all_videos.py"
        args = ["--reencode"]
    elif (proj_p / "generate_video.py").exists():
        script = "generate_video.py"
        args = []
    else:
        raise HTTPException(status_code=400, detail="Could not determine regenerate script for this asset")

    # Mark as pending regeneration
    asset_manager.update_asset_status(req.rel_path, "regenerating", "Regeneration triggered from UI")

    # Launch process
    res = await process_runner.run_script(
        script_path=str(proj_p / script),
        cwd=str(proj_p),
        args=args
    )
    return {"success": True, "job": res, "script": script, "args": args}

# ----------------- Social Media APIs -----------------
@app.post("/api/social/publish")
async def publish_social(req: SocialPublishRequest):
    active_path = req.project_path or config_manager.get_active_project()
    if not active_path:
        raise HTTPException(status_code=400, detail="No active project")

    res = await social_dispatcher.publish_video(
        project_path_str=active_path,
        video_rel_path=req.rel_path,
        platforms=req.platforms,
        custom_title=req.title,
        custom_desc=req.description,
        custom_tags=req.tags,
        force_republish=req.force_republish or False,
        platform_captions=req.platform_captions,
        custom_pinned_comment=req.pinned_comment
    )
    return res
@app.get("/api/social/metadata/preview")
async def get_social_metadata_preview(rel_path: str = Query(...)):
    active_path = config_manager.get_active_project()
    if not active_path or not Path(active_path).exists():
        raise HTTPException(status_code=400, detail="No active project")
    base_p = Path(active_path)
    meta = social_dispatcher.extract_metadata_for_video(base_p, rel_path)
    return {
        "success": True,
        "metadata": meta
    }

@app.get("/api/social/format")
async def get_social_format(rel_path: str = Query(...)):
    """Format classification + per-platform routing, using the same rules as publish_video."""
    active_path = config_manager.get_active_project()
    if not active_path or not Path(active_path).exists():
        raise HTTPException(status_code=400, detail="No active project")
    base_p = Path(active_path).resolve()
    video_p = (base_p / rel_path).resolve()
    if not video_p.is_relative_to(base_p) or not video_p.is_file():
        raise HTTPException(status_code=404, detail="Video not found")
    media_info = await asyncio.to_thread(asset_manager.get_media_info, video_p)
    duration_sec = media_info.get("duration_sec") or 0.0
    fmt = social_dispatcher.classify_video_format(media_info.get("resolution"), duration_sec, rel_path)
    cfg = config_manager.get_project_social_config(active_path)
    routes = social_dispatcher.get_platform_routing(fmt["format"], duration_sec, cfg, media_info.get("duration") or "")

    # The modal also needs to know which accounts can actually be posted to right now
    connected = await asyncio.to_thread(_platform_connections)
    for plat, route in routes.items():
        route["connected"] = connected.get(plat, False)
        if route["eligible"] and not route["connected"]:
            route.update(eligible=False, reason=f"{PLATFORM_NAMES[plat]} isn't connected: {CONNECT_HINTS[plat]}.")
    return {
        "success": True,
        "format": fmt["format"],
        "aspect_ratio": fmt["aspect_ratio"],
        "duration_sec": duration_sec,
        "platforms": routes
    }

PLATFORM_NAMES = {"youtube": "YouTube", "facebook": "Facebook", "instagram": "Instagram", "threads": "Threads", "tiktok": "TikTok", "x": "X"}
CONNECT_HINTS = {
    "youtube": "use Connect next to YouTube above",
    "facebook": "use Connect next to Facebook above to add a Page access token",
    "instagram": "use Connect next to Facebook above (the Page token also covers Instagram)",
    "threads": "connect Threads in Studio settings",
    "tiktok": "add your TikTok session in Studio settings",
    "x": "X posting is not implemented yet"
}

def _platform_connections() -> Dict[str, bool]:
    return {
        "youtube": youtube_uploader.is_authenticated(),
        "facebook": bool(meta_uploader.page_token),
        "instagram": bool(meta_uploader.page_token and meta_uploader.ig_user_id),
        "threads": threads_uploader.is_authenticated(),
        "tiktok": tiktok_uploader.is_authenticated(),
        "x": False
    }

class MetaTokenRequest(BaseModel):
    page_token: str
    page_id: Optional[str] = None
    ig_user_id: Optional[str] = None

@app.post("/api/social/meta/token")
async def save_meta_token(req: MetaTokenRequest):
    """Validates and stores the Facebook Page token (covers Facebook + Instagram) in data/meta_token.json."""
    return await asyncio.to_thread(meta_uploader.save_credentials, req.page_token, req.page_id, req.ig_user_id)

@app.get("/api/social/config")
async def get_social_config(project_path: Optional[str] = Query(None)):
    target_path = project_path or config_manager.get_active_project()
    return config_manager.get_project_social_config(target_path)

@app.post("/api/social/config")
async def update_social_config(req: SocialConfigRequest):
    target_path = req.project_path or config_manager.get_active_project()
    if req.reset_to_default:
        res = config_manager.reset_project_social_config(target_path)
        return {"success": True, "reset": True, "social": res}

    data = req.model_dump(exclude_unset=True)
    data.pop("project_path", None)
    data.pop("reset_to_default", None)
    config_manager.update_project_social_config(target_path, data)
    return {"success": True, "social": config_manager.get_project_social_config(target_path)}

@app.post("/api/social/test_webhook")
async def test_webhook_endpoint(req: SocialTestWebhookRequest):
    return social_dispatcher.test_webhook(req.webhook_url, req.auth_header, req.project_path)

@app.get("/api/social/platforms/status")
async def get_social_platforms_status():
    meta_status = meta_uploader.get_status()
    threads_status = threads_uploader.get_status()
    yt_auth = youtube_uploader.is_authenticated()
    yt_info = youtube_uploader.get_channel_info() if yt_auth else {"authenticated": False}
    tiktok_status = tiktok_uploader.get_status()
    return {
        "success": True,
        "facebook": meta_status.get("facebook", {"active": False}),
        "instagram": meta_status.get("instagram", {"active": False}),
        "threads": threads_status,
        "youtube": {
            "authenticated": yt_auth,
            "channel": yt_info
        },
        "tiktok": tiktok_status,
        "oauth_bridge": get_oauth_bridge_status()
    }

async def _with_oauth_bridge_warning(res: Dict[str, Any], redirect_uri: Optional[str]) -> Dict[str, Any]:
    """When sign-in redirects to the local callback bridge, make sure it runs; if its port is taken
    (e.g. by n8n), keep the auth URL but tell the user to paste the redirect URL manually."""
    if res.get("success") and not redirect_uri:
        bridge = await asyncio.to_thread(ensure_oauth_bridge)
        if not bridge["running"]:
            res["warning"] = bridge["error"]
    return res

class YouTubeExchangeRequest(BaseModel):
    code: str
    redirect_uri: Optional[str] = None

@app.post("/api/social/youtube/exchange")
async def exchange_youtube_code(req: YouTubeExchangeRequest):
    res = youtube_uploader.exchange_code(req.code, req.redirect_uri)
    return res

@app.get("/api/social/youtube/auth_url")
async def get_youtube_auth_url(redirect_uri: Optional[str] = Query(None)):
    res = youtube_uploader.generate_auth_url(redirect_uri)
    return await _with_oauth_bridge_warning(res, redirect_uri)

@app.get("/api/social/youtube/callback")
async def handle_youtube_callback(code: str = Query(...)):
    res = youtube_uploader.exchange_code(code, "http://localhost:7860/api/social/youtube/callback")
    if res.get("success"):
        return HTMLResponse("""
        <html>
        <body style="background:#080b11;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="background:#101522;padding:40px;border-radius:16px;border:1px solid #232d42;text-align:center;max-width:400px;box-shadow:0 20px 40px rgba(0,0,0,0.5);">
                <div style="width:50px;height:50px;border-radius:50%;background:rgba(34,197,94,0.15);color:#22c55e;display:flex;align-items:center;justify-content:center;margin:0 auto 16px auto;font-size:24px;">✓</div>
                <h2 style="color:#ffffff;margin:0 0 8px 0;font-size:20px;">YouTube Connected!</h2>
                <p style="color:#94a3b8;font-size:13px;line-height:1.5;margin:0 0 20px 0;">Your YouTube channel has been authenticated successfully. Direct video and shorts upload is now enabled in KCT Studio.</p>
                <button onclick="window.close()" style="background:#FFE614;color:#000;border:none;padding:10px 24px;border-radius:8px;font-weight:bold;cursor:pointer;font-size:13px;">Close Window</button>
            </div>
        </body>
        </html>
        """)
    else:
        return HTMLResponse(f"<h3>OAuth Error:</h3><pre>{res.get('error')}</pre>")

# ----------------- Threads OAuth & API Endpoints -----------------
class ThreadsExchangeRequest(BaseModel):
    code: str
    redirect_uri: Optional[str] = None
    app_id: Optional[str] = None
    app_secret: Optional[str] = None

class ThreadsDirectTokenRequest(BaseModel):
    token: str
    threads_user_id: Optional[str] = None
    username: Optional[str] = None
    app_secret: Optional[str] = None
    public_base_url: Optional[str] = None

@app.get("/api/social/threads/status")
async def get_threads_status_endpoint():
    return threads_uploader.get_status()

@app.get("/api/social/threads/auth_url")
async def get_threads_auth_url(redirect_uri: Optional[str] = Query(None), app_id: Optional[str] = Query(None)):
    res = threads_uploader.generate_auth_url(redirect_uri, app_id)
    return await _with_oauth_bridge_warning(res, redirect_uri)

@app.post("/api/social/threads/exchange")
async def exchange_threads_code(req: ThreadsExchangeRequest):
    return threads_uploader.exchange_code(req.code, req.redirect_uri, req.app_id, req.app_secret)

@app.post("/api/social/threads/direct_token")
async def save_threads_direct_token_endpoint(req: ThreadsDirectTokenRequest):
    return threads_uploader.save_token_direct(
        token=req.token,
        threads_user_id=req.threads_user_id,
        username=req.username,
        app_secret=req.app_secret,
        public_base_url=req.public_base_url
    )

@app.get("/api/social/threads/callback")
async def handle_threads_callback(code: str = Query(...)):
    res = threads_uploader.exchange_code(code, "http://localhost:7860/api/social/threads/callback")
    if res.get("success"):
        u = res.get("username", "Threads User")
        return HTMLResponse(f"""
        <html>
        <body style="background:#080b11;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
            <div style="background:#101522;padding:40px;border-radius:16px;border:1px solid #232d42;text-align:center;max-width:400px;box-shadow:0 20px 40px rgba(0,0,0,0.5);">
                <div style="width:50px;height:50px;border-radius:50%;background:rgba(168,85,247,0.15);color:#a855f7;display:flex;align-items:center;justify-content:center;margin:0 auto 16px auto;font-size:24px;">@</div>
                <h2 style="color:#ffffff;margin:0 0 8px 0;font-size:20px;">Threads Connected!</h2>
                <p style="color:#94a3b8;font-size:13px;line-height:1.5;margin:0 0 20px 0;">Authenticated as <b>@{u}</b> via your Instagram account. Direct Reel & video posting is active.</p>
                <button onclick="window.close()" style="background:#a855f7;color:#fff;border:none;padding:10px 24px;border-radius:8px;font-weight:bold;cursor:pointer;font-size:13px;">Close Window</button>
            </div>
        </body>
        </html>
        """)
    else:
        return HTMLResponse(f"<h3>Threads OAuth Error:</h3><pre>{res.get('error')}</pre>")


# ----------------- TikTok Session & Upload Endpoints -----------------
class TikTokSessionRequest(BaseModel):
    sessionid: str
    username: Optional[str] = "biblestories832"
    account_name: Optional[str] = "BibleStories"

@app.get("/api/social/tiktok/status")
async def get_tiktok_status_endpoint():
    return tiktok_uploader.get_status()

@app.post("/api/social/tiktok/save_session")
async def save_tiktok_session_endpoint(req: TikTokSessionRequest):
    res = tiktok_uploader.save_session(req.sessionid, req.username, req.account_name)
    return res


# ----------------- Video Generator & Studio APIs -----------------
@app.get("/generator")
@app.get("/studio")
async def serve_generator_page():
    gen_file = Path(__file__).resolve().parent / "static" / "generator.html"
    if not gen_file.exists():
        raise HTTPException(status_code=404, detail="Generator page not found")
    return FileResponse(str(gen_file))

@app.get("/api/generator/weeks")
async def get_generator_weeks_api():
    active_path = config_manager.get_active_project()
    if not active_path or not Path(active_path).exists():
        return {"weeks": []}
    base_p = Path(active_path)

    from core.story_map_definitions import MASTER_WEEK_DEFINITIONS
    curriculum_by_w = {item["week"]: item for item in MASTER_WEEK_DEFINITIONS}
    
    weeks = []
    for w in range(1, 157):
        w_tag = f"W{w:02d}"
        w_dir = base_p / w_tag
        cur = curriculum_by_w.get(w, {})
        title = cur.get("title", f"Week {w}")
        has_dir = w_dir.exists()
        
        rendered_count = 0
        if has_dir:
            lf_dir = w_dir / "long_form"
            if lf_dir.exists() and any(p.suffix == ".mp4" and "temp" not in p.parts for p in lf_dir.glob("*.mp4")):
                rendered_count += 1
            r_dir = w_dir / "reels"
            if r_dir.exists():
                for sub in r_dir.iterdir():
                    if sub.is_dir() and any(p.suffix == ".mp4" and "temp" not in p.parts for p in sub.glob("*.mp4")):
                        rendered_count += 1
            s_dir = w_dir / "stories"
            if s_dir.exists():
                for sub in s_dir.iterdir():
                    if sub.is_dir() and any(p.suffix == ".mp4" and "temp" not in p.parts for p in sub.glob("*.mp4")):
                        rendered_count += 1

        weeks.append({
            "week_num": w,
            "week_tag": w_tag,
            "title": title,
            "theme": cur.get("theme", ""),
            "has_dir": has_dir,
            "rendered_count": rendered_count,
            "total_videos": 11,
            "has_scripts": has_dir and (w_dir / "long_form" / "script_30min.txt").exists()
        })
    return {"weeks": weeks}

def get_video_duration_fast(path: Path) -> float:
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]
        cf = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2.0, creationflags=cf)
        if res.returncode == 0 and res.stdout.strip():
            return float(res.stdout.strip())
    except Exception:
        pass
    return 0.0

@app.get("/api/generator/week/{week_id}")
async def get_generator_week_api(week_id: str):
    active_path = config_manager.get_active_project()
    if not active_path or not Path(active_path).exists():
        raise HTTPException(status_code=400, detail="No active project found")
    base_p = Path(active_path)

    clean_id = str(week_id).strip().upper().lstrip("W")
    try:
        w_num = int(clean_id)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid week identifier: {week_id}")

    w_tag = f"W{w_num:02d}"
    w_dir = base_p / w_tag

    from core.story_map_definitions import MASTER_WEEK_DEFINITIONS
    curriculum = None
    for item in MASTER_WEEK_DEFINITIONS:
        if item.get("week") == w_num:
            curriculum = item
            break

    title = f"Week {w_num}"
    theme = ""
    scriptures = ""
    christological_key = ""
    if curriculum:
        title = curriculum.get("title", title)
        theme = curriculum.get("theme", "")
        scs = curriculum.get("scriptures", [])
        scriptures = ", ".join(scs) if isinstance(scs, list) else str(scs)
        christological_key = curriculum.get("christological_key", "")

    # Long-Form Documentary (16:9)
    lf_dir = w_dir / "long_form"
    lf_data = {
        "title": title,
        "aspect_ratio": "16:9",
        "resolution": "1920x1080",
        "duration_target": "30-35 min",
        "script_status": "Missing",
        "script_word_count": 0,
        "script_file": None,
        "scene_count": 0,
        "is_rendered": False,
        "video_path": None,
        "video_url": None,
        "thumbnail_url": None,
        "video_size_mb": 0.0,
        "videos": []
    }

    if lf_dir.exists():
        lf_subdirs = sorted([d for d in lf_dir.iterdir() if d.is_dir() and d.name.lower() not in ["images", "temp", "__pycache__", "sample_2min_before_genesis"]])
        
        # Default fallback root thumbnail
        default_thumb_url = None
        for tn in ["thumbnail_option_1.jpg", "thumbnail.png", "thumbnail.jpg", "thumbnail_option_2.jpg"]:
            t_path = lf_dir / tn
            if t_path.exists():
                default_thumb_url = f"/api/thumbnail/{str(t_path.relative_to(base_p)).replace('\\', '/')}"
                break

        if lf_subdirs:
            # 1. Multi-Cut / Subfolder Architecture
            for s_idx, s_dir in enumerate(lf_subdirs):
                vid_num = s_idx + 1
                v_title = f"{title} (Cut {vid_num})"
                v_hook = ""
                v_desc = ""
                v_tags = []
                v_timestamps = []
                v_merch = ""
                v_pinned = ""
                v_fb = ""
                v_yt = ""
                v_ig = ""
                v_tt = ""
                v_x = ""
                v_scriptures = scriptures
                v_christ_key = christological_key
                v_theme = theme
                v_meta: Dict[str, Any] = {}

                # Check metadata inside subfolder
                for meta_name in ["metadata.json", "episode_metadata.json"]:
                    m_path = s_dir / meta_name
                    if m_path.exists():
                        try:
                            m_json = json.loads(m_path.read_text(encoding="utf-8"))
                            v_meta = m_json if isinstance(m_json, dict) else {}
                            v_title = m_json.get("title") or m_json.get("episode_title") or v_title
                            v_hook = m_json.get("hook") or ""
                            v_desc = m_json.get("description") or ""
                            v_tags = m_json.get("tags") or []
                            v_timestamps = m_json.get("timestamps") or []
                            v_merch = m_json.get("merch_block") or ""
                            v_pinned = m_json.get("pinned_comment") or ""
                            v_fb = m_json.get("facebook_caption") or ""
                            v_yt = m_json.get("youtube_description") or ""
                            v_ig = m_json.get("instagram_caption") or ""
                            v_tt = m_json.get("tiktok_caption") or ""
                            v_x = m_json.get("x_post") or ""
                            if m_json.get("scriptures"):
                                v_scriptures = m_json.get("scriptures")
                            if m_json.get("christological_key"):
                                v_christ_key = m_json.get("christological_key")
                            if m_json.get("curriculum_theme") or m_json.get("theme"):
                                v_theme = m_json.get("curriculum_theme") or m_json.get("theme")
                        except Exception:
                            pass
                        break

                # Social captions in the house format (same builder the publisher uses)
                caps = social_dispatcher.build_platform_captions(
                    v_meta or {"title": v_title, "scriptures": v_scriptures}, fallback_title=v_title
                )
                v_fb, v_yt, v_ig, v_tt, v_x = (caps[k] for k in ("facebook_caption", "youtube_description", "instagram_caption", "tiktok_caption", "x_post"))
                v_pinned = caps["pinned_comment"]

                # Script in subfolder
                s_file = None
                s_content = ""
                sw_count = 0
                for sc in ["script_30min.txt", "script.txt", "narration_script.txt", "script.md"]:
                    sp = s_dir / sc
                    if sp.exists():
                        s_file = sc
                        try:
                            s_content = sp.read_text(encoding="utf-8", errors="replace")
                            sw_count = len(s_content.split())
                        except Exception:
                            pass
                        break

                # Images in subfolder or root
                s_img_dir = s_dir / "images" if (s_dir / "images").exists() else (lf_dir / "images")
                scene_cnt = len(list(s_img_dir.glob("*.png")) + list(s_img_dir.glob("*.jpg"))) if s_img_dir.exists() else 0

                # Thumbnail in subfolder or root
                sub_thumb_url = default_thumb_url
                for tn in ["thumbnail.jpg", "thumbnail.png", "thumbnail_option_1.jpg", "thumbnail_option_2.jpg", "thumbnail_option_3.jpg"]:
                    tp = s_dir / tn
                    if tp.exists():
                        sub_thumb_url = f"/api/thumbnail/{str(tp.relative_to(base_p)).replace('\\', '/')}"
                        break

                # Video in subfolder
                s_mp4s = [p for p in s_dir.glob("*.mp4") if "temp" not in p.parts]
                vid_path_rel = None
                dur_sec = 0.0
                dur_formatted = "30–35 min"
                size_mb = 0.0

                if s_mp4s:
                    s_mp4s.sort(key=lambda x: (0 if "16x9" in x.name.lower() else (1 if "final" in x.name.lower() else 2)))
                    main_mp4 = s_mp4s[0]
                    vid_path_rel = str(main_mp4.relative_to(base_p)).replace("\\", "/")
                    dur_sec = get_video_duration_fast(main_mp4)
                    if dur_sec > 0:
                        mins = int(dur_sec // 60)
                        secs = int(dur_sec % 60)
                        dur_formatted = f"{mins}:{secs:02d}"
                    size_mb = round(main_mp4.stat().st_size / (1024 * 1024), 1)
                    if not sub_thumb_url:
                        sub_thumb_url = f"/api/thumbnail/{vid_path_rel}"

                # Clean short label
                raw_slug = s_dir.name
                if re.match(r'^\d+[_\-]', raw_slug):
                    raw_slug = re.sub(r'^\d+[_\-]', '', raw_slug)
                clean_short = raw_slug.replace("_", " ").title()[:24]

                v_obj = {
                    "index": s_idx,
                    "id": f"vid_{vid_num}",
                    "label": f"V{vid_num}: {clean_short} ({dur_formatted})",
                    "short_label": f"V{vid_num}: {clean_short}",
                    "tab_title": f"V{vid_num}",
                    "subfolder": s_dir.name,
                    "filename": s_mp4s[0].name if s_mp4s else None,
                    "video_path": vid_path_rel,
                    "video_url": f"/api/media/{vid_path_rel}" if vid_path_rel else None,
                    "thumbnail_url": sub_thumb_url,
                    "duration_sec": dur_sec,
                    "duration_formatted": dur_formatted,
                    "duration_target": "30–35 min",
                    "size_mb": size_mb,
                    "resolution": "1920x1080",
                    "scene_count": scene_cnt,
                    "script_file": s_file,
                    "script_word_count": sw_count,
                    "script_content": s_content,
                    "title": v_title,
                    "hook": v_hook,
                    "description": v_desc,
                    "scriptures": v_scriptures,
                    "christological_key": v_christ_key,
                    "timestamps": v_timestamps,
                    "merch_block": v_merch,
                    "tags": v_tags,
                    "hashtags": [f"#{t.replace(' ', '')}" for t in v_tags] if v_tags else [],
                    "facebook_caption": v_fb,
                    "youtube_description": v_yt,
                    "instagram_caption": v_ig,
                    "tiktok_caption": v_tt,
                    "threads_caption": caps["threads_caption"],
                    "x_post": v_x,
                    "pinned_comment": v_pinned
                }
                lf_data["videos"].append(v_obj)

        else:
            # 2. Legacy / Root long_form Architecture
            lf_meta: Dict[str, Any] = {}
            for meta_name in ["episode_metadata.json", "metadata.json"]:
                m_path = lf_dir / meta_name
                if m_path.exists():
                    try:
                        m_json = json.loads(m_path.read_text(encoding="utf-8"))
                        lf_meta = m_json if isinstance(m_json, dict) else {}
                        lf_data["title"] = m_json.get("title") or m_json.get("episode_title") or lf_data["title"]
                        lf_data["hook"] = m_json.get("hook") or ""
                        lf_data["description"] = m_json.get("description") or ""
                        lf_data["tags"] = m_json.get("tags") or []
                        lf_data["hashtags"] = m_json.get("hashtags") or [f"#{t.replace(' ', '')}" for t in lf_data["tags"]]
                        lf_data["timestamps"] = m_json.get("timestamps") or []
                        if m_json.get("scriptures"):
                            scriptures = m_json.get("scriptures")
                            lf_data["scriptures"] = scriptures
                        if m_json.get("christological_key"):
                            christological_key = m_json.get("christological_key")
                            lf_data["christological_key"] = christological_key
                        if m_json.get("curriculum_theme") or m_json.get("theme"):
                            theme = m_json.get("curriculum_theme") or m_json.get("theme")
                            lf_data["theme"] = theme
                    except Exception:
                        pass
                    break

            if not lf_data.get("scriptures"):
                lf_data["scriptures"] = scriptures
            if not lf_data.get("christological_key"):
                lf_data["christological_key"] = christological_key
            if not lf_data.get("theme"):
                lf_data["theme"] = theme

            # Social captions in the house format (same builder the publisher uses)
            caps = social_dispatcher.build_platform_captions(
                lf_meta or {"title": lf_data["title"], "scriptures": scriptures}, fallback_title=lf_data["title"]
            )
            for key in ("facebook_caption", "youtube_description", "instagram_caption", "tiktok_caption", "threads_caption", "x_post", "pinned_comment"):
                lf_data[key] = caps[key]

            for sc in ["script_30min.txt", "script.txt", "narration_script.txt", "script.md", "03_what_happened_before_genesis_30min.txt"]:
                s_path = lf_dir / sc
                if s_path.exists():
                    txt = s_path.read_text(encoding="utf-8", errors="replace")
                    lf_data["script_status"] = "Ready"
                    lf_data["script_word_count"] = len(txt.split())
                    lf_data["script_file"] = sc
                    lf_data["script_content"] = txt
                    break

            img_dir = lf_dir / "images"
            if img_dir.exists():
                imgs = list(img_dir.glob("*.png")) + list(img_dir.glob("*.jpg"))
                lf_data["scene_count"] = len(imgs)

            mp4s = [p for p in lf_dir.glob("*.mp4") if "temp" not in p.parts and "sample" not in p.name.lower()]
            if not mp4s:
                mp4s = [p for p in lf_dir.glob("*.mp4") if "temp" not in p.parts]
            if mp4s:
                mp4s.sort(key=lambda x: (
                    0 if "30min" in x.name.lower() and "16x9" in x.name.lower()
                    else (1 if "16x9" in x.name.lower() else (2 if "final" in x.name.lower() else 3))
                ))

                for idx, vid in enumerate(mp4s):
                    name_l = vid.name.lower()
                    if "30min" in name_l:
                        cut_label = "30-Min Master"
                        dur_target = "30–35 min"
                        s_file = "script_30min.txt" if (lf_dir / "script_30min.txt").exists() else "script.txt"
                    elif idx == 1 or "final" in name_l:
                        cut_label = f"Video Cut {idx+1}: Standard" if len(mp4s) > 1 else "Master Cut"
                        dur_target = "9–15 min"
                        s_file = "script.txt" if (lf_dir / "script.txt").exists() else "script_30min.txt"
                    else:
                        clean_nm = vid.stem.replace("_", " ").title()
                        cut_label = f"Video {idx+1}: {clean_nm[:20]}"
                        dur_target = "30–35 min"
                        s_file = "script.txt" if (lf_dir / "script.txt").exists() else "script_30min.txt"

                    dur_sec = get_video_duration_fast(vid)
                    if dur_sec > 0:
                        mins = int(dur_sec // 60)
                        secs = int(dur_sec % 60)
                        dur_formatted = f"{mins}:{secs:02d}"
                    else:
                        dur_formatted = dur_target

                    s_content = ""
                    sw_count = 0
                    if s_file and (lf_dir / s_file).exists():
                        try:
                            s_content = (lf_dir / s_file).read_text(encoding="utf-8", errors="replace")
                            sw_count = len(s_content.split())
                        except Exception:
                            pass

                    rel_v = str(vid.relative_to(base_p)).replace("\\", "/")
                    vid_thumb = default_thumb_url or f"/api/thumbnail/{rel_v}"

                    v_obj = {
                        "index": idx,
                        "id": f"vid_{idx+1}",
                        "label": f"{cut_label} ({dur_formatted})",
                        "short_label": cut_label,
                        "tab_title": f"V{idx+1}",
                        "filename": vid.name,
                        "video_path": rel_v,
                        "video_url": f"/api/media/{rel_v}",
                        "thumbnail_url": vid_thumb,
                        "duration_sec": dur_sec,
                        "duration_formatted": dur_formatted,
                        "duration_target": dur_target,
                        "size_mb": round(vid.stat().st_size / (1024 * 1024), 1),
                        "resolution": "1920x1080",
                        "scene_count": lf_data.get("scene_count", 0),
                        "script_file": s_file,
                        "script_word_count": sw_count,
                        "script_content": s_content or lf_data.get("script_content", ""),
                        "title": lf_data["title"],
                        "hook": lf_data.get("hook", ""),
                        "description": lf_data.get("description", ""),
                        "scriptures": lf_data.get("scriptures", ""),
                        "christological_key": lf_data.get("christological_key", ""),
                        "timestamps": lf_data.get("timestamps", []),
                        "merch_block": lf_data.get("merch_block", ""),
                        "tags": lf_data.get("tags", []),
                        "hashtags": lf_data.get("hashtags", []),
                        "facebook_caption": lf_data.get("facebook_caption", ""),
                        "youtube_description": lf_data.get("youtube_description", ""),
                        "instagram_caption": lf_data.get("instagram_caption", ""),
                        "tiktok_caption": lf_data.get("tiktok_caption", ""),
                        "threads_caption": lf_data.get("threads_caption", ""),
                        "x_post": lf_data.get("x_post", ""),
                        "pinned_comment": lf_data.get("pinned_comment", "")
                    }
                    lf_data["videos"].append(v_obj)

        # Sync primary video to top-level fields for seamless backwards compatibility
        if lf_data["videos"]:
            # Prefer video with rendered video_url, otherwise first video
            v_primary = next((v for v in lf_data["videos"] if v.get("video_url")), lf_data["videos"][0])
            lf_data["is_rendered"] = bool(v_primary.get("video_url"))
            lf_data["video_path"] = v_primary.get("video_path")
            lf_data["video_url"] = v_primary.get("video_url")
            lf_data["video_size_mb"] = v_primary.get("size_mb", 0.0)
            lf_data["duration_target"] = v_primary.get("duration_formatted") or v_primary.get("duration_target", "30–35 min")
            lf_data["thumbnail_url"] = v_primary.get("thumbnail_url") or default_thumb_url
            lf_data["title"] = v_primary.get("title", lf_data["title"])
            lf_data["hook"] = v_primary.get("hook", lf_data.get("hook", ""))
            lf_data["description"] = v_primary.get("description", lf_data.get("description", ""))
            lf_data["scene_count"] = v_primary.get("scene_count", lf_data.get("scene_count", 0))
            if v_primary.get("script_file"):
                lf_data["script_file"] = v_primary["script_file"]
                lf_data["script_word_count"] = v_primary["script_word_count"]
                lf_data["script_content"] = v_primary["script_content"]
                lf_data["script_status"] = "Ready"
        elif default_thumb_url:
            lf_data["thumbnail_url"] = default_thumb_url

    # 5 Daily Reels (9:16)
    reels_list = []
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    r_dir = w_dir / "reels"
    r_subdirs = sorted([d for d in r_dir.iterdir() if d.is_dir() and "temp" not in d.name.lower()]) if (r_dir.exists() and r_dir.is_dir()) else []

    for i in range(5):
        day_name = days[i]
        reel_num = i + 1
        prefix = f"0{reel_num}"
        target_sub = None
        for d in r_subdirs:
            if d.name.startswith(prefix) or d.name.startswith(f"{reel_num}_"):
                target_sub = d
                break
        if not target_sub and i < len(r_subdirs):
            target_sub = r_subdirs[i]

        global_reel_num = (w_num - 1) * 5 + reel_num
        r_info = {
            "num": reel_num,
            "global_num": global_reel_num,
            "day": day_name,
            "reel_id": f"REEL-{w_tag}.{reel_num}",
            "title": f"Reel {reel_num}",
            "hook": "",
            "caption": "",
            "scriptures": "",
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "duration_target": "55s",
            "script_status": "Missing",
            "script_word_count": 0,
            "script_preview": "",
            "is_rendered": False,
            "video_path": None,
            "video_url": None,
            "thumbnail_url": None,
            "video_size_mb": 0.0,
            "folder_name": target_sub.name if target_sub else None
        }

        if curriculum:
            if i < len(curriculum.get("reel_titles", [])):
                r_info["title"] = curriculum["reel_titles"][i]
            if i < len(curriculum.get("reel_hooks", [])):
                r_info["hook"] = curriculum["reel_hooks"][i]

        if target_sub:
            r_meta: Dict[str, Any] = {}
            m_path = target_sub / "metadata.json"
            txt_path = target_sub / "metadata.txt"
            if not m_path.exists() and txt_path.exists():
                # Older reels keep their metadata in metadata.txt
                r_meta = social_dispatcher.parse_metadata_txt(txt_path.read_text(encoding="utf-8", errors="replace"))
                r_info["title"] = r_meta.get("title") or r_info["title"]
                r_info["hook"] = r_meta.get("hook") or r_info["hook"]
                r_info["description"] = r_meta.get("description") or ""
                r_info["tags"] = r_meta.get("hashtags") or []
            if m_path.exists():
                try:
                    m_json = json.loads(m_path.read_text(encoding="utf-8"))
                    r_meta = m_json if isinstance(m_json, dict) else {}
                    r_info["title"] = m_json.get("title") or r_info["title"]
                    r_info["hook"] = m_json.get("hook") or r_info["hook"]
                    r_info["caption"] = m_json.get("caption") or ""
                    r_info["scriptures"] = m_json.get("scriptures") or ""
                    r_info["description"] = m_json.get("description") or ""
                    r_info["tags"] = m_json.get("tags") or m_json.get("hashtags") or []
                    if m_json.get("reel_id"):
                        r_info["reel_id"] = m_json.get("reel_id")
                except Exception:
                    pass

            # Social captions in the house format (same builder the publisher uses)
            caps = social_dispatcher.build_platform_captions(
                r_meta or {"title": r_info["title"], "hook": r_info["hook"]}, fallback_title=r_info["title"]
            )
            for key in ("facebook_caption", "youtube_description", "instagram_caption", "tiktok_caption", "threads_caption", "x_post", "pinned_comment"):
                r_info[key] = caps[key]

            s_path = target_sub / "script.txt"
            if s_path.exists():
                txt = s_path.read_text(encoding="utf-8", errors="replace")
                r_info["script_status"] = "Ready"
                r_info["script_word_count"] = len(txt.split())
                r_info["script_preview"] = txt.strip()[:200]
                r_info["script_content"] = txt

            mp4s = [p for p in target_sub.glob("*.mp4") if "temp" not in p.parts]
            if mp4s:
                mp4s.sort(key=lambda x: (
                    0 if "final_reel" in x.name.lower()
                    else (1 if "master" in x.name.lower() else 2)
                ))
                vid = mp4s[0]
                rel_vid = str(vid.relative_to(base_p)).replace("\\", "/")
                r_info["is_rendered"] = True
                r_info["video_path"] = rel_vid
                r_info["video_url"] = f"/api/media/{rel_vid}"
                r_info["thumbnail_url"] = f"/api/thumbnail/{rel_vid}"
                r_info["video_size_mb"] = round(vid.stat().st_size / (1024 * 1024), 1)

            # Always look for a thumbnail/scene background image for the reel card
            if not r_info["thumbnail_url"]:
                thumb_candidates = [
                    target_sub / "thumbnail.jpg",
                    target_sub / "thumbnail.png",
                ]
                # Also check images/ folder for any generated scene image
                imgs_dir = target_sub / "images"
                if imgs_dir.exists():
                    scene_imgs = sorted([
                        f for f in imgs_dir.iterdir()
                        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
                        and f.stat().st_size > 10000
                        and "hook" not in f.name.lower()
                    ])
                    thumb_candidates.extend(scene_imgs)

                for tc in thumb_candidates:
                    if tc.exists() and tc.stat().st_size > 5000:
                        rel_tc = str(tc.relative_to(base_p)).replace("\\", "/")
                        r_info["thumbnail_url"] = f"/api/thumbnail/{rel_tc}"
                        break

        reels_list.append(r_info)

    # 5 Daily Stories (9:16)
    stories_list = []
    s_dir = w_dir / "stories"
    s_subdirs = sorted([d for d in s_dir.iterdir() if d.is_dir() and "temp" not in d.name.lower()]) if (s_dir.exists() and s_dir.is_dir()) else []

    for i in range(5):
        day_name = days[i]
        story_num = i + 1
        prefix = f"0{story_num}"
        target_sub = None
        for d in s_subdirs:
            if d.name.startswith(prefix) or d.name.startswith(f"{story_num}_") or d.name.startswith(f"{story_num}-"):
                target_sub = d
                break
        if not target_sub and i < len(s_subdirs):
            target_sub = s_subdirs[i]

        s_info = {
            "num": story_num,
            "day": day_name,
            "story_id": f"STRY-{w_tag}.{story_num}",
            "title": f"Story {story_num}",
            "reference": "",
            "total_slides": 5,
            "sound_suggestion": "",
            "aspect_ratio": "9:16",
            "script_status": "Missing",
            "script_word_count": 0,
            "is_rendered": False,
            "video_path": None,
            "video_url": None,
            "thumbnail_url": None,
            "video_size_mb": 0.0,
            "folder_name": target_sub.name if target_sub else None
        }

        if target_sub:
            m_path = target_sub / "metadata.json"
            if m_path.exists():
                try:
                    m_json = json.loads(m_path.read_text(encoding="utf-8"))
                    s_info["title"] = m_json.get("title") or s_info["title"]
                    s_info["reference"] = m_json.get("reference") or ""
                    s_info["total_slides"] = m_json.get("total_slides", 5)
                    s_info["sound_suggestion"] = m_json.get("sound_suggestion") or ""
                    if m_json.get("story_id"):
                        s_info["story_id"] = m_json.get("story_id")
                except Exception:
                    pass

            sc_path = target_sub / "story_script.md"
            if sc_path.exists():
                txt = sc_path.read_text(encoding="utf-8", errors="replace")
                s_info["script_status"] = "Ready"
                s_info["script_word_count"] = len(txt.split())
                s_info["script_content"] = txt

            mp4s = [p for p in target_sub.glob("*.mp4") if "temp" not in p.parts]
            if mp4s:
                vid = mp4s[0]
                rel_vid = str(vid.relative_to(base_p)).replace("\\", "/")
                s_info["is_rendered"] = True
                s_info["video_path"] = rel_vid
                s_info["video_url"] = f"/api/media/{rel_vid}"
                s_info["video_size_mb"] = round(vid.stat().st_size / (1024 * 1024), 1)

            # Check for cover thumbnail or slide preview image
            thumb_candidates = [
                target_sub / "thumbnail.png",
                target_sub / "thumbnail.jpg",
                target_sub / "slide_1.png",
                target_sub / "slide_1.jpg",
                target_sub / "images" / "slide_1.png",
                target_sub / "images" / "slide_1.jpg",
            ]
            for tc in thumb_candidates:
                if tc.exists() and tc.stat().st_size > 1000:
                    rel_tc = str(tc.relative_to(base_p)).replace("\\", "/")
                    s_info["thumbnail_url"] = f"/api/thumbnail/{rel_tc}"
                    break

            if not s_info["thumbnail_url"] and s_info["is_rendered"] and s_info["video_path"]:
                s_info["thumbnail_url"] = f"/api/thumbnail/{s_info['video_path']}"

        stories_list.append(s_info)

    rendered_count = (1 if lf_data["is_rendered"] else 0) + sum(1 for r in reels_list if r["is_rendered"]) + sum(1 for s in stories_list if s["is_rendered"])

    return {
        "week_num": w_num,
        "week_tag": w_tag,
        "title": title,
        "theme": theme,
        "scriptures": scriptures,
        "christological_key": christological_key,
        "rendered_count": rendered_count,
        "total_videos": 11,
        "long_form": lf_data,
        "reels": reels_list,
        "stories": stories_list
    }

@app.get("/api/generator/script")
async def get_generator_script(
    week: str = Query(...),
    type: str = Query("long_form"),
    target_num: Optional[int] = Query(None),
    filename: Optional[str] = Query(None)
):
    active_path = config_manager.get_active_project()
    if not active_path or not Path(active_path).exists():
        raise HTTPException(status_code=400, detail="No active project")
    base_p = Path(active_path)
    
    clean_w = str(week).upper().strip()
    if not re.fullmatch(r"W?\d{1,3}", clean_w):
        raise HTTPException(status_code=400, detail=f"Invalid week identifier: {week}")
    w_tag = f"W{int(clean_w.lstrip('W')):02d}"
    w_dir = base_p / w_tag
    if not w_dir.exists():
        raise HTTPException(status_code=404, detail=f"Week folder {w_tag} not found")

    # Only bare filenames inside the resolved target folder may be read
    if filename and (Path(filename).name != filename or filename in (".", "..")):
        raise HTTPException(status_code=400, detail="Invalid filename")

    target_dir = None
    meta_candidates = []
    script_candidates = []

    if type == "long_form":
        lf_base = w_dir / "long_form"
        subdirs = sorted([d for d in lf_base.iterdir() if d.is_dir() and d.name.lower() not in ["images", "temp", "__pycache__", "sample_2min_before_genesis"]]) if lf_base.exists() else []
        if target_num and subdirs:
            num = target_num
            for d in subdirs:
                if d.name.startswith(f"0{num}") or d.name.startswith(f"{num}_") or d.name.startswith(f"{num}-"):
                    target_dir = d
                    break
            if not target_dir and 1 <= num <= len(subdirs):
                target_dir = subdirs[num - 1]
        if not target_dir:
            target_dir = lf_base
        meta_candidates = ["episode_metadata.json", "metadata.json"]
        script_candidates = [filename] if filename else ["script_30min.txt", "script.txt", "narration_script.txt", "script.md", "03_what_happened_before_genesis_30min.txt"]
    elif type == "reel":
        num = target_num or 1
        r_dir = w_dir / "reels"
        subdirs = sorted([d for d in r_dir.iterdir() if d.is_dir() and "temp" not in d.name.lower()]) if r_dir.exists() else []
        for d in subdirs:
            if d.name.startswith(f"0{num}") or d.name.startswith(f"{num}_") or d.name.startswith(f"{num}-"):
                target_dir = d
                break
        if not target_dir and num <= len(subdirs):
            target_dir = subdirs[num - 1]
        if not target_dir:
            raise HTTPException(status_code=404, detail=f"Reel 0{num} folder not found")
        meta_candidates = ["metadata.json", "metadata.txt"]
        script_candidates = [filename] if filename else ["script.txt", "script.md"]
    elif type == "story":
        num = target_num or 1
        s_dir = w_dir / "stories"
        subdirs = sorted([d for d in s_dir.iterdir() if d.is_dir() and "temp" not in d.name.lower()]) if s_dir.exists() else []
        for d in subdirs:
            if d.name.startswith(f"0{num}") or d.name.startswith(f"{num}_") or d.name.startswith(f"{num}-"):
                target_dir = d
                break
        if not target_dir and num <= len(subdirs):
            target_dir = subdirs[num - 1]
        if not target_dir:
            raise HTTPException(status_code=404, detail=f"Story 0{num} folder not found")
        meta_candidates = ["metadata.json", "metadata.txt"]
        script_candidates = [filename] if filename else ["story_script.md", "script.txt", "script.md"]
    else:
        raise HTTPException(status_code=400, detail=f"Invalid type: {type}")

    meta = {}
    for mc in meta_candidates:
        mp = target_dir / mc
        if mp.exists():
            try:
                meta = json.loads(mp.read_text(encoding="utf-8"))
                break
            except Exception:
                pass

    script_text = ""
    found_filename = ""
    for sc in script_candidates:
        if not sc:
            continue
        sp = (target_dir / sc).resolve()
        if not sp.is_relative_to(w_dir.resolve()):
            continue
        if sp.exists() and sp.is_file():
            script_text = sp.read_text(encoding="utf-8", errors="replace")
            found_filename = sp.name
            break

    word_count = len(script_text.split()) if script_text else 0

    return {
        "success": True,
        "title": meta.get("title") or target_dir.name,
        "filename": found_filename,
        "word_count": word_count,
        "content": script_text,
        "metadata": meta
    }

@app.post("/api/generator/run")
async def run_generator_api(req: GeneratorRunRequest):
    active_path = config_manager.get_active_project()
    if not active_path or not Path(active_path).exists():
        raise HTTPException(status_code=400, detail="No active project")
    base_p = Path(active_path)

    w_tag = f"W{req.week:02d}"
    w_dir = base_p / w_tag

    script_path = None
    args = []
    cwd = str(base_p)

    if req.type == "long_form":
        script_candidates = [
            base_p / "generate_video.py",
            base_p / "scripts" / "generate_video.py",
            Path(__file__).resolve().parent / "scripts" / "generate_video.py",
            w_dir / "long_form" / "generate_video.py"
        ]
        script_path = next((p for p in script_candidates if p.exists()), None)
        if not script_path:
            raise HTTPException(status_code=404, detail="generate_video.py not found in project")
        args = ["--week", str(req.week), "--force-rebuild"]
        if req.target_num:
            args.extend(["--video", str(req.target_num)])
        cwd = str(base_p)

    elif req.type == "reel":
        target_num = req.target_num or 1
        script_candidates = [
            base_p / "generate_reel.py",
            base_p / "scripts" / "generate_reel.py",
            Path(__file__).resolve().parent / "scripts" / "generate_reel.py"
        ]
        script_path = next((p for p in script_candidates if p.exists()), None)
        if not script_path:
            raise HTTPException(status_code=404, detail="generate_reel.py not found in project")
        args = ["--week", str(req.week), "--reel", str(target_num), "--force-rebuild"]

    elif req.type == "regen_thumbnail":
        target_num = req.target_num or 1
        script_candidates = [
            base_p / "generate_reel.py",
            base_p / "scripts" / "generate_reel.py",
            Path(__file__).resolve().parent / "scripts" / "generate_reel.py"
        ]
        script_path = next((p for p in script_candidates if p.exists()), None)
        if not script_path:
            raise HTTPException(status_code=404, detail="generate_reel.py not found in project")
        args = ["--week", str(req.week), "--reel", str(target_num), "--thumbnail-only"]

    elif req.type == "combine_ad":
        target_num = req.target_num or 1
        script_candidates = [
            base_p / "generate_reel.py",
            base_p / "scripts" / "generate_reel.py",
            Path(__file__).resolve().parent / "scripts" / "generate_reel.py"
        ]
        script_path = next((p for p in script_candidates if p.exists()), None)
        if not script_path:
            raise HTTPException(status_code=404, detail="generate_reel.py not found in project")
        args = ["--week", str(req.week), "--reel", str(target_num), "--ads", str(req.ad_variant or 1), "--combine-ad"]
        if req.regen_thumb:
            args.append("--thumbnail-only")

    elif req.type == "all_reels":
        script_candidates = [
            base_p / "generate_reel.py",
            base_p / "scripts" / "generate_reel.py",
            Path(__file__).resolve().parent / "scripts" / "generate_reel.py"
        ]
        script_path = next((p for p in script_candidates if p.exists()), None)
        if not script_path:
            raise HTTPException(status_code=404, detail="generate_reel.py not found in project")
        args = ["--week", str(req.week), "--all", "--force-rebuild"]

    elif req.type == "story":
        target_num = req.target_num or 1
        script_candidates = [
            base_p / "scripts" / "generate_story.py",
            base_p / "generate_story.py",
            Path(__file__).resolve().parent / "scripts" / "generate_story.py"
        ]
        script_path = next((p for p in script_candidates if p.exists()), None)
        if not script_path:
            raise HTTPException(status_code=404, detail="generate_story.py not found in project")
        args = ["--week", str(req.week), "--story", str(target_num), "--force-rebuild"]

    elif req.type == "regen_story_thumbnail":
        target_num = req.target_num or 1
        script_candidates = [
            base_p / "scripts" / "generate_story.py",
            base_p / "generate_story.py",
            Path(__file__).resolve().parent / "scripts" / "generate_story.py"
        ]
        script_path = next((p for p in script_candidates if p.exists()), None)
        if not script_path:
            raise HTTPException(status_code=404, detail="generate_story.py not found in project")
        args = ["--week", str(req.week), "--story", str(target_num), "--thumbnail-only"]

    elif req.type == "all_stories":
        script_candidates = [
            base_p / "scripts" / "generate_story.py",
            base_p / "generate_story.py",
            Path(__file__).resolve().parent / "scripts" / "generate_story.py"
        ]
        script_path = next((p for p in script_candidates if p.exists()), None)
        if not script_path:
            raise HTTPException(status_code=404, detail="generate_story.py not found in project")
        args = ["--week", str(req.week), "--all", "--force-rebuild"]

    elif req.type == "all_week":
        if (base_p / "generate_video.py").exists():
            script_path = base_p / "generate_video.py"
            args = ["--week", str(req.week)]
        elif (base_p / "scripts" / "generate_video.py").exists():
            script_path = base_p / "scripts" / "generate_video.py"
            args = ["--week", str(req.week)]
        elif (base_p / "generate_reel.py").exists():
            script_path = base_p / "generate_reel.py"
            args = ["--week", str(req.week)]
        elif (base_p / "scripts" / "generate_story.py").exists():
            script_path = base_p / "scripts" / "generate_story.py"
            args = ["--week", str(req.week), "--all"]
        else:
            raise HTTPException(status_code=404, detail="Generation scripts not found")

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported generator target type: {req.type}")

    res = await process_runner.run_script(
        script_path=str(script_path),
        cwd=cwd,
        args=args
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res

# ----------------- Video Posting Calendar Planner APIs -----------------
@app.get("/calendar")
async def serve_calendar_page():
    cal_file = Path(__file__).resolve().parent / "static" / "calendar.html"
    if not cal_file.exists():
        raise HTTPException(status_code=404, detail="Calendar page not found")
    return FileResponse(str(cal_file))

# ----------------- Master Story Map & Curriculum APIs -----------------
@app.get("/story-map")
async def serve_story_map_page():
    map_file = Path(__file__).resolve().parent / "static" / "story_map.html"
    if not map_file.exists():
        map_file = Path(__file__).resolve().parent / "static" / "index.html"
    return FileResponse(str(map_file))

@app.get("/api/story-map")
async def get_story_map_api(
    year: Optional[int] = Query(None),
    quarter: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    return story_map_manager.get_curriculum(year=year, quarter=quarter, status=status, search=search)

@app.get("/api/story-map/week/{week_num}")
async def get_story_map_week_api(week_num: int):
    detail = story_map_manager.get_week_detail(week_num)
    if not detail:
        raise HTTPException(status_code=404, detail="Week not found")
    return detail

@app.post("/api/story-map/refresh")
async def refresh_story_map_api():
    story_map_manager.refresh_covered_status()
    return story_map_manager.get_curriculum()

@app.get("/api/calendar/schedule")
async def get_calendar_schedule(
    project_path: Optional[str] = Query(None),
    month: Optional[int] = Query(None),
    year: Optional[int] = Query(None),
    status: Optional[str] = Query(None)
):
    return calendar_manager.get_schedule(project_path=project_path, month=month, year=year, status=status)

@app.post("/api/calendar/schedule")
async def add_calendar_schedule(req: CalendarScheduleRequest):
    proj_path = req.project_path or config_manager.get_active_project()
    try:
        entry = calendar_manager.schedule_video(
            project_path=proj_path,
            video_rel_path=req.video_rel_path,
            date_str=req.scheduled_date,
            time_str=req.scheduled_time,
            platforms=req.platforms,
            title=req.title,
            force=req.force or False
        )
        return {"success": True, "entry": entry}
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/calendar/schedule/{post_id}")
async def update_calendar_schedule(post_id: str, req: CalendarUpdateRequest):
    try:
        updated = calendar_manager.update_post(
            post_id=post_id,
            date_str=req.scheduled_date,
            time_str=req.scheduled_time,
            platforms=req.platforms,
            force=req.force or False,
            status=req.status
        )
        return {"success": True, "entry": updated}
    except KeyError:
        raise HTTPException(status_code=404, detail="Schedule post not found")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/calendar/schedule/{post_id}")
async def delete_calendar_schedule(post_id: str):
    removed = calendar_manager.delete_post(post_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Schedule post not found")
    return {"success": True, "deleted_id": post_id}

@app.post("/api/calendar/schedule/{post_id}/post_now")
async def trigger_post_now(
    post_id: str, 
    force_republish: bool = Query(False),
    platforms: Optional[str] = Query(None)
):
    items = calendar_manager._load_all()
    item = next((it for it in items if it.get("id") == post_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Schedule post not found")
    # If item["title"] is just the filename stem, allow extract_metadata_for_video to supply the true title
    passed_title = item.get("title")
    vid_stem_title = Path(item["video_rel_path"]).stem.replace("_", " ").title()
    if passed_title == vid_stem_title:
        passed_title = None

    target_platforms = [p.strip().lower() for p in platforms.split(",") if p.strip()] if platforms else item.get("platforms", ["youtube"])
    item["platforms"] = target_platforms

    res = await social_dispatcher.publish_video(
        project_path_str=item["project_path"],
        video_rel_path=item["video_rel_path"],
        platforms=target_platforms,
        custom_title=passed_title,
        force_republish=force_republish
    )
    import datetime
    now_iso = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    item["posted_at"] = now_iso
    item["dispatch_result"] = res
    if res.get("title"):
        item["title"] = res["title"]
    if (res.get("success", False) or res.get("simulated", False)) and not res.get("skipped", False):
        item["status"] = "posted"
        asset_manager.update_social_posted_batch(item["video_rel_path"], target_platforms)
    else:
        item["status"] = "failed"
        item["error"] = res.get("message") or res.get("error", "Dispatch failed or skipped")
    calendar_manager._save_all(items)
    return {"success": item["status"] == "posted", "entry": item, "dispatch": res}

@app.post("/api/calendar/schedule/{post_id}/pre_upload")
async def trigger_pre_upload(
    post_id: str,
    platforms: Optional[str] = Query(None)
):
    target_platforms = [p.strip().lower() for p in platforms.split(",") if p.strip()] if platforms else None
    try:
        res = await calendar_manager.pre_upload_post(
            post_id=post_id,
            platforms=target_platforms,
            social_dispatcher=social_dispatcher
        )
        return res
    except KeyError:
        raise HTTPException(status_code=404, detail="Schedule post not found")
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/calendar/auto_schedule")
async def auto_schedule_posts(req: CalendarAutoScheduleRequest):
    target_path = req.project_path or config_manager.get_active_project()
    new_items = calendar_manager.auto_schedule_approved_videos(target_path)
    return {"success": True, "scheduled_count": len(new_items), "items": new_items}

@app.get("/api/calendar/next_slot")
async def get_next_calendar_slot(project_path: Optional[str] = Query(None), platforms: Optional[str] = Query(None)):
    target_path = project_path or config_manager.get_active_project()
    plat_list = [p.strip() for p in platforms.split(",")] if platforms else None
    slot = calendar_manager.find_next_available_slot(target_path, plat_list)
    return slot

@app.get("/api/calendar/unposted_approved_videos")
async def get_unposted_approved_videos(project_path: Optional[str] = Query(None)):
    target_path = project_path or config_manager.get_active_project()
    all_assets = asset_manager.get_assets(target_path)
    existing_items = calendar_manager.get_schedule(project_path=target_path)
    scheduled_paths = {it["video_rel_path"].lower() for it in existing_items if it.get("status") in ("scheduled", "posted")}
    approved_unposted = [
        a for a in all_assets
        if a.get("status") == "approved"
        and not a.get("hidden", False)
        and a.get("rel_path", "").lower() not in scheduled_paths
    ]
    return {"videos": approved_unposted}

@app.get("/api/social/template/n8n")
async def get_n8n_template():
    template_file = Path(__file__).resolve().parent / "docs" / "n8n_social_posting_workflow.json"
    if not template_file.exists():
        raise HTTPException(status_code=404, detail="n8n workflow template not found")
    try:
        import json
        data = json.loads(template_file.read_text(encoding="utf-8"))
        return JSONResponse(
            content=data,
            headers={"Content-Disposition": "attachment; filename=n8n_social_posting_workflow.json"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ----------------- Hardware & System APIs -----------------
@app.get("/api/system/stats")
async def get_system():
    comfy_url = config_manager.get("comfyui", {}).get("url", "http://127.0.0.1:8188")
    return get_system_stats(comfy_url)

# ----------------- Media Streaming Route (HTTP 206 Partial Content) -----------------
@app.api_route("/api/media/{file_path:path}", methods=["GET", "HEAD"])
async def stream_media(file_path: str, request: Request):
    active_path = Path(config_manager.get_active_project())
    target = (active_path / file_path).resolve()

    # Security check: ensure target starts within allowed project directory or is valid file
    if not target.exists() or not target.is_file():
        # Fallback check across all configured project paths
        found = False
        for p in config_manager.get("projects", []):
            alt = (Path(p["path"]) / file_path).resolve()
            if alt.exists() and alt.is_file():
                target = alt
                found = True
                break
        if not found:
            raise HTTPException(status_code=404, detail="File not found")

    mime_type, _ = mimetypes.guess_type(str(target))
    if not mime_type:
        mime_type = "application/octet-stream"

    return FileResponse(target, media_type=mime_type, filename=target.name)
 
@app.api_route("/api/video/{file_path:path}", methods=["GET", "HEAD"])
async def stream_video_alias(file_path: str, request: Request):
    return await stream_media(file_path, request)

@app.get("/api/thumbnail/{file_path:path}")
async def get_thumbnail(file_path: str):
    active_path = Path(config_manager.get_active_project())
    target = (active_path / file_path).resolve()

    if not target.exists() or not target.is_file():
        # Fallback check across all configured project paths
        for p in config_manager.get("projects", []):
            alt = (Path(p["path"]) / file_path).resolve()
            if alt.exists() and alt.is_file():
                target = alt
                break

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    # If the requested file is already an image, serve it
    if target.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
        mime_type, _ = mimetypes.guess_type(str(target))
        return FileResponse(
            target,
            media_type=mime_type or "image/jpeg",
            headers={"Cache-Control": "public, max-age=86400"}
        )

    # If video, first check for custom thumbnail file in folder (e.g. thumbnail_option_1.jpg)
    if target.suffix.lower() in [".mp4", ".mov", ".webm", ".mkv"]:
        from core.social_dispatcher import social_dispatcher
        custom_thumb = social_dispatcher.find_custom_thumbnail(target.parent, target.name)
        if custom_thumb and custom_thumb.exists():
            mime_type, _ = mimetypes.guess_type(str(custom_thumb))
            return FileResponse(
                custom_thumb,
                media_type=mime_type or "image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"}
            )

        # Fallback to extracted frame thumbnail
        thumb = await asyncio.to_thread(asset_manager.get_or_create_thumbnail, target)
        if thumb and thumb.exists():
            return FileResponse(
                thumb,
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=86400"}
            )

    raise HTTPException(status_code=404, detail="Thumbnail not available")

# ----------------- Serve UI Frontend -----------------
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.get("/favicon.ico")
async def serve_favicon_ico():
    ico_file = STATIC_DIR / "favicon.ico"
    if ico_file.exists():
        return FileResponse(ico_file, media_type="image/x-icon")
    return HTMLResponse("", status_code=404)

@app.get("/favicon.svg")
async def serve_favicon_svg():
    svg_file = STATIC_DIR / "favicon.svg"
    if svg_file.exists():
        return FileResponse(svg_file, media_type="image/svg+xml")
    return HTMLResponse("", status_code=404)

@app.get("/")
async def serve_index():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return HTMLResponse(content=index_file.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>KCT Studio - static/index.html loading...</h1>")

def ensure_port_free(port: int):
    """Detects and terminates any stale process listening on the target port."""
    current_pid = os.getpid()
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['pid'] == current_pid:
                continue
            try:
                conns = getattr(proc, 'net_connections', proc.connections)('inet')
                for conn in conns:
                    if conn.laddr.port == port:
                        print(f"[Server] Port {port} is occupied by existing PID {proc.info['pid']} ({proc.info['name']}). Freeing port...")
                        proc.kill()
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        time.sleep(0.5)
    except Exception as e:
        print(f"[Server] Warning while checking port {port}: {e}")

if __name__ == "__main__":
    cfg = config_manager.get("server", {})
    host = cfg.get("host", "0.0.0.0")
    port = cfg.get("port", 7860)
    ssl_enabled = cfg.get("ssl_enabled", True)

    # Automatically free port if occupied by a previous stale instance
    ensure_port_free(port)

    ssl_kwargs = {}
    if ssl_enabled:
        try:
            cert_file, key_file = cert_manager.ensure_certificates()
            if cert_file.exists() and key_file.exists():
                ssl_kwargs["ssl_certfile"] = str(cert_file.resolve())
                ssl_kwargs["ssl_keyfile"] = str(key_file.resolve())
                protocol = "https"
            else:
                protocol = "http"
        except Exception as e:
            print(f"[Warning] Failed to initialize SSL certificates: {e}. Falling back to HTTP.")
            protocol = "http"
    else:
        protocol = "http"

    local_ip = cert_manager.get_local_ip()
    print("=" * 60)
    print(f"  KCT Studio v2.0 - AI Video Pipeline")
    print(f"  Local URL:  {protocol}://localhost:{port}")
    print(f"  IPv4 URL:   {protocol}://127.0.0.1:{port}")
    if local_ip and local_ip not in ("127.0.0.1", "0.0.0.0"):
        print(f"  LAN URL:    {protocol}://{local_ip}:{port}")
    if ssl_kwargs:
        print(f"  SSL Cert:   certs/cert.pem (Active)")
        print(f"  Windows Trust: Run install_certificate.bat to trust certificate")
    print("=" * 60)

    uvicorn.run(app, host=host, port=port, log_level="info", **ssl_kwargs)
