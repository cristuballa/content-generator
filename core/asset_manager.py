import json
import os
import sys
import time
import subprocess
import shutil
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "media_catalog.json"

class AssetManager:
    def __init__(self, data_file: Path = DATA_FILE):
        self.data_file = data_file
        self._data = self._load_data()

    def _load_data(self) -> Dict[str, Any]:
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[AssetManager] Error loading {self.data_file}: {e}")
        return {"assets": {}}

    def _save_data(self):
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
        except Exception as e:
            print(f"[AssetManager] Error saving data: {e}")

    def get_asset_record(self, rel_path: str) -> Dict[str, Any]:
        norm = rel_path.replace("\\", "/")
        return self._data.setdefault("assets", {}).setdefault(norm, {
            "status": "pending",  # pending, approved, rejected
            "hidden": False,
            "notes": "",
            "approved_at": None,
            "reviewed_at": None,
            "published": {}
        })

    def update_asset_status(self, rel_path: str, status: str, notes: Optional[str] = None) -> Dict[str, Any]:
        rec = self.get_asset_record(rel_path)
        rec["status"] = status
        rec["reviewed_at"] = time.time()
        if status == "approved":
            rec["approved_at"] = time.time()
        if notes is not None:
            rec["notes"] = notes
        self._save_data()
        return rec

    def toggle_hidden(self, rel_path: str, hidden: Optional[bool] = None) -> Dict[str, Any]:
        rec = self.get_asset_record(rel_path)
        if hidden is None:
            rec["hidden"] = not rec.get("hidden", False)
        else:
            rec["hidden"] = hidden
        self._save_data()
        return rec

    def mark_published(self, rel_path: str, platform: str, details: Dict[str, Any]):
        rec = self.get_asset_record(rel_path)
        published = rec.setdefault("published", {})
        published[platform] = {
            "status": "published",
            "time": time.time(),
            "details": details
        }
        self._save_data()

    def set_social_posted(self, rel_path: str, platform: str, posted: bool, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        rec = self.get_asset_record(rel_path)
        published = rec.setdefault("published", {})
        aliases = {"fb": "facebook", "yt": "youtube", "tt": "tiktok", "inst": "instagram", "twitter": "x"}
        key = aliases.get(platform.lower(), platform.lower())
        if posted:
            published[key] = {
                "status": "published",
                "time": time.time(),
                "details": details or {"manual": True}
            }
        else:
            published.pop(key, None)
        self._save_data()
        return rec

    def update_social_posted_batch(self, rel_path: str, platforms: Dict[str, bool]) -> Dict[str, Any]:
        rec = self.get_asset_record(rel_path)
        published = rec.setdefault("published", {})
        aliases = {"fb": "facebook", "yt": "youtube", "tt": "tiktok", "inst": "instagram", "twitter": "x"}
        for plat, posted in platforms.items():
            key = aliases.get(plat.lower(), plat.lower())
            if posted:
                if key not in published:
                    published[key] = {
                        "status": "published",
                        "time": time.time(),
                        "details": {"manual": True}
                    }
            else:
                published.pop(key, None)
        self._save_data()
        return rec

    def find_or_create_metadata_file(self, project_path_str: str, rel_path: str) -> Path:
        """Locates or creates a metadata text/json file for a video asset to be opened in Notepad."""
        base_p = Path(project_path_str)
        clean_rel = rel_path.replace("\\", "/").lstrip("/")
        video_p = base_p / clean_rel
        folder = video_p.parent if video_p.is_file() or video_p.suffix else video_p

        check_folders = [folder]
        if folder.parent != base_p and folder.parent.exists():
            check_folders.append(folder.parent)

        # 1. Search for existing metadata / script files
        for fld in check_folders:
            if not fld.exists():
                continue
            for name in [
                "metadata.json", "metadata.txt", "youtube_metadata.md", "youtube_metadata.txt",
                "script.txt", "script.md", "script_35min.txt", "script_clean.txt", "scenes_prompts.json"
            ]:
                cand = fld / name
                if cand.exists() and cand.is_file():
                    return cand

            for cand in fld.glob("*metadata*.*"):
                if cand.is_file():
                    return cand

        # 2. If none found, create a template metadata.txt in the video's folder
        target_file = folder / "metadata.txt"
        clean_title = video_p.stem.replace("_", " ").title()
        template = f"""Title: {clean_title}
Video File: {video_p.name}
Description: 
Tags: 
Timestamps:
00:00 - Introduction
"""
        try:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            target_file.write_text(template, encoding="utf-8")
        except Exception as e:
            print(f"[AssetManager] Error creating metadata template: {e}")
        return target_file

    def get_media_info(self, file_path: Path, rec: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        stat = file_path.stat()
        info = {
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "modified": stat.st_mtime,
            "modified_str": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
            "duration": None,
            "resolution": None
        }

        # Check cached probe info
        if rec and rec.get("probe_mtime") == stat.st_mtime and rec.get("duration"):
            info["duration"] = rec.get("duration")
            info["resolution"] = rec.get("resolution")
            return info

        # Use ffprobe if available
        if shutil.which("ffprobe") and file_path.suffix.lower() in [".mp4", ".mov", ".webm", ".mkv"]:
            try:
                cmd = [
                    "ffprobe", "-v", "error",
                    "-show_entries", "format=duration:stream=width,height",
                    "-of", "json", str(file_path)
                ]
                creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5, creationflags=creationflags)
                if res.returncode == 0:
                    probe = json.loads(res.stdout)
                    fmt = probe.get("format", {})
                    if "duration" in fmt:
                        dur_sec = float(fmt["duration"])
                        mins = int(dur_sec // 60)
                        secs = int(dur_sec % 60)
                        info["duration_sec"] = round(dur_sec, 1)
                        info["duration"] = f"{mins}:{secs:02d}"
                    streams = probe.get("streams", [])
                    for s in streams:
                        if "width" in s and "height" in s:
                            info["resolution"] = f"{s['width']}x{s['height']}"
                            break

                    # Save to rec cache
                    if rec is not None:
                        rec["duration"] = info["duration"]
                        rec["resolution"] = info["resolution"]
                        rec["probe_mtime"] = stat.st_mtime
            except Exception:
                pass
        return info

    def get_or_create_thumbnail(self, video_path: Path) -> Optional[Path]:
        """Extracts and caches the initial frame (poster thumbnail) from a video using ffmpeg."""
        try:
            thumb_dir = Path(__file__).resolve().parent.parent / "data" / "thumbnails"
            thumb_dir.mkdir(parents=True, exist_ok=True)

            stat = video_path.stat()
            import hashlib
            path_hash = hashlib.md5(f"{str(video_path.resolve())}_{stat.st_mtime}".encode("utf-8")).hexdigest()
            thumb_file = thumb_dir / f"{path_hash}.jpg"

            if thumb_file.exists() and thumb_file.stat().st_size > 100:
                return thumb_file

            ffmpeg_bin = shutil.which("ffmpeg")
            if not ffmpeg_bin:
                return None

            # Fast seek: extract frame at 0.1s
            cmd = [
                ffmpeg_bin,
                "-ss", "0.1",
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "3",
                "-vf", "scale=640:-1",
                str(thumb_file),
                "-y"
            ]
            creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            res = subprocess.run(cmd, capture_output=True, timeout=6, creationflags=creationflags)
            if res.returncode == 0 and thumb_file.exists() and thumb_file.stat().st_size > 100:
                return thumb_file

            # Fallback seek from start if 0.1s seek failed
            cmd_fallback = [
                ffmpeg_bin,
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "3",
                "-vf", "scale=640:-1",
                str(thumb_file),
                "-y"
            ]
            res_fb = subprocess.run(cmd_fallback, capture_output=True, timeout=6, creationflags=creationflags)
            if res_fb.returncode == 0 and thumb_file.exists() and thumb_file.stat().st_size > 100:
                return thumb_file

        except Exception as e:
            print(f"[AssetManager] Error generating initial frame thumbnail for {video_path}: {e}")
        return None

    def scan_assets(self, project_path_str: str, include_hidden: bool = False, filter_type: Optional[str] = None) -> List[Dict[str, Any]]:
        project_path = Path(project_path_str)
        if not project_path.exists():
            return []

        results = []
        # Find all mp4 files
        for f in project_path.rglob("*.mp4"):
            # Exclude cache / temp chunks if too small
            if f.name.startswith("temp_") and f.stat().st_size < 1000:
                continue

            rel = str(f.relative_to(project_path)).replace("\\", "/")
            rec = self.get_asset_record(rel)

            if rec.get("hidden", False) and not include_hidden:
                continue

            # Classify category
            name_lower = f.name.lower()
            rel_lower = rel.lower()
            if "final" in name_lower or "full_story" in name_lower or f.parent == project_path:
                category = "final_master"
            elif "chapter" in rel_lower or "slideshow" in rel_lower or "reels" in rel_lower:
                category = "chapter_reel"
            else:
                category = "scene_clip"

            if filter_type and filter_type != "all" and category != filter_type:
                continue

            # Check for adjacent thumbnail
            thumb_rel = None
            parent_images = f.parent.parent / "images"
            if parent_images.exists():
                first_img = next(parent_images.glob("*.png"), None)
                if first_img:
                    thumb_rel = str(first_img.relative_to(project_path)).replace("\\", "/")

            media_info = self.get_media_info(f, rec)

            # Determine chapter / episode association
            from core.project_scanner import parse_numbered_folder
            in_numbered_episode = False
            episode_folder = ""
            episode_rel_path = ""
            episode_num = None
            chapter_tag = "Master"

            rel_parts = Path(rel).parts[:-1]
            for i, part in enumerate(rel_parts):
                parsed = parse_numbered_folder(part)
                if parsed:
                    in_numbered_episode = True
                    episode_folder = part
                    episode_rel_path = "/".join(rel_parts[:i+1]).replace("\\", "/")
                    episode_num = parsed["episode_num"]
                    if "chapter" in part.lower():
                        chapter_tag = f"Chapter {episode_num}"
                    else:
                        chapter_tag = f"#{episode_num:02d} {parsed['clean_title']}"
                    break

            results.append({
                "id": rel,
                "filename": f.name,
                "rel_path": rel,
                "abs_path": str(f),
                "category": category,
                "chapter_tag": chapter_tag,
                "in_numbered_episode": in_numbered_episode,
                "episode_folder": episode_folder,
                "episode_rel_path": episode_rel_path,
                "episode_num": episode_num,
                "status": rec.get("status", "pending"),
                "hidden": rec.get("hidden", False),
                "notes": rec.get("notes", ""),
                "approved_at": rec.get("approved_at"),
                "reviewed_at": rec.get("reviewed_at"),
                "published": rec.get("published", {}),
                "size_mb": media_info["size_mb"],
                "duration": media_info.get("duration") or "N/A",
                "resolution": media_info.get("resolution") or "16:9 HD",
                "modified": media_info["modified"],
                "modified_str": media_info["modified_str"],
                "thumbnail_rel": thumb_rel,
                "thumbnail_url": f"/api/thumbnail/{urllib.parse.quote(rel, safe='/')}"
            })

        self._save_data()
        # Default sort: date descending (latest -> oldest)
        results.sort(key=lambda x: x.get("modified", 0), reverse=True)
        return results

asset_manager = AssetManager()
