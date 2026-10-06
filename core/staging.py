"""
Week-ahead scheduling: which platforms can hold a scheduled post, and the calls that move, release or cancel a copy
that is already uploaded and waiting on a platform.

YouTube holds a scheduled video of any format (stories go up as Shorts). Facebook holds scheduled long-form videos and
Reels, but not Stories. Instagram can't hold a scheduled post at all (its API has no scheduling and prepared uploads
expire after 24 hours), so a project can hand Instagram, and Facebook Stories, to Meta Business Suite
(social.business_suite): KCT Studio then never posts those from the calendar and lists them in the Business Suite
checklist instead.

The copy functions make blocking API calls; callers run them in a worker thread.
"""

import datetime
import logging
import re
import time
from typing import Any, Dict, Iterable, List, Optional

from core.asset_manager import asset_manager
from core.meta_uploader import meta_uploader
from core.week_links import is_reel
from core.youtube_uploader import youtube_uploader

# Facebook needs a scheduled time at least 10 minutes ahead; the extra room covers the upload itself
MIN_STAGE_LEAD = datetime.timedelta(minutes=20)
MAX_STAGE_ATTEMPTS = 3
STAGE_RETRY_SEC = 30 * 60
# A YouTube quota or channel upload-limit error pauses YouTube staging this long (without using up an attempt)
QUOTA_PAUSE_SEC = 6 * 3600
QUOTA_MARKERS = ("quotaexceeded", "uploadlimitexceeded", "exceeded the number of videos", "exceeded your quota")
# Business Suite reels are looked for this long after their time before being reported missing
BUSINESS_SUITE_LOOKUP = datetime.timedelta(days=3)


def is_story_path(rel_path: Optional[str]) -> bool:
    return "/stories/" in "/" + (rel_path or "").replace("\\", "/").lower()


def native_platforms(rel_path: str, platforms: Iterable[str]) -> List[str]:
    """The selected platforms that can hold this post as a scheduled upload."""
    out = []
    for p in platforms or []:
        if p == "youtube" or (p == "facebook" and not is_story_path(rel_path)):
            out.append(p)
    return out


def business_suite_platforms(cfg: Dict[str, Any], rel_path: str, platforms: Iterable[str]) -> List[str]:
    """The selected platforms this project schedules by hand in Meta Business Suite for this post."""
    bs = cfg.get("business_suite") or {}
    platforms = list(platforms or [])
    out = []
    if bs.get("instagram") and "instagram" in platforms and (is_reel(rel_path) or is_story_path(rel_path)):
        out.append("instagram")
    if bs.get("facebook_stories") and "facebook" in platforms and is_story_path(rel_path):
        out.append("facebook")
    return out


def due_datetime(item: Dict[str, Any]) -> Optional[datetime.datetime]:
    """A calendar post's time (local, naive) or None."""
    due_iso = item.get("scheduled_datetime_iso") or f"{item.get('scheduled_date', '')}T{item.get('scheduled_time', '00:00')}:00"
    try:
        return datetime.datetime.fromisoformat(due_iso)
    except (TypeError, ValueError):
        return None


def to_utc_iso(local_dt: datetime.datetime) -> str:
    """Local naive time -> the UTC form YouTube's publishAt takes (same format publish_video uses)."""
    return local_dt.astimezone().astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def is_quota_error(text: Optional[str]) -> bool:
    low = (text or "").lower()
    return any(m in low for m in QUOTA_MARKERS)


def _details(rel_path: str, platform: str) -> Dict[str, Any]:
    entry = (asset_manager.get_asset_record(rel_path).get("published") or {}).get(platform) or {}
    return entry.get("details") if isinstance(entry.get("details"), dict) else {}


def move_copy(rel_path: str, platform: str, new_due: datetime.datetime) -> Dict[str, Any]:
    """Moves a waiting YouTube copy to a new time. Facebook can't change a scheduled time through the API, so it
    answers {"replace": True}: the caller deletes that copy and it is uploaded again for the new time."""
    if platform != "youtube":
        return {"success": False, "replace": True}
    details = _details(rel_path, platform)
    if not details.get("id"):
        return {"success": False, "error": "No uploaded YouTube video is recorded for this post."}
    publish_at = to_utc_iso(new_due)
    res = youtube_uploader.set_publish_time(str(details["id"]), publish_at)
    if res.get("success"):
        details["scheduled"] = True
        details["scheduled_for"] = publish_at
        if details.get("pending_comment"):
            details["comment_due_at"] = int(new_due.timestamp()) + 60
        asset_manager.save()
    return res


def release_copy(rel_path: str, platform: str) -> Dict[str, Any]:
    """Makes a waiting YouTube copy public now; its links comment follows within a minute."""
    details = _details(rel_path, platform)
    if platform != "youtube" or not details.get("id"):
        return {"success": False, "error": f"Can't publish the {platform} copy early."}
    res = youtube_uploader.set_publish_time(str(details["id"]), None)
    if res.get("success"):
        details["scheduled"] = False
        details["scheduled_for"] = None
        if details.get("pending_comment"):
            details["comment_due_at"] = int(time.time()) + 60
        asset_manager.save()
    return res


def cancel_copy(rel_path: str, platform: str) -> Dict[str, Any]:
    """Deletes a copy that hasn't gone live yet and clears its publish record."""
    details = _details(rel_path, platform)
    video_id = details.get("id")
    if video_id:
        if platform == "youtube":
            res = youtube_uploader.delete_video(str(video_id))
        elif platform == "facebook":
            res = meta_uploader.delete_video(str(video_id))
        else:
            res = {"success": False, "error": f"Can't delete a {platform} post from KCT Studio."}
        if not res.get("success"):
            return res
    asset_manager.set_social_posted(rel_path, platform, False)
    logging.info(f"[Staging] Cancelled the {platform} copy of {rel_path}")
    return {"success": True}


def caption_key(text: Optional[str]) -> str:
    """A caption's opening words, lower-case letters and digits only (spacing and emoji differences don't matter)."""
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()[:60]


def match_instagram_post(caption: str, due: datetime.datetime, media: List[Dict[str, Any]],
                         used_ids: Iterable[str] = ()) -> Optional[Dict[str, Any]]:
    """The Instagram reel that is this post: same caption opening, posted from a day before to 3 days after its time,
    closest to it. Posts already matched to another video are skipped."""
    want = caption_key(caption)
    if len(want) < 12:
        return None
    used = set(used_ids)
    best = None
    for m in media or []:
        if m.get("id") in used or m.get("media_product_type") not in (None, "REELS"):
            continue
        have = caption_key(m.get("caption"))
        n = min(len(want), len(have))
        if n < 12 or want[:n] != have[:n]:
            continue
        try:
            posted = datetime.datetime.strptime(m.get("timestamp", ""), "%Y-%m-%dT%H:%M:%S%z").astimezone().replace(tzinfo=None)
        except ValueError:
            continue
        if not (due - datetime.timedelta(days=1) <= posted <= due + BUSINESS_SUITE_LOOKUP):
            continue
        gap = abs((posted - due).total_seconds())
        if best is None or gap < best[0]:
            best = (gap, m)
    return best[1] if best else None
