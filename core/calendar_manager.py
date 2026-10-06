import asyncio
import json
import logging
import time
import os
import uuid
import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from core.config import config_manager
from core.asset_manager import asset_manager
from core.meta_uploader import meta_uploader
from core.staging import (BUSINESS_SUITE_LOOKUP, MAX_STAGE_ATTEMPTS, MIN_STAGE_LEAD, QUOTA_PAUSE_SEC, STAGE_RETRY_SEC,
                          business_suite_platforms, cancel_copy, due_datetime, is_quota_error, is_story_path,
                          match_instagram_post, move_copy, native_platforms, release_copy)
from core.reels import reel_day_and_time, reel_posting_times
from core.week_links import export_week_links, is_reel, week_of

SCHEDULE_FILE = Path(__file__).resolve().parent.parent / "data" / "posting_schedule.json"

# Stories get their own daily slots (3 a day) and never compete with reels / long-form for a day
DEFAULT_STORY_POSTING_TIMES = ["08:00", "13:00", "20:00"]

# Business Suite reels are looked for on Instagram at most this often
BUSINESS_SUITE_SYNC_SEC = 10 * 60


class PostBusyError(Exception):
    """The post is being uploaded right now, so it can't be changed until that finishes."""


def _forget_staged(item: Dict[str, Any], platform: str):
    """Drops a platform's staged copy from a calendar post (the copy was deleted or replaced)."""
    for key in ("staged_platforms", "published_platforms"):
        if platform in (item.get(key) or []):
            item[key].remove(platform)
    (item.get("staged_for") or {}).pop(platform, None)
    if not item.get("staged_platforms"):
        item["staged"] = False
        item["pre_uploaded"] = False


