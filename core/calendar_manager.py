import json
import time
import os
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from core.config import config_manager
from core.asset_manager import asset_manager

SCHEDULE_FILE = Path(__file__).resolve().parent.parent / "data" / "posting_schedule.json"

class CalendarManager:
    def __init__(self, schedule_file: Path = SCHEDULE_FILE):
        self.schedule_file = schedule_file
        self.schedule_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_file()

    def _ensure_file(self):
        if not self.schedule_file.exists():
            try:
                self.schedule_file.write_text("[]", encoding="utf-8")
            except Exception as e:
                print(f"[Calendar] Error creating {self.schedule_file}: {e}")

    def _load_all(self) -> List[Dict[str, Any]]:
        self._ensure_file()
        try:
            raw = self.schedule_file.read_text(encoding="utf-8")
            data = json.loads(raw)
            if isinstance(data, list):
                return data
            return []
        except Exception as e:
            print(f"[Calendar] Error loading schedule file: {e}")
            return []

    def _save_all(self, items: List[Dict[str, Any]]):
        try:
            self.schedule_file.parent.mkdir(parents=True, exist_ok=True)
            self.schedule_file.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"[Calendar] Error saving schedule file: {e}")

    def get_schedule(self, project_path: Optional[str] = None, month: Optional[int] = None, year: Optional[int] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns scheduled posts filtered by project, year, month, or status."""
        items = self._load_all()
        filtered = []

        norm_project = None
        if project_path and project_path != "all":
            try:
                norm_project = str(Path(project_path).resolve()).lower()
            except Exception:
                norm_project = str(project_path).lower()

        for item in items:
            # Project filter
            if norm_project:
                item_proj = ""
                try:
                    item_proj = str(Path(item.get("project_path", "")).resolve()).lower()
                except Exception:
                    item_proj = str(item.get("project_path", "")).lower()
                if item_proj != norm_project:
                    continue

            # Status filter
            if status and item.get("status") != status:
                continue

            # Date filter (YYYY-MM-DD)
            sdate = item.get("scheduled_date", "")
            if month or year:
                try:
                    dt = datetime.date.fromisoformat(sdate)
                    if year and dt.year != year:
                        continue
                    if month and dt.month != month:
                        continue
                except Exception:
                    continue

            # Ensure scheduled (unposted) items inherit current platforms from their project if not set
            if item.get("status") == "scheduled" and not item.get("platforms"):
                item_proj_path = item.get("project_path")
                if item_proj_path:
                    proj_plats = config_manager.get_project_platforms(item_proj_path)
                    enabled_plats = [p for p in ["youtube", "facebook", "instagram", "tiktok", "x"] if proj_plats.get(p, False)]
                    if enabled_plats:
                        item["platforms"] = enabled_plats

            # Attach published platforms from asset_manager
            try:
                rec = asset_manager.get_asset_record(item.get("video_rel_path", ""))
                pub = rec.get("published", {})
                item["published_platforms"] = [p for p, pd in pub.items() if isinstance(pd, dict) and pd.get("status") == "published"]
            except Exception:
                item["published_platforms"] = []

            # Backfill video duration if missing
            if not item.get("duration"):
                try:
                    vid_p = Path(item.get("project_path", "")) / item.get("video_rel_path", "")
                    if vid_p.exists():
                        rec = asset_manager.get_asset_record(item.get("video_rel_path", ""))
                        info = asset_manager.get_media_info(vid_p, rec)
                        item["duration"] = info.get("duration") or ""
                except Exception:
                    pass

            # Auto-heal title if missing or matching generic filename stem
            item_vrel = item.get("video_rel_path", "")
            item_proj = item.get("project_path", "")
            if item_vrel and item_proj:
                vid_stem = Path(item_vrel).stem.replace("_", " ").title()
                cur_title = item.get("title", "")
                if not cur_title or cur_title == vid_stem:
                    try:
                        from core.social_dispatcher import social_dispatcher
                        mdata = social_dispatcher.extract_metadata_for_video(Path(item_proj), item_vrel)
                        if mdata.get("title"):
                            item["title"] = mdata["title"]
                    except Exception:
                        pass

            filtered.append(item)

        # Sort chronologically by scheduled_datetime_iso
        filtered.sort(key=lambda x: (x.get("scheduled_datetime_iso", ""), x.get("scheduled_date", ""), x.get("scheduled_time", "")))
        return filtered

    def get_post_by_id(self, post_id: str) -> Optional[Dict[str, Any]]:
        items = self._load_all()
        for it in items:
            if it.get("id") == post_id:
                return it
        return None

    def validate_slot(self, project_path: str, date_str: str, platforms: List[str], exclude_post_id: Optional[str] = None) -> Dict[str, Any]:
        """Validates the 1 post per account/platform in a day rule for a project."""
        items = self._load_all()
        norm_proj = ""
        try:
            norm_proj = str(Path(project_path).resolve()).lower()
        except Exception:
            norm_proj = str(project_path).lower()

        conflicts = []
        for it in items:
            if it.get("id") == exclude_post_id:
                continue
            if it.get("status") in ("cancelled", "failed"):
                continue
            if it.get("scheduled_date") != date_str:
                continue

            it_proj = ""
            try:
                it_proj = str(Path(it.get("project_path", "")).resolve()).lower()
            except Exception:
                it_proj = str(it.get("project_path", "")).lower()

            if it_proj == norm_proj:
                it_plats = it.get("platforms", [])
                for p in platforms:
                    if p in it_plats:
                        conflicts.append({
                            "platform": p,
                            "existing_id": it.get("id"),
                            "existing_title": it.get("title", ""),
                            "scheduled_time": it.get("scheduled_time", "")
                        })

        return {
            "valid": len(conflicts) == 0,
            "conflicts": conflicts
        }

    def find_next_available_slot(self, project_path: str, platforms: Optional[List[str]] = None, start_date_str: Optional[str] = None) -> Dict[str, Any]:
        """Finds the earliest available calendar day where none of the target platforms already have a post scheduled."""
        cfg = config_manager.get_project_social_config(project_path)
        default_time = cfg.get("default_posting_time", "18:00")
        
        target_platforms = platforms
        if not target_platforms:
            proj_plats = config_manager.get_project_platforms(project_path)
            target_platforms = [p for p in ["youtube", "facebook", "instagram", "tiktok", "x"] if proj_plats.get(p, False)]
            if not target_platforms:
                target_platforms = ["youtube"]

        now = datetime.datetime.now()
        start_date = now.date()
        if start_date_str:
            try:
                start_date = datetime.date.fromisoformat(start_date_str)
            except Exception:
                start_date = now.date()

        # Parse default time
        try:
            hour, minute = map(int, default_time.split(":")[:2])
        except Exception:
            hour, minute = 18, 0
            default_time = "18:00"

        # If starting from today, verify if default_time has already elapsed today
        offset = 0
        if start_date == now.date():
            target_dt_today = datetime.datetime(now.year, now.month, now.day, hour, minute)
            if now >= target_dt_today:
                # Today's posting time has passed; start checking from tomorrow
                offset = 1

        for d in range(offset, 365):
            candidate_date = start_date + datetime.timedelta(days=d)
            cand_str = candidate_date.strftime("%Y-%m-%d")
            res = self.validate_slot(project_path, cand_str, target_platforms)
            if res["valid"]:
                return {
                    "date": cand_str,
                    "time": default_time,
                    "datetime_iso": f"{cand_str}T{default_time}:00",
                    "platforms": target_platforms
                }

        # Fallback to tomorrow if somehow full
        fallback_date = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        return {
            "date": fallback_date,
            "time": default_time,
            "datetime_iso": f"{fallback_date}T{default_time}:00",
            "platforms": target_platforms
        }

    def schedule_video(
        self,
        project_path: str,
        video_rel_path: str,
        date_str: Optional[str] = None,
        time_str: Optional[str] = None,
        platforms: Optional[List[str]] = None,
        title: Optional[str] = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """Schedules an approved video for posting on a specific date/time or auto-assigns next slot."""
        cfg = config_manager.get_project_social_config(project_path)
        proj_name = cfg.get("project_name") or Path(project_path).name

        all_plats = ["youtube", "facebook", "instagram", "tiktok", "x"]
        if platforms:
            target_platforms = platforms
        else:
            proj_plats = config_manager.get_project_platforms(project_path)
            target_platforms = [p for p in all_plats if proj_plats.get(p, False)]
            if not target_platforms:
                target_platforms = ["youtube"]

        # Calculate slot if not fully specified
        if not date_str or not time_str:
            slot = self.find_next_available_slot(project_path, target_platforms, start_date_str=date_str)
            date_str = date_str or slot["date"]
            time_str = time_str or slot["time"]

        # Validate date is not in the past
        today_iso = datetime.date.today().isoformat()
        if not force and date_str < today_iso:
            raise ValueError(f"Cannot schedule post to a past date ({date_str}). Please select today or a future date.")

        # Multi-post per day enabled: allow multiple videos/images per day per project.
        # Sequential daily slot assignment is still maintained on approval via find_next_available_slot.

        # Resolve video metadata
        vid_path = Path(project_path) / video_rel_path
        vid_filename = vid_path.name
        vid_title = title
        if not vid_title:
            try:
                from core.social_dispatcher import social_dispatcher
                mdata = social_dispatcher.extract_metadata_for_video(Path(project_path), video_rel_path)
                if mdata.get("title") and mdata["title"] != vid_path.stem.replace("_", " ").title():
                    vid_title = mdata["title"]
            except Exception:
                pass
            if not vid_title:
                vid_title = vid_path.stem.replace("_", " ").title()

        # Resolve episode number
        ep_num = None
        try:
            for a in asset_manager.get_assets(project_path):
                if a.get("rel_path", "").replace("\\", "/").lower() == video_rel_path.replace("\\", "/").lower():
                    ep_num = a.get("episode_num")
                    break
        except Exception:
            pass
        if ep_num is None:
            import re
            m = re.search(r'(?:reels[/\\]|#|^|\/|_)(\d{1,4})(?:_|\s|-|\.|$)', video_rel_path, re.IGNORECASE)
            if m:
                try:
                    ep_num = int(m.group(1))
                except Exception:
                    pass

        # Resolve video duration
        vid_duration = ""
        try:
            rec = asset_manager.get_asset_record(video_rel_path)
            info = asset_manager.get_media_info(vid_path, rec)
            vid_duration = info.get("duration") or ""
        except Exception:
            pass

        # Thumbnail URL
        thumb_url = f"/api/thumbnail/{video_rel_path.replace(os.sep, '/')}"

        # Clean iso datetime
        clean_time = time_str
        if len(clean_time) == 5:
            clean_time += ":00"
        dt_iso = f"{date_str}T{clean_time}"

        new_entry = {
            "id": f"sched_{int(time.time())}_{uuid.uuid4().hex[:6]}",
            "project_path": str(Path(project_path).resolve()),
            "project_name": proj_name,
            "video_rel_path": video_rel_path.replace("\\", "/"),
            "video_filename": vid_filename,
            "episode_num": ep_num,
            "title": vid_title,
            "thumbnail_url": thumb_url,
            "duration": vid_duration,
            "scheduled_date": date_str,
            "scheduled_time": time_str,
            "scheduled_datetime_iso": dt_iso,
            "platforms": target_platforms,
            "status": "scheduled",
            "created_at": datetime.datetime.now().isoformat(),
            "posted_at": None,
            "error": None,
            "dispatch_result": None
        }

        items = self._load_all()
        # If this video already had a scheduled entry for this project, replace or update it
        norm_vrel = video_rel_path.replace("\\", "/").lower()
        items = [it for it in items if not (it.get("status") == "scheduled" and it.get("video_rel_path", "").lower() == norm_vrel)]
        items.append(new_entry)
        self._save_all(items)

        return new_entry

    def update_post(self, post_id: str, date_str: str, time_str: str, platforms: Optional[List[str]] = None, force: bool = False, status: Optional[str] = None) -> Dict[str, Any]:
        """Reschedules an existing post or updates status."""
        items = self._load_all()
        target = None
        for it in items:
            if it.get("id") == post_id:
                target = it
                break

        if not target:
            raise KeyError(f"Post with ID {post_id} not found.")

        # Validate date is not in the past
        today_iso = datetime.date.today().isoformat()
        if not force and date_str < today_iso:
            raise ValueError(f"Cannot reschedule post to a past date ({date_str}). Please select today or a future date.")

        target_platforms = platforms if platforms is not None else target.get("platforms", ["youtube"])

        # Multi-post per day enabled: allow rescheduling without collision error.

        # Backfill episode_num if missing
        if target.get("episode_num") is None:
            import re
            m = re.search(r'(?:reels[/\\]|#|^|\/|_)(\d{1,4})(?:_|\s|-|\.|$)', target.get("video_rel_path", ""), re.IGNORECASE)
            if m:
                try:
                    target["episode_num"] = int(m.group(1))
                except Exception:
                    pass

        clean_time = time_str
        if len(clean_time) == 5:
            clean_time += ":00"

        target["scheduled_date"] = date_str
        target["scheduled_time"] = time_str
        target["scheduled_datetime_iso"] = f"{date_str}T{clean_time}"
        target["platforms"] = target_platforms

        if status:
            target["status"] = status
            if status == "posted":
                target["error"] = None
                target["posted_at"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                asset_manager.update_social_posted_batch(target["video_rel_path"], target_platforms)
            elif status == "scheduled":
                target["error"] = None
                target["posted_at"] = None
                target["dispatch_result"] = None
                for p in target_platforms:
                    asset_manager.set_social_posted(target["video_rel_path"], p, False)
        elif target["status"] in ("failed", "posted"):
            target["status"] = "scheduled"
            target["error"] = None
            target["posted_at"] = None
            target["dispatch_result"] = None
            for p in target_platforms:
                asset_manager.set_social_posted(target["video_rel_path"], p, False)
        elif target.get("status") == "scheduled":
            target["error"] = None
            target["posted_at"] = None
            target["dispatch_result"] = None
            for p in target_platforms:
                asset_manager.set_social_posted(target["video_rel_path"], p, False)

        self._save_all(items)
        return target

    def delete_post(self, post_id: str) -> bool:
        """Cancels/removes a scheduled post."""
        items = self._load_all()
        initial_len = len(items)
        items = [it for it in items if it.get("id") != post_id]
        if len(items) < initial_len:
            self._save_all(items)
            return True
        return False

    def remove_schedule_for_video(self, project_path: str, video_rel_path: str) -> int:
        """Removes any pending (not yet posted) scheduled items for a video when unapproved."""
        items = self._load_all()
        norm_proj = ""
        try:
            norm_proj = str(Path(project_path).resolve()).lower()
        except Exception:
            norm_proj = str(project_path).lower()
        norm_rel = video_rel_path.replace("\\", "/").lower()

        kept = []
        removed_count = 0
        for it in items:
            it_proj = ""
            try:
                it_proj = str(Path(it.get("project_path", "")).resolve()).lower()
            except Exception:
                it_proj = str(it.get("project_path", "")).lower()
            it_rel = it.get("video_rel_path", "").replace("\\", "/").lower()
            if it_proj == norm_proj and it_rel == norm_rel and it.get("status") == "scheduled":
                removed_count += 1
                continue
            kept.append(it)

        if removed_count > 0:
            self._save_all(kept)
        return removed_count

    def auto_schedule_approved_videos(self, project_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Finds all approved videos not yet scheduled/posted and assigns consecutive future daily slots."""
        target_path = project_path or config_manager.get_active_project()
        if not target_path or not Path(target_path).exists():
            return []

        # Load project catalog
        catalog = asset_manager.load_catalog(target_path)
        all_assets = asset_manager.get_assets(target_path)

        # Collect existing scheduled or posted rel_paths
        existing_items = self._load_all()
        scheduled_or_posted_paths = set()
        for it in existing_items:
            if it.get("status") in ("scheduled", "posted"):
                scheduled_or_posted_paths.add(it.get("video_rel_path", "").replace("\\", "/").lower())

        # Filter approved videos
        approved_to_schedule = []
        for asset in all_assets:
            if asset.get("status") != "approved":
                continue
            if asset.get("hidden", False):
                continue
            rel = asset.get("rel_path", "").replace("\\", "/")
            if rel.lower() in scheduled_or_posted_paths:
                continue

            # Check if already published across all platforms
            pub = asset.get("published", {})
            if any(pub.values()) and not asset.get("status") == "approved":
                continue

            approved_to_schedule.append(asset)

        if not approved_to_schedule:
            return []

        # Sort sequentially by chapter/filename
        approved_to_schedule.sort(key=lambda a: (a.get("chapter_tag", ""), a.get("filename", "")))

        proj_plats = config_manager.get_project_platforms(target_path)
        platforms = [p for p in ["youtube", "facebook", "instagram", "tiktok", "x"] if proj_plats.get(p, False)]
        if not platforms:
            platforms = ["youtube"]

        scheduled_results = []
        for asset in approved_to_schedule:
            rel = asset.get("rel_path", "").replace("\\", "/")
            slot = self.find_next_available_slot(target_path, platforms)
            new_item = self.schedule_video(
                project_path=target_path,
                video_rel_path=rel,
                date_str=slot["date"],
                time_str=slot["time"],
                platforms=platforms,
                title=asset.get("clean_title") or asset.get("filename")
            )
            scheduled_results.append(new_item)

        return scheduled_results

    async def execute_due_posts(self, social_dispatcher) -> List[Dict[str, Any]]:
        """Scans for scheduled posts that are due now and dispatches them."""
        items = self._load_all()
        now_dt = datetime.datetime.now()
        now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%S")

        executed = []
        changed = False

        for it in items:
            if it.get("status") != "scheduled":
                continue

            dt_iso = it.get("scheduled_datetime_iso") or f"{it.get('scheduled_date', '')}T{it.get('scheduled_time', '00:00')}:00"
            if dt_iso <= now_iso:
                # Post is due for publishing!
                proj_path = it.get("project_path", "")
                video_rel = it.get("video_rel_path", "")
                platforms = it.get("platforms", [])

                try:
                    res = await social_dispatcher.publish_video(
                        project_path_str=proj_path,
                        video_rel_path=video_rel,
                        platforms=platforms,
                        custom_title=it.get("title"),
                        force_republish=True
                    )

                    it["posted_at"] = now_iso
                    it["dispatch_result"] = res
                    if (res.get("success", False) or res.get("simulated", False)) and not res.get("skipped", False):
                        it["status"] = "posted"
                        # Mark asset social published status
                        asset_manager.update_social_posted_batch(video_rel, platforms)
                    else:
                        it["status"] = "failed"
                        it["error"] = res.get("message") or res.get("error", "Dispatch failed or skipped")

                    executed.append(it)
                    changed = True

                except Exception as e:
                    it["status"] = "failed"
                    it["error"] = str(e)
                    executed.append(it)
                    changed = True

        if changed:
            self._save_all(items)

        return executed

calendar_manager = CalendarManager()
