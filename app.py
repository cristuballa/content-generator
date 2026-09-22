import os
import sys
import time
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

    scheduler_task = None
    async def scheduler_loop():
        while True:
            try:
                await asyncio.sleep(30)
                await calendar_manager.execute_due_posts(social_dispatcher)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"[Scheduler] Error executing due posts: {e}")

    try:
        scheduler_task = asyncio.create_task(scheduler_loop())
    except Exception as e:
        logging.warning(f"Could not start calendar scheduler task: {e}")

    yield

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
    status: Optional[str] = Query(None)
):
    active_path = config_manager.get_active_project()
    if not active_path or not Path(active_path).exists():
        return {"assets": []}

    assets = await asyncio.to_thread(asset_manager.scan_assets, active_path, include_hidden=include_hidden, filter_type=filter_type)
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
    active_path = config_manager.get_active_project()
    if not active_path:
        raise HTTPException(status_code=400, detail="No active project")

    res = await social_dispatcher.publish_video(
        project_path_str=active_path,
        video_rel_path=req.rel_path,
        platforms=req.platforms,
        custom_title=req.title,
        custom_desc=req.description,
        custom_tags=req.tags
    )
    return res

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

# ----------------- Video Posting Calendar Planner APIs -----------------
@app.get("/calendar")
async def serve_calendar_page():
    cal_file = Path(__file__).resolve().parent / "static" / "calendar.html"
    if not cal_file.exists():
        raise HTTPException(status_code=404, detail="Calendar page not found")
    return FileResponse(str(cal_file))

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
            force=req.force or False
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
async def trigger_post_now(post_id: str):
    item = calendar_manager.get_post_by_id(post_id)
    if not item:
        raise HTTPException(status_code=404, detail="Schedule post not found")
    res = await social_dispatcher.publish_video(
        project_path_str=item["project_path"],
        video_rel_path=item["video_rel_path"],
        platforms=item["platforms"],
        custom_title=item.get("title")
    )
    import datetime
    now_iso = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    item["posted_at"] = now_iso
    item["dispatch_result"] = res
    if res.get("success", False) or res.get("simulated", False):
        item["status"] = "posted"
        asset_manager.update_social_posted_batch(item["video_rel_path"], item["platforms"])
    else:
        item["status"] = "failed"
        item["error"] = res.get("error", "Dispatch failed")
    calendar_manager._save_all(calendar_manager._load_all())
    return {"success": item["status"] == "posted", "entry": item, "dispatch": res}

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
@app.get("/api/media/{file_path:path}")
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

    # If video, extract or fetch cached initial frame
    if target.suffix.lower() in [".mp4", ".mov", ".webm", ".mkv"]:
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
