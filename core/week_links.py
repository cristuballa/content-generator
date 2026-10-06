"""
Links between a week's posts: reels point to the week's full documentary.

Published links already live in the media catalog (asset_manager: published[platform].details.url). This module
answers "which documentary does this reel support, and is it live on YouTube yet?", composes the reel's links comment
with that link, and writes a readable <week>/published_links.json for people (and other agents) to look at.
"""

import datetime
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from core.asset_manager import asset_manager

DOC_LINE = "🎬 Watch the full documentary: {url}"
WEEK_RE = re.compile(r"^(W\d+)$", re.IGNORECASE)


def week_of(rel_path: str) -> Optional[str]:
    first = rel_path.replace("\\", "/").split("/", 1)[0]
    return first.upper() if WEEK_RE.match(first) else None


def is_reel(rel_path: str) -> bool:
    return "/reels/" in "/" + rel_path.replace("\\", "/").lower()


def _is_live(details: Dict[str, Any]) -> bool:
    """A scheduled upload only counts once its publish time has passed (before that the link shows 'unavailable')."""
    when = details.get("scheduled_for")
    if not details.get("scheduled") or not when:
        return True
    try:
        dt = datetime.datetime.fromisoformat(str(when).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.astimezone()
        return dt <= datetime.datetime.now(datetime.timezone.utc)
    except ValueError:
        return True


def _published(rel_path_prefix: str):
    """(rel_path, platform, details, time) for every published entry under a path prefix."""
    asset_manager.reload_if_needed()
    prefix = rel_path_prefix.replace("\\", "/").lower()
    for rel, rec in (asset_manager._data.get("assets") or {}).items():
        if not rel.replace("\\", "/").lower().startswith(prefix):
            continue
        for platform, entry in (rec.get("published") or {}).items():
            if isinstance(entry, dict) and isinstance(entry.get("details"), dict):
                yield rel.replace("\\", "/"), platform, entry["details"], float(entry.get("time") or 0)


def episode_youtube_links(week: str) -> Dict[str, str]:
    """{episode folder: newest live YouTube URL} for the week's long-form videos."""
    best: Dict[str, tuple] = {}
    for rel, platform, details, when in _published(f"{week}/long_form/"):
        # "superseded": an upload replaced by a newer cut (set on its catalog record) is never linked
        if platform != "youtube" or not details.get("url") or not _is_live(details) or details.get("superseded"):
            continue
        parts = rel.split("/")
        episode = parts[2] if len(parts) > 3 else "long_form"
        if episode not in best or when > best[episode][0]:
            best[episode] = (when, details["url"])
    return {ep: url for ep, (_, url) in best.items()}


def live_documentary_url(project_path: Path, reel_rel_path: str) -> Optional[str]:
    """YouTube URL of the documentary this reel supports, once it is live (None until then)."""
    week = week_of(reel_rel_path)
    if not week:
        return None
    links = episode_youtube_links(week)
    if not links:
        return None
    meta_p = (Path(project_path) / reel_rel_path).parent / "metadata.json"
    try:
        target = json.loads(meta_p.read_text(encoding="utf-8")).get("supports_long_form")
    except Exception:
        target = None
    if target:
        target = Path(str(target).replace("\\", "/")).name  # "long_form/02_x" or "02_x"
        if target in links:
            return links[target]
    return links[sorted(links)[0]]


def with_documentary_link(comment: str, url: Optional[str]) -> str:
    """Puts the documentary line first; unchanged when there is no link or it is already there."""
    comment = (comment or "").strip()
    if not url or url in comment:
        return comment
    line = DOC_LINE.format(url=url)
    return f"{line}\n\n{comment}" if comment else line


def comment_id_of(details: Dict[str, Any]) -> Optional[str]:
    first = details.get("first_comment") if isinstance(details.get("first_comment"), dict) else {}
    return details.get("comment_id") or first.get("comment_id")


def export_week_links(project_path: Path, week: Optional[str]) -> Optional[Path]:
    """Writes <project>/<week>/published_links.json: every published post of the week with its platform links."""
    if not week:
        return None
    week_dir = Path(project_path) / week
    if not week_dir.exists():
        return None
    out: Dict[str, Dict[str, Dict[str, str]]] = {"long_form": {}, "reels": {}, "stories": {}}
    for rel, platform, details, _ in _published(f"{week}/"):
        parts = rel.split("/")
        kind = parts[1] if len(parts) > 2 else ""
        if kind not in out or not details.get("url"):
            continue
        item = parts[2] if len(parts) > 3 else parts[-1]
        entry = out[kind].setdefault(item, {})
        entry[platform] = details["url"]
        if details.get("documentary_link"):
            entry["documentary_link_in_comment"] = details["documentary_link"]
    target = week_dir / "published_links.json"
    try:
        target.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        return target
    except OSError:
        return None
