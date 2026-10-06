"""
Reel folders and their posting order.

A week's reels live in W06/reels/<day>_<n>_<name>/ : day is mon..sun, n is the reel's place in that day (1, 2, 3...).
Posting order is day, then n. Slot n posts at the project's reel_posting_times[n-1] unless the reel's metadata.json
sets "post_time". Older weeks named by number (01_<name>.. or 146_<name>..) read by rank: the 1st is Monday's, the
2nd Tuesday's, and so on, one reel a day.

The standalone generators (generate_reel.py, generate_story.py) keep identical copies of reel_slots, ordered_reels and
find_reel, because they run from the project's own Python and can't import core.
"""

import json
import re
from pathlib import Path
from typing import List, Optional, Tuple

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DEFAULT_REEL_POSTING_TIMES = ["07:30", "17:30", "20:30"]

_DAY_RE = re.compile(r"^(mon|tue|wed|thu|fri|sat|sun)_(\d+)_(.+)$", re.IGNORECASE)
_NUMBERED_RE = re.compile(r"^(\d+)[_-](.+)$")


def reel_slots(reels_dir: Path) -> List[Tuple[Path, int, int]]:
    """(folder, day index 0=Mon, place in the day) for a week's reels, in posting order. Day-named folders
    (mon_2_name) say it themselves; numbered folders (03_name, 146_name) take the days in number order, one a day.
    Folders that fit neither come last."""
    if not reels_dir or not reels_dir.is_dir():
        return []
    named, numbered, other = [], [], []
    for d in reels_dir.iterdir():
        if not d.is_dir() or d.name.lower() in ("temp", "temp_slides") or d.name.startswith((".", "__")):
            continue
        m = _DAY_RE.match(d.name)
        n = _NUMBERED_RE.match(d.name)
        if m:
            named.append((d, DAYS.index(m.group(1).lower()), int(m.group(2))))
        elif n:
            numbered.append((int(n.group(1)), d))
        else:
            other.append(d)
    for rank, (_, d) in enumerate(sorted(numbered, key=lambda x: (x[0], x[1].name))):
        named.append((d, rank % 7, rank // 7 + 1))
    named.sort(key=lambda x: (x[1], x[2], x[0].name))
    last = (named[-1][1], named[-1][2]) if named else (0, 0)
    return named + [(d, last[0], last[1] + i + 1) for i, d in enumerate(sorted(other, key=lambda d: d.name))]


def ordered_reels(reels_dir: Path) -> List[Path]:
    """A week's reel folders in posting order."""
    return [d for d, _, _ in reel_slots(reels_dir)]


def reel_key(folder: Path) -> Optional[str]:
    """"mon_2" for W06/reels/mon_2_name (an older numbered folder gets the key of its day, e.g. "wed_1")."""
    for d, day, n in reel_slots(folder.parent):
        if d.name == folder.name:
            return f"{DAYS[day]}_{n}"
    return None


def find_reel(reels_dir: Path, which) -> Optional[Path]:
    """A reel by its key ("tue_2"), folder name, or position in posting order (1 = first)."""
    slots = reel_slots(reels_dir)
    text = str(which).strip().lower()
    for d, day, n in slots:
        if text in (d.name.lower(), f"{DAYS[day]}_{n}"):
            return d
    if text.isdigit() and 1 <= int(text) <= len(slots):
        return slots[int(text) - 1][0]
    return None


def recorded_reel_number(folder: Path) -> Optional[int]:
    """A reel's "Bible Secrets #NNN" number: metadata.json global_episode, or an older metadata.txt's EPISODE line."""
    try:
        num = json.loads((folder / "metadata.json").read_text(encoding="utf-8")).get("global_episode")
        if num is not None:
            return int(num)
    except (OSError, ValueError, TypeError):
        pass
    try:
        m = re.search(r"^EPISODE\s+(\d+)", (folder / "metadata.txt").read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
        if m:
            return int(m.group(1))
    except OSError:
        pass
    return None


def reel_posting_times(cfg: dict) -> List[str]:
    times = [str(t).strip()[:5] for t in (cfg.get("reel_posting_times") or []) if str(t).strip()]
    return times or list(DEFAULT_REEL_POSTING_TIMES)


def reel_day_and_time(folder: Path, times: List[str]) -> Tuple[Optional[int], str]:
    """(weekday 0=Mon, "HH:MM") the reel posts at: its metadata.json "post_time" wins over the time for its place
    in the day."""
    day, slot = None, 1
    for d, dd, n in reel_slots(folder.parent):
        if d.name == folder.name:
            day, slot = dd, n
            break
    try:
        pinned = str(json.loads((folder / "metadata.json").read_text(encoding="utf-8")).get("post_time") or "")[:5]
        if re.match(r"^\d{2}:\d{2}$", pinned):
            return day, pinned
    except (OSError, ValueError):
        pass
    return day, times[min(slot, len(times)) - 1]