class CalendarManager:
    def __init__(self, schedule_file: Path = SCHEDULE_FILE):
        self.schedule_file = schedule_file
        self.schedule_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_file()
        self._busy = set()               # posts being uploaded right now (staging, a due post or Post Now)
        self._youtube_paused_until = 0.0  # YouTube staging waits after a quota / upload-limit error
        self._business_suite_synced_at = 0.0

    def _patch_item(self, post_id: str, fn) -> Optional[Dict[str, Any]]:
        """Re-reads the schedule, changes that one post and saves, so edits made while an upload ran are kept."""
        items = self._load_all()
        for it in items:
            if it.get("id") == post_id:
                fn(it)
                self._save_all(items)
                return it
        return None

    def is_busy(self, post_id: str) -> bool:
        return post_id in self._busy

    def _ensure_not_busy(self, post_id: str):
        if post_id in self._busy:
            raise PostBusyError("This post is being uploaded right now. Try again in a few minutes.")

    @staticmethod
    def _pending_copies(item: Dict[str, Any], now: Optional[datetime.datetime] = None) -> List[str]:
        """Staged platforms whose copy is still waiting on the platform (its publish time hasn't passed)."""
        now = now or datetime.datetime.now()
        out = []
        for p in item.get("staged_platforms") or []:
            when = (item.get("staged_for") or {}).get(p) or item.get("scheduled_datetime_iso")
            try:
                if datetime.datetime.fromisoformat(when) > now:
                    out.append(p)
            except (TypeError, ValueError):
                continue
        return out

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

            item["platform_states"] = self._platform_states(item)
            item["video_changed_since_staged"] = self._video_changed_since_staged(item)

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

    def _platform_states(self, item: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
        """Per platform, for the calendar: "staged" (waiting on the platform, with live_at), "business_suite" (scheduled
        by hand: todo / scheduled / live / missing), or the last staging error. Platforms posted as usual are left out."""
        states: Dict[str, Dict[str, Any]] = {}
        pending = self._pending_copies(item)
        for p in item.get("staged_platforms") or []:
            states[p] = {"state": "staged" if p in pending else "live",
                         "live_at": (item.get("staged_for") or {}).get(p) or item.get("scheduled_datetime_iso")}
        for p, st in (item.get("stage") or {}).items():
            if p not in states and st.get("error"):
                states[p] = {"state": "stage_failed", "error": st.get("error"),
                             "gave_up": int(st.get("attempts") or 0) >= MAX_STAGE_ATTEMPTS}
        try:
            cfg = config_manager.get_project_social_config(item.get("project_path"))
            for p in business_suite_platforms(cfg, item.get("video_rel_path", ""), item.get("platforms") or []):
                manual = (item.get("manual") or {}).get(p) or {}
                states[p] = {"state": "business_suite", "step": manual.get("state") or "todo", "url": manual.get("url")}
        except Exception:
            pass
        return states

    @staticmethod
    def _video_changed_since_staged(item: Dict[str, Any]) -> bool:
        """True when the video file was re-rendered after it was uploaded to wait on a platform."""
        staged_mtime = item.get("staged_video_mtime")
        if not staged_mtime or not CalendarManager._pending_copies(item):
            return False
        try:
            return (Path(item.get("project_path", "")) / item.get("video_rel_path", "")).stat().st_mtime > float(staged_mtime) + 1
        except OSError:
            return False

    def get_post_by_id(self, post_id: str) -> Optional[Dict[str, Any]]:
        items = self._load_all()
        for it in items:
            if it.get("id") == post_id:
                return it
        return None

    @staticmethod
    def _post_kind(rel_path: Optional[str]) -> str:
        return "story" if is_story_path(rel_path) else ("reel" if is_reel(rel_path or "") else "other")

    def validate_slot(self, project_path: str, date_str: str, platforms: List[str], exclude_post_id: Optional[str] = None,
                      story: bool = False, time_str: Optional[str] = None, reel: bool = False) -> Dict[str, Any]:
        """Validates the 1 post per account/platform in a day rule for a project (long-form and other videos).
        Stories and reels are counted separately and post several times a day: a story only conflicts with another
        story, and a reel with another reel, at the same date and time."""
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
            kind = "story" if story else ("reel" if reel else "other")
            if self._post_kind(it.get("video_rel_path")) != kind:
                continue
            if kind != "other" and time_str and (it.get("scheduled_time") or "")[:5] != time_str[:5]:
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

    def story_posting_times(self, project_path: str) -> List[str]:
        cfg = config_manager.get_project_social_config(project_path)
        times = cfg.get("story_posting_times") or DEFAULT_STORY_POSTING_TIMES
        return sorted(t[:5] for t in times)

    def _story_preferred_time(self, project_path: str, video_rel_path: str, times: List[str]) -> Optional[str]:
        """A story's metadata.json may pin its daily slot ("post_time": "08:00")."""
        try:
            meta_p = (Path(project_path) / video_rel_path).parent / "metadata.json"
            pref = str(json.loads(meta_p.read_text(encoding="utf-8")).get("post_time") or "")[:5]
            return pref if pref in times else None
        except Exception:
            return None

    @staticmethod
    def _story_weekday(project_path: str, video_rel_path: str) -> Optional[int]:
        """A story's metadata.json "day" ("Tuesday" / "Tue") pins it to that weekday, next to the reels it follows."""
        try:
            meta_p = (Path(project_path) / video_rel_path).parent / "metadata.json"
            day = str(json.loads(meta_p.read_text(encoding="utf-8")).get("day") or "").strip().lower()[:3]
            return ["mon", "tue", "wed", "thu", "fri", "sat", "sun"].index(day) if day else None
        except Exception:
            return None

    def _find_story_slot(self, project_path: str, platforms: List[str], start_date_str: Optional[str],
                         video_rel_path: str) -> Dict[str, Any]:
        """Earliest free story slot: each day has one slot per story posting time (3 a day by default). A story whose
        metadata names its day only takes that weekday."""
        times = self.story_posting_times(project_path)
        preferred = self._story_preferred_time(project_path, video_rel_path, times)
        candidates = [preferred] if preferred else times
        weekday = self._story_weekday(project_path, video_rel_path)

        now = datetime.datetime.now()
        start_date = now.date()
        if start_date_str:
            try:
                start_date = datetime.date.fromisoformat(start_date_str)
            except Exception:
                pass

        for d in range(0, 365):
            cand_date = start_date + datetime.timedelta(days=d)
            if weekday is not None and cand_date.weekday() != weekday:
                continue
            cand_str = cand_date.strftime("%Y-%m-%d")
            for t in candidates:
                hour, minute = map(int, t.split(":"))
                if datetime.datetime(cand_date.year, cand_date.month, cand_date.day, hour, minute) <= now:
                    continue
                if self.validate_slot(project_path, cand_str, platforms, story=True, time_str=t)["valid"]:
                    return {"date": cand_str, "time": t, "datetime_iso": f"{cand_str}T{t}:00", "platforms": platforms}

        fallback_date = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        return {"date": fallback_date, "time": candidates[0], "datetime_iso": f"{fallback_date}T{candidates[0]}:00",
                "platforms": platforms}

    def _find_reel_slot(self, project_path: str, platforms: List[str], start_date_str: Optional[str],
                        video_rel_path: str) -> Dict[str, Any]:
        """A reel posts on its own weekday at the time for its place in the day (W06/reels/tue_2_x -> the next free
        Tuesday at the 2nd reel time); a reel only conflicts with another reel at the same date and time."""
        times = reel_posting_times(config_manager.get_project_social_config(project_path))
        weekday, post_time = reel_day_and_time((Path(project_path) / video_rel_path).parent, times)
        hour, minute = map(int, post_time.split(":"))

        now = datetime.datetime.now()
        start_date = now.date()
        if start_date_str:
            try:
                start_date = datetime.date.fromisoformat(start_date_str)
            except Exception:
                pass

        for d in range(0, 366):
            cand_date = start_date + datetime.timedelta(days=d)
            if weekday is not None and cand_date.weekday() != weekday:
                continue
            if datetime.datetime(cand_date.year, cand_date.month, cand_date.day, hour, minute) <= now:
                continue
            cand_str = cand_date.strftime("%Y-%m-%d")
            if self.validate_slot(project_path, cand_str, platforms, reel=True, time_str=post_time)["valid"]:
                return {"date": cand_str, "time": post_time, "datetime_iso": f"{cand_str}T{post_time}:00", "platforms": platforms}

        fallback_date = (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        return {"date": fallback_date, "time": post_time, "datetime_iso": f"{fallback_date}T{post_time}:00",
                "platforms": platforms}

    def find_next_available_slot(self, project_path: str, platforms: Optional[List[str]] = None, start_date_str: Optional[str] = None,
                                 video_rel_path: Optional[str] = None) -> Dict[str, Any]:
        """Finds the earliest available calendar day where none of the target platforms already have a post scheduled.
        Stories (a video under a stories/ folder) use their own daily story slots instead."""
        cfg = config_manager.get_project_social_config(project_path)
        default_time = cfg.get("default_posting_time", "18:00")

        target_platforms = platforms
        if not target_platforms:
            proj_plats = config_manager.get_project_platforms(project_path)
            target_platforms = [p for p in ["youtube", "facebook", "instagram", "tiktok", "x"] if proj_plats.get(p, False)]
            if not target_platforms:
                target_platforms = ["youtube"]

        if is_story_path(video_rel_path):
            return self._find_story_slot(project_path, target_platforms, start_date_str, video_rel_path)
        if video_rel_path and is_reel(video_rel_path):
            return self._find_reel_slot(project_path, target_platforms, start_date_str, video_rel_path)

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
            slot = self.find_next_available_slot(project_path, target_platforms, start_date_str=date_str,
                                                  video_rel_path=video_rel_path)
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
        for it in items:
            if it.get("status") == "scheduled" and it.get("video_rel_path", "").lower() == norm_vrel and self._pending_copies(it):
                waiting = ", ".join(p.capitalize() for p in self._pending_copies(it))
                raise ValueError(
                    f"This video is already uploaded and waiting on {waiting} for {it.get('scheduled_date')} "
                    f"{it.get('scheduled_time')}. Change that post's time on the calendar, or remove it first."
                )
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

        # Copies already uploaded and waiting on a platform keep their publish record (change_post moves or
        # replaces them); clearing it would make KCT Studio forget a video the platform still publishes
        waiting = set(self._pending_copies(target))

        def clear_posted_flags():
            for p in target_platforms:
                if p not in waiting:
                    asset_manager.set_social_posted(target["video_rel_path"], p, False)
            # A saved post starts its staging attempts afresh
            target["stage"] = {p: st for p, st in (target.get("stage") or {}).items() if p in waiting}

        target["scheduled_date"] = date_str
        target["scheduled_time"] = time_str
        target["scheduled_datetime_iso"] = f"{date_str}T{clean_time}"
        target["platforms"] = target_platforms

        if status:
            target["status"] = status
            if status == "posted":
                target["error"] = None
                target["posted_at"] = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                target["retry_count"] = 0
                target["next_retry_at"] = None
                asset_manager.update_social_posted_batch(target["video_rel_path"], target_platforms)
            elif status in ("scheduled", "retrying"):
                target["error"] = None
                target["posted_at"] = None
                target["dispatch_result"] = None
                target["retry_count"] = 0
                target["next_retry_at"] = None
                clear_posted_flags()
        elif target["status"] in ("failed", "posted", "retrying"):
            target["status"] = "scheduled"
            target["error"] = None
            target["posted_at"] = None
            target["dispatch_result"] = None
            target["retry_count"] = 0
            target["next_retry_at"] = None
            clear_posted_flags()
        elif target.get("status") == "scheduled":
            target["error"] = None
            target["posted_at"] = None
            target["dispatch_result"] = None
            target["retry_count"] = 0
            target["next_retry_at"] = None
            clear_posted_flags()

        self._save_all(items)
        return target

    async def change_post(self, post_id: str, date_str: str, time_str: str, platforms: Optional[List[str]] = None,
                          force: bool = False, status: Optional[str] = None) -> Dict[str, Any]:
        """
        Saves a post's new time / platforms / status (Save, drag-and-drop) and keeps copies that are already waiting on
        a platform in step: a YouTube copy moves to the new time, a Facebook copy (whose time the API can't change) is
        deleted and uploaded again for the new time, and an unticked platform's copy is deleted. Copies that are
        already live are never touched.
        Returns {"entry", "notes", "errors"}.
        """
        item = self.get_post_by_id(post_id)
        if not item:
            raise KeyError(f"Post with ID {post_id} not found.")
        self._ensure_not_busy(post_id)
        if not force and date_str < datetime.date.today().isoformat():
            raise ValueError(f"Cannot reschedule post to a past date ({date_str}). Please select today or a future date.")

        rel = item.get("video_rel_path", "")
        clean_time = time_str + ":00" if len(time_str) == 5 else time_str
        new_due_iso = f"{date_str}T{clean_time}"
        new_due = datetime.datetime.fromisoformat(new_due_iso)
        new_platforms = platforms if platforms is not None else (item.get("platforms") or [])
        now = datetime.datetime.now()
        notes: List[str] = []
        errors: List[str] = []
        moved: List[str] = []

        pending = [] if status == "posted" else self._pending_copies(item, now)
        if pending:
            self._busy.add(post_id)
            try:
                for p in pending:
                    name = p.capitalize()
                    if p not in new_platforms:
                        res = await asyncio.to_thread(cancel_copy, rel, p)
                        if res.get("success"):
                            self._patch_item(post_id, lambda it, p=p: _forget_staged(it, p))
                            notes.append(f"Deleted the {name} copy that was waiting to go live.")
                        else:
                            errors.append(f"{name}: couldn't delete the waiting copy ({res.get('error')}).")
                        continue
                    if (item.get("staged_for") or {}).get(p) == new_due_iso:
                        continue
                    if p == "youtube" and new_due <= now + datetime.timedelta(minutes=2):
                        res = await asyncio.to_thread(release_copy, rel, p)
                        if res.get("success"):
                            moved.append(p)
                            notes.append("The YouTube copy is public now.")
                        else:
                            errors.append(f"YouTube: couldn't publish the waiting copy ({res.get('error')}).")
                        continue
                    res = await asyncio.to_thread(move_copy, rel, p, new_due)
                    if res.get("success"):
                        moved.append(p)
                        notes.append(f"The {name} copy now goes live at {new_due.strftime('%a %d %b %H:%M')}.")
                    elif res.get("replace"):
                        res = await asyncio.to_thread(cancel_copy, rel, p)
                        if res.get("success"):
                            self._patch_item(post_id, lambda it, p=p: _forget_staged(it, p))
                            notes.append(f"The {name} copy was removed; it is uploaded again for the new time"
                                         " (or posted by this PC if the time is under 20 minutes away).")
                        else:
                            errors.append(f"{name}: couldn't replace the waiting copy ({res.get('error')}).")
                    else:
                        errors.append(f"{name}: couldn't move the waiting copy ({res.get('error')}).")
            finally:
                self._busy.discard(post_id)

        entry = self.update_post(post_id, date_str, time_str, platforms, force, status)
        if moved:
            entry = self._patch_item(post_id, lambda it: it.setdefault("staged_for", {}).update({p: new_due_iso for p in moved}))
        return {"entry": entry, "notes": notes, "errors": errors}

    async def pre_upload_post(self, post_id: str, platforms: Optional[List[str]] = None, social_dispatcher=None,
                              replace: bool = False, automatic: bool = False) -> Dict[str, Any]:
        """
        Uploads a scheduled post to YouTube / Facebook now, set to go live at its scheduled time: the platform holds
        it, so it goes out even if this PC is off. replace=True swaps copies that are already waiting (after a
        re-render or caption change). automatic=True is the week-ahead stager: failures back off and are retried, and
        after MAX_STAGE_ATTEMPTS the PC simply posts that platform at its time.
        """
        item = self.get_post_by_id(post_id)
        if not item:
            raise KeyError(f"Scheduled post with ID {post_id} not found.")
        self._ensure_not_busy(post_id)

        rel = item["video_rel_path"]
        raw_plats = platforms if platforms else item.get("platforms", ["youtube"])
        schedulable_platforms = native_platforms(rel, raw_plats)
        if not schedulable_platforms:
            raise ValueError(
                f"Selected platforms ({', '.join(raw_plats)}) can't hold a scheduled post. Only YouTube, and Facebook for "
                "long-form and reels, can; Instagram and Facebook Stories are scheduled in Business Suite or posted at their time."
            )
        due = due_datetime(item)
        if not due or due < datetime.datetime.now() + MIN_STAGE_LEAD:
            raise ValueError("This post is due in under 20 minutes, too soon to upload it ahead. Use Post Now, or move it later.")
        due_iso = due.strftime("%Y-%m-%dT%H:%M:%S")

        # Title
        passed_title = item.get("title")
        vid_stem_title = Path(rel).stem.replace("_", " ").title()
        if passed_title == vid_stem_title:
            passed_title = None

        replace_errors = []
        self._busy.add(post_id)
        try:
            if replace:
                for p in [p for p in self._pending_copies(item) if p in schedulable_platforms]:
                    res = await asyncio.to_thread(cancel_copy, rel, p)
                    if res.get("success"):
                        self._patch_item(post_id, lambda it, p=p: _forget_staged(it, p))
                    else:
                        replace_errors.append(f"{p}: couldn't remove the old copy ({res.get('error')})")
                        schedulable_platforms.remove(p)
            if not automatic:
                # A deliberate Stage / Re-stage starts the platform's attempts afresh
                self._patch_item(post_id, lambda it: [(it.get("stage") or {}).pop(p, None) for p in schedulable_platforms])
            if schedulable_platforms:
                res = await social_dispatcher.publish_video(
                    project_path_str=item["project_path"],
                    video_rel_path=rel,
                    platforms=schedulable_platforms,
                    custom_title=passed_title,
                    force_republish=False,
                    scheduled_datetime_iso=due_iso,
                    publish_mode="schedule"
                )
            else:
                res = {"success": False, "error": "; ".join(replace_errors), "platforms": {}}
        finally:
            self._busy.discard(post_id)

        dispatched = res.get("platforms") or {}
        # A Facebook upload that failed part-way is removed, so a retry can never leave two scheduled copies
        for plat, pinfo in dispatched.items():
            if plat == "facebook" and isinstance(pinfo, dict) and pinfo.get("status") == "failed" and pinfo.get("id"):
                await asyncio.to_thread(meta_uploader.delete_video, str(pinfo["id"]))

        try:
            video_mtime = (Path(item["project_path"]) / rel).stat().st_mtime
        except OSError:
            video_mtime = None
        now_ts = time.time()
        now_iso = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        dry_run = bool(res.get("dry_run"))

        def apply(it):
            it["last_attempt_at"] = now_iso
            it["dispatch_result"] = res
            staged = it.setdefault("staged_platforms", [])
            published = it.setdefault("published_platforms", [])
            staged_for = it.setdefault("staged_for", {})
            state = it.setdefault("stage", {})
            for plat in schedulable_platforms:
                pinfo = dispatched.get(plat) if isinstance(dispatched.get(plat), dict) else {}
                if pinfo.get("status") == "published" or pinfo.get("scheduled"):
                    if plat not in staged:
                        staged.append(plat)
                    if plat not in published:
                        published.append(plat)
                    if not pinfo.get("already_published"):
                        staged_for[plat] = due_iso
                    state.pop(plat, None)
                elif dry_run:
                    continue
                elif pinfo.get("status") == "skipped":
                    state[plat] = {"attempts": MAX_STAGE_ATTEMPTS, "error": pinfo.get("message") or "Skipped"}
                else:
                    err = pinfo.get("error") or res.get("error") or "Upload failed"
                    previous = state.get(plat) or {}
                    if plat == "youtube" and is_quota_error(err):
                        self._youtube_paused_until = now_ts + QUOTA_PAUSE_SEC
                        state[plat] = {**previous, "error": err, "retry_at": now_ts + QUOTA_PAUSE_SEC}
                    else:
                        attempts = int(previous.get("attempts") or 0) + 1
                        state[plat] = {"attempts": attempts, "error": err, "retry_at": now_ts + STAGE_RETRY_SEC * attempts}
            if staged:
                it["staged"] = True
                it["pre_uploaded"] = True
                it["pre_uploaded_at"] = now_iso
                if video_mtime:
                    it["staged_video_mtime"] = video_mtime
            newly = [p for p in schedulable_platforms if p in staged]
            if newly and not replace_errors:
                it["error"] = None
            elif not automatic:
                if dry_run:
                    it["error"] = "Dry run is on: nothing was uploaded. Turn off dry run, then stage again."
                else:
                    msgs = replace_errors + [f"{p}: {state[p].get('error')}" for p in schedulable_platforms if p in state]
                    it["error"] = "; ".join(msgs) or res.get("error") or res.get("message") or "Failed to stage video to cloud platforms"

        entry = self._patch_item(post_id, apply) or item
        success = all(p in (entry.get("staged_platforms") or []) for p in schedulable_platforms) and bool(schedulable_platforms)
        if not success and automatic:
            logging.warning(f"[Staging] {rel}: not every platform was staged ({entry.get('stage')})")
        return {"success": success, "entry": entry, "dispatch": res}

    async def stage_upcoming_posts(self, social_dispatcher, now: Optional[datetime.datetime] = None) -> List[str]:
        """
        Week-ahead staging (scheduler): uploads posts due within the project's stage_ahead_days to YouTube / Facebook
        with the platform's own schedule, earliest first and one at a time, so they go live even if this PC is off.
        Projects with dry run on or stage_ahead_days 0 are left alone. A platform that keeps failing is posted by the
        PC at its time, as before.
        """
        staged_ids: List[str] = []
        tried = set()
        while True:
            pick = self._next_to_stage(now or datetime.datetime.now(), tried)
            if not pick:
                break
            post_id, plats = pick
            tried.add(post_id)
            try:
                res = await self.pre_upload_post(post_id, plats, social_dispatcher, automatic=True)
                if res.get("success"):
                    staged_ids.append(post_id)
            except (KeyError, ValueError, PostBusyError) as e:
                logging.info(f"[Staging] Skipped {post_id}: {e}")
        return staged_ids

    def _next_to_stage(self, now: datetime.datetime, exclude) -> Optional[tuple]:
        """(post id, platforms) of the earliest post that should be uploaded ahead now, or None."""
        now_ts = time.time()
        best = None
        for it in self._load_all():
            pid = it.get("id")
            if it.get("status") != "scheduled" or pid in self._busy or pid in exclude:
                continue
            cfg = config_manager.get_project_social_config(it.get("project_path"))
            days = float(cfg.get("stage_ahead_days") or 0)
            if days <= 0 or cfg.get("dry_run", True):
                continue
            due = due_datetime(it)
            if not due or due < now + MIN_STAGE_LEAD or due > now + datetime.timedelta(days=days):
                continue
            plats = self._platforms_to_stage(it, cfg, now_ts)
            if plats and (best is None or due < best[0]):
                best = (due, pid, plats)
        return (best[1], best[2]) if best else None

    def _platforms_to_stage(self, item: Dict[str, Any], cfg: Dict[str, Any], now_ts: float) -> List[str]:
        rel = item.get("video_rel_path", "")
        wanted = [p for p in native_platforms(rel, item.get("platforms") or []) if (cfg.get(p) or {}).get("enabled", True)]
        done = set(item.get("staged_platforms") or []) | set(item.get("published_platforms") or [])
        try:
            pub = asset_manager.get_asset_record(rel).get("published") or {}
            done |= {p for p, e in pub.items() if isinstance(e, dict) and e.get("status") in ("published", "scheduled")}
        except Exception:
            pass
        state = item.get("stage") or {}
        out = []
        for p in wanted:
            st = state.get(p) or {}
            if p in done or int(st.get("attempts") or 0) >= MAX_STAGE_ATTEMPTS or float(st.get("retry_at") or 0) > now_ts:
                continue
            if p == "youtube" and self._youtube_paused_until > now_ts:
                continue
            out.append(p)
        return out

    async def release_staged(self, post_id: str, platforms: List[str]) -> Dict[str, List[str]]:
        """
        Post Now on a post whose copies are waiting on a platform: the YouTube copy is made public now, the Facebook
        copy is deleted so the caller uploads it as an immediate post. Never leaves a second copy.
        Returns {"released", "replaced", "errors"}.
        """
        item = self.get_post_by_id(post_id)
        out = {"released": [], "replaced": [], "errors": []}
        if not item:
            return out
        rel = item.get("video_rel_path", "")
        now_iso = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        for p in [p for p in self._pending_copies(item) if p in platforms]:
            if p == "youtube":
                res = await asyncio.to_thread(release_copy, rel, p)
                if res.get("success"):
                    out["released"].append(p)
                    self._patch_item(post_id, lambda it: it.setdefault("staged_for", {}).update({"youtube": now_iso}))
                else:
                    out["errors"].append(f"YouTube: {res.get('error')}")
            else:
                res = await asyncio.to_thread(cancel_copy, rel, p)
                if res.get("success"):
                    out["replaced"].append(p)
                    self._patch_item(post_id, lambda it, p=p: _forget_staged(it, p))
                else:
                    out["errors"].append(f"{p.capitalize()}: {res.get('error')}")
        return out

    async def remove_post(self, post_id: str) -> Dict[str, Any]:
        """
        Removes a post from the calendar. Copies already uploaded and still waiting on YouTube / Facebook are deleted
        first, so nothing goes live later; if one can't be deleted the post stays on the calendar and the error says
        which. Copies that are already live are never deleted.
        """
        item = self.get_post_by_id(post_id)
        if not item:
            raise KeyError(f"Post with ID {post_id} not found.")
        self._ensure_not_busy(post_id)
        rel = item.get("video_rel_path", "")
        deleted, errors = [], []
        self._busy.add(post_id)
        try:
            for p in self._pending_copies(item):
                res = await asyncio.to_thread(cancel_copy, rel, p)
                if res.get("success"):
                    deleted.append(p)
                    self._patch_item(post_id, lambda it, p=p: _forget_staged(it, p))
                else:
                    errors.append(f"{p.capitalize()}: {res.get('error')}")
        finally:
            self._busy.discard(post_id)
        if errors:
            return {"success": False, "deleted_copies": deleted, "errors": errors}
        self.delete_post(post_id)
        return {"success": True, "deleted_copies": deleted, "errors": []}

    def delete_post(self, post_id: str) -> bool:
        """Cancels/removes a scheduled post."""
        items = self._load_all()
        initial_len = len(items)
        items = [it for it in items if it.get("id") != post_id]
        if len(items) < initial_len:
            self._save_all(items)
            return True
        return False

    async def remove_schedule_for_video(self, project_path: str, video_rel_path: str) -> int:
        """Removes any pending (not yet posted) scheduled items for a video when unapproved. Copies already waiting on
        YouTube / Facebook are deleted too (remove_post), so an unapproved video never goes live."""
        items = self._load_all()
        norm_proj = ""
        try:
            norm_proj = str(Path(project_path).resolve()).lower()
        except Exception:
            norm_proj = str(project_path).lower()
        norm_rel = video_rel_path.replace("\\", "/").lower()

        kept = []
        removed_count = 0
        with_copies = []
        for it in items:
            it_proj = ""
            try:
                it_proj = str(Path(it.get("project_path", "")).resolve()).lower()
            except Exception:
                it_proj = str(it.get("project_path", "")).lower()
            it_rel = it.get("video_rel_path", "").replace("\\", "/").lower()
            if it_proj == norm_proj and it_rel == norm_rel and it.get("status") == "scheduled":
                if self._pending_copies(it):
                    with_copies.append(it.get("id"))
                    kept.append(it)
                    continue
                removed_count += 1
                continue
            kept.append(it)

        if removed_count > 0:
            self._save_all(kept)
        for post_id in with_copies:
            try:
                res = await self.remove_post(post_id)
                if res.get("success"):
                    removed_count += 1
                else:
                    logging.warning(f"[Calendar] Kept {post_id} on the calendar: {'; '.join(res.get('errors') or [])}")
            except (KeyError, PostBusyError) as e:
                logging.warning(f"[Calendar] Could not remove {post_id}: {e}")
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
            slot = self.find_next_available_slot(target_path, platforms, video_rel_path=rel)
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
        """
        Scans for scheduled posts that are due now and dispatches them. On failure, cleanly marks as failed for manual
        reposting. Copies already waiting on a platform are not uploaded again, platforms the project schedules in
        Business Suite are left to it, and a post that is uploading right now waits for the next pass.
        Each post is saved on its own after its upload, so changes made meanwhile are kept.
        """
        now_dt = datetime.datetime.now()
        now_iso = now_dt.strftime("%Y-%m-%dT%H:%M:%S")

        executed = []

        for snapshot in self._load_all():
            if snapshot.get("status") != "scheduled":
                continue
            post_id = snapshot.get("id")
            if post_id in self._busy:
                continue

            due_iso = snapshot.get("scheduled_datetime_iso") or f"{snapshot.get('scheduled_date', '')}T{snapshot.get('scheduled_time', '00:00')}:00"
            if not due_iso or due_iso > now_iso:
                continue

            # Post is due for publishing!
            proj_path = snapshot.get("project_path", "")
            video_rel = snapshot.get("video_rel_path", "")
            platforms = snapshot.get("platforms", [])
            manual = business_suite_platforms(config_manager.get_project_social_config(proj_path), video_rel, platforms)

            # Fetch publication records from asset_manager and schedule item
            rec = asset_manager.get_asset_record(video_rel)
            existing_published = rec.get("published", {})
            already_published = set(
                plat for plat, pinfo in existing_published.items()
                if isinstance(pinfo, dict) and pinfo.get("status") in ("published", "scheduled")
            )
            already_published.update(snapshot.get("published_platforms", []))
            already_published.update(snapshot.get("staged_platforms", []))

            # Filter out platforms that have already succeeded, been staged in the cloud, or are left to Business Suite
            target_platforms = [p for p in platforms if p not in already_published and p not in manual]

            # If all selected platforms are already published, mark posted immediately
            if not target_platforms:
                done = [p for p in platforms if p not in manual]

                def mark_done(it):
                    it["last_attempt_at"] = now_iso
                    it["status"] = "posted"
                    it["error"] = None
                    it["retry_count"] = 0
                    it["next_retry_at"] = None
                    it["posted_at"] = it.get("posted_at") or now_iso

                asset_manager.update_social_posted_batch(video_rel, done)
                item = self._patch_item(post_id, mark_done)
                if item:
                    executed.append(item)
                continue

            self._busy.add(post_id)
            try:
                res = await social_dispatcher.publish_video(
                    project_path_str=proj_path,
                    video_rel_path=video_rel,
                    platforms=target_platforms,
                    custom_title=snapshot.get("title"),
                    force_republish=False
                )
                error = None
            except Exception as e:
                res, error = None, str(e)
            finally:
                self._busy.discard(post_id)

            if error is not None:
                def mark_error(it, error=error):
                    it["last_attempt_at"] = now_iso
                    it["status"] = "failed"
                    it["retry_count"] = 0
                    it["next_retry_at"] = None
                    it["error"] = f"Dispatch error: {error}"

                item = self._patch_item(post_id, mark_error)
                if item:
                    executed.append(item)
                continue

            dispatched_plats = res.get("platforms", {})
            for plat, pinfo in dispatched_plats.items():
                if isinstance(pinfo, dict) and pinfo.get("status") == "published" and not pinfo.get("already_published"):
                    asset_manager.mark_published(video_rel, plat, pinfo)

            def apply(it, res=res, already_published=already_published, platforms=platforms, manual=manual):
                it["last_attempt_at"] = now_iso
                it["posted_at"] = now_iso
                it["dispatch_result"] = res

                # Track any platforms that succeeded in this dispatch
                if "published_platforms" not in it:
                    it["published_platforms"] = list(already_published)
                for plat, pinfo in dispatched_plats.items():
                    if isinstance(pinfo, dict) and pinfo.get("status") == "published":
                        if plat not in it["published_platforms"]:
                            it["published_platforms"].append(plat)

                # Platforms the dispatcher skipped on purpose (format limits, disabled in settings, unsupported)
                skipped = {
                    plat: pinfo.get("message", "Skipped")
                    for plat, pinfo in dispatched_plats.items()
                    if isinstance(pinfo, dict) and pinfo.get("status") == "skipped"
                }
                it["skipped_platforms"] = skipped

                # Verify whether all non-skipped platforms are now published (Business Suite ones are done by hand)
                current_pub = set(it.get("published_platforms", []))
                posted_now = [p for p in platforms if p in current_pub]
                unposted = [p for p in platforms if p not in current_pub and p not in skipped and p not in manual]

                it["retry_count"] = 0
                it["next_retry_at"] = None
                if res.get("dry_run"):
                    # Nothing is uploaded in dry-run mode; leave publish history untouched
                    it["status"] = "failed"
                    it["error"] = "Dry run is on: nothing was published. Turn off dry run, then repost."
                elif not unposted and posted_now:
                    it["status"] = "posted"
                    it["error"] = None
                    asset_manager.update_social_posted_batch(video_rel, posted_now)
                elif not unposted:
                    it["status"] = "failed"
                    it["error"] = "Nothing was published: " + "; ".join(f"{p}: {m}" for p, m in skipped.items())
                else:
                    # Cleanly mark failed for manual user reposting (no background auto-retry loop)
                    err_msg = res.get("error") or "; ".join(
                        f"{p}: {(dispatched_plats.get(p) or {}).get('error') or 'not published'}" for p in unposted
                    )
                    it["status"] = "failed"
                    it["error"] = f"Failed to publish to [{', '.join(unposted)}]: {err_msg}"

            item = self._patch_item(post_id, apply)
            if item:
                executed.append(item)

        return executed

    # ------------------------------------------------------------------------------------------------------------
    # Meta Business Suite: Instagram (reels, stories) and Facebook Stories that the project schedules by hand.
    # ------------------------------------------------------------------------------------------------------------
    def business_suite_tasks(self, project_path: Optional[str] = None, days: int = 7) -> List[Dict[str, Any]]:
        """Posts from yesterday to `days` ahead that have a platform scheduled by hand in Business Suite, one entry
        per platform, earliest first."""
        now = datetime.datetime.now()
        start, end = now - datetime.timedelta(days=1), now + datetime.timedelta(days=days)
        norm_project = None
        if project_path and project_path != "all":
            norm_project = str(Path(project_path).resolve()).lower()
        tasks = []
        for it in self._load_all():
            if it.get("status") not in ("scheduled", "posted", "failed"):
                continue
            if norm_project and str(Path(it.get("project_path", "")).resolve()).lower() != norm_project:
                continue
            due = due_datetime(it)
            if not due or not (start <= due <= end):
                continue
            rel = it.get("video_rel_path", "")
            cfg = config_manager.get_project_social_config(it.get("project_path"))
            for p in business_suite_platforms(cfg, rel, it.get("platforms") or []):
                state = (it.get("manual") or {}).get(p) or {}
                story = is_story_path(rel)
                tasks.append({
                    "post_id": it.get("id"),
                    "platform": p,
                    "label": f"{'Instagram' if p == 'instagram' else 'Facebook'} {'Story' if story else 'Reel'}",
                    "is_story": story,
                    "due": due.strftime("%Y-%m-%dT%H:%M:%S"),
                    "title": it.get("title"),
                    "project_path": it.get("project_path"),
                    "video_rel_path": rel,
                    "thumbnail_url": it.get("thumbnail_url"),
                    "step": state.get("state") or "todo",
                    "url": state.get("url"),
                })
        tasks.sort(key=lambda t: (t["due"], t["platform"]))
        return tasks

    def set_manual_state(self, post_id: str, platform: str, done: bool) -> Dict[str, Any]:
        """Ticks (or unticks) a Business Suite platform as scheduled there. A post already found live stays live."""
        now_iso = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        def apply(it):
            manual = it.setdefault("manual", {})
            current = manual.get(platform) or {}
            if current.get("state") == "live":
                return
            manual[platform] = {**current, "state": "scheduled" if done else "todo", "at": now_iso}

        item = self._patch_item(post_id, apply)
        if not item:
            raise KeyError(f"Post with ID {post_id} not found.")
        return item

    async def sync_business_suite_posts(self, social_dispatcher, now: Optional[datetime.datetime] = None) -> int:
        """
        Finds Instagram reels that were scheduled in Business Suite once they are live: records the link (so week links
        and reel comments know it) and queues the usual links comment under it (posted by post_due_comments). Looks at
        most every 10 minutes and only while a reel is waiting to be found; after 3 days it is reported missing.
        """
        now_dt = now or datetime.datetime.now()
        if now is None and time.time() - self._business_suite_synced_at < BUSINESS_SUITE_SYNC_SEC:
            return 0
        waiting = []
        for it in self._load_all():
            rel = it.get("video_rel_path", "")
            if not is_reel(rel) or it.get("status") not in ("scheduled", "posted", "failed"):
                continue
            cfg = config_manager.get_project_social_config(it.get("project_path"))
            if "instagram" not in business_suite_platforms(cfg, rel, it.get("platforms") or []):
                continue
            if ((it.get("manual") or {}).get("instagram") or {}).get("state") in ("live", "missing"):
                continue
            due = due_datetime(it)
            if not due or due > now_dt:
                continue
            posted = ((asset_manager.get_asset_record(rel).get("published") or {}).get("instagram") or {})
            if posted.get("status") == "published":
                # Already on Instagram (e.g. Post Now): nothing to look for
                url = (posted.get("details") or {}).get("url")
                self._patch_item(it["id"], lambda x, url=url: x.setdefault("manual", {}).update(
                    {"instagram": {"state": "live", "url": url}}))
                continue
            waiting.append((it, due))
        if not waiting:
            return 0
        self._business_suite_synced_at = time.time()

        media = await asyncio.to_thread(meta_uploader.recent_instagram_media)
        used = {str(d.get("id")) for r, p, d in asset_manager.iter_published() if p == "instagram" and d.get("id")}
        found = 0
        for it, due in waiting:
            rel = it["video_rel_path"]
            project = Path(it.get("project_path", ""))
            now_iso = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
            texts = await asyncio.to_thread(social_dispatcher.compose_post_texts, project, rel)
            match = match_instagram_post(texts["captions"]["instagram"], due, media, used)
            if match:
                used.add(str(match["id"]))
                details = {
                    "id": match["id"],
                    "url": match.get("permalink"),
                    "via": "business_suite",
                    "pending_comment": texts["pinned_comment"],
                    "comment_due_at": int(time.time()),
                }
                asset_manager.mark_published(rel, "instagram", details)
                export_week_links(project, week_of(rel))
                self._patch_item(it["id"], lambda x, m=match: x.setdefault("manual", {}).update(
                    {"instagram": {"state": "live", "url": m.get("permalink"), "at": now_iso}}))
                logging.info(f"[BusinessSuite] Found the Instagram reel for {rel}: {match.get('permalink')}")
                found += 1
            elif now_dt - due > BUSINESS_SUITE_LOOKUP:
                self._patch_item(it["id"], lambda x: x.setdefault("manual", {}).update(
                    {"instagram": {**((x.get("manual") or {}).get("instagram") or {}), "state": "missing", "at": now_iso}}))
        return found

calendar_manager = CalendarManager()
