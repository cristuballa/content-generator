"""
Renames every week's numbered reel folders to the day naming used for several reels a day:

    W06/reels/01_why_god_rejected_cains_fruit  ->  W06/reels/mon_1_why_god_rejected_cains_fruit
    W30/reels/146_at_jesuss_baptism...          ->  W30/reels/mon_1_at_jesuss_baptism...

The day comes from the week's metadata.json ("reels": [{"num": 1, "day": "Mon"}, ...]), else the folder's rank (1st =
Monday). Files and folders inside a reel that start with its old name are renamed too (videos, the narration cache in
temp/), so nothing is re-recorded. KCT Studio's records follow the new paths: the media catalog (approvals, published
links), the posting schedule and the story map. Each reel's metadata.json keeps its global number (global_episode),
and each story that names a reel by number (reel_num) also gets the reel's key ("reel": "tue_1"), so adding a second
reel to a day can never move a story onto another reel.

Stop KCT Studio (tray: Stop Server) first, so nothing running writes the old paths back.

    python scripts/rename_reels_by_day.py --project C:\\Projects\\BHSR            # dry run: prints the plan
    python scripts/rename_reels_by_day.py --project C:\\Projects\\BHSR --apply
    python scripts/rename_reels_by_day.py --undo data/backups/reel_rename_<time>/rename_log.json
"""

import argparse
import datetime
import json
import os
import re
import shutil
import socket
import sys
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_ROOT))
from core.reels import DAYS, recorded_reel_number  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA_DIR = PIPELINE_ROOT / "data"
DATA_FILES = ("media_catalog.json", "posting_schedule.json", "story_map_data.json")
NUMBERED = re.compile(r"^(\d+)[_-](.+)$")
WEEK = re.compile(r"^W\d+$", re.IGNORECASE)
DAY_ALIASES = {d: d for d in DAYS} | {name.lower(): d for name, d in zip(
    ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"), DAYS)}


def week_reel_days(week_dir: Path) -> dict:
    """{reel number in the week: day key} from the week's metadata.json."""
    try:
        reels = json.loads((week_dir / "metadata.json").read_text(encoding="utf-8")).get("reels") or []
        return {int(r["num"]): DAY_ALIASES[str(r["day"]).strip().lower()] for r in reels
                if isinstance(r, dict) and r.get("num") is not None and str(r.get("day", "")).strip().lower() in DAY_ALIASES}
    except (OSError, ValueError, KeyError, TypeError):
        return {}


def plan_week(week_dir: Path) -> list:
    """[{week, rank, old, new, key, number}] for the week's numbered reel folders (day-named ones are left alone)."""
    reels_dir = week_dir / "reels"
    if not reels_dir.is_dir():
        return []
    numbered = sorted(((int(m.group(1)), d, m.group(2)) for d in reels_dir.iterdir()
                       if d.is_dir() and (m := NUMBERED.match(d.name))), key=lambda x: (x[0], x[1].name))
    if not numbered:
        return []
    days_by_num = week_reel_days(week_dir)
    taken = {}
    for d in reels_dir.iterdir():  # day-named reels already there keep their places
        m = re.match(r"^(mon|tue|wed|thu|fri|sat|sun)_(\d+)_", d.name, re.IGNORECASE)
        if d.is_dir() and m:
            taken.setdefault(m.group(1).lower(), set()).add(int(m.group(2)))
    week_num = int(week_dir.name[1:])
    plan = []
    for rank, (_, folder, slug) in enumerate(numbered, 1):
        day = days_by_num.get(rank) or DAYS[(rank - 1) % 7]
        n = 1
        while n in taken.setdefault(day, set()):
            n += 1
        taken[day].add(n)
        new = f"{day}_{n}_{slug}"
        plan.append({
            "week": week_dir.name, "rank": rank, "old": folder.name, "new": new, "key": f"{day}_{n}",
            "number": recorded_reel_number(folder) or (week_num - 1) * 5 + rank,
        })
    return plan


def rewrite_path(text: str, week: str, old: str, new: str) -> str:
    """Rewrites <week>/reels/<old>/... in a path or URL (either slash), including files under it named after the
    old folder (<old>_final_reel.mp4, temp/<old>_raw_voice.wav)."""
    folder = re.compile(rf"(?<![\w]){re.escape(week)}(?P<sep>[\\/]+)reels(?P=sep){re.escape(old)}(?=[\\/?#\s\"]|$)")
    out, pos = [], 0
    for m in folder.finditer(text):
        sep = m.group("sep")
        out.append(text[pos:m.start()])
        out.append(f"{week}{sep}reels{sep}{new}")
        tail = re.match(r"[^?#\s\"]*", text[m.end():]).group(0)
        parts = re.split(r"([\\/]+)", tail)
        out.append("".join(new + p[len(old):] if (p == old or p.startswith((old + "_", old + "."))) else p for p in parts))
        pos = m.end() + len(tail)
    out.append(text[pos:])
    return "".join(out)


def rewrite_json(value, renames):
    """Every string and dict key in a JSON value, with each (week, old, new) folder rename applied."""
    if isinstance(value, str):
        for week, old, new in renames:
            if old in value:
                value = rewrite_path(value, week, old, new)
        return value
    if isinstance(value, list):
        return [rewrite_json(v, renames) for v in value]
    if isinstance(value, dict):
        return {rewrite_json(k, renames): rewrite_json(v, renames) for k, v in value.items()}
    return value


def server_running(port: int = 7860) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def apply(project: Path, plan: list, backup_dir: Path, data_dir: Path = DATA_DIR) -> dict:
    backup_dir.mkdir(parents=True, exist_ok=True)
    log = {"created": datetime.datetime.now().isoformat(timespec="seconds"), "project": str(project),
           "backup_dir": str(backup_dir), "data_dir": str(data_dir), "renames": [], "edited_files": []}
    log_path = backup_dir / "rename_log.json"

    def save_log():
        write_json(log_path, log)

    def backup(path: Path):
        """Keeps the original of a file this run edits (once), for --undo."""
        if not path.exists() or str(path) in log["edited_files"]:
            return
        dest = backup_dir / "files" / f"{len(log['edited_files']):05d}_{path.name}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
        log["edited_files"].append(str(path))
        log.setdefault("file_backups", {})[str(path)] = str(dest)

    for name in DATA_FILES:
        backup(data_dir / name)
    save_log()

    # 1. Folders, then everything inside them named after the old folder (deepest first)
    for item in plan:
        old_dir = project / item["week"] / "reels" / item["old"]
        new_dir = project / item["week"] / "reels" / item["new"]
        os.rename(old_dir, new_dir)
        log["renames"].append([str(old_dir), str(new_dir)])
        inner = sorted((p for p in new_dir.rglob("*") if p.name == item["old"] or p.name.startswith((item["old"] + "_", item["old"] + "."))),
                       key=lambda p: len(p.parts), reverse=True)
        for p in inner:
            target = p.with_name(item["new"] + p.name[len(item["old"]):])
            os.rename(p, target)
            log["renames"].append([str(p), str(target)])
        save_log()

    # 2. Reel metadata keeps its global number; week metadata names each reel's folder
    by_week = {}
    for item in plan:
        by_week.setdefault(item["week"], []).append(item)
        meta_p = project / item["week"] / "reels" / item["new"] / "metadata.json"
        if meta_p.exists():
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            if meta.get("global_episode") is None:
                backup(meta_p)
                meta["global_episode"] = item["number"]
                write_json(meta_p, meta)
    for week, items in by_week.items():
        week_meta_p = project / week / "metadata.json"
        if week_meta_p.exists():
            meta = json.loads(week_meta_p.read_text(encoding="utf-8"))
            by_rank = {i["rank"]: i for i in items}
            for r in meta.get("reels") or []:
                if isinstance(r, dict) and r.get("num") in by_rank:
                    r["folder"] = by_rank[r["num"]]["new"]
            backup(week_meta_p)
            write_json(week_meta_p, meta)

        # 3. Stories that borrow a reel by number also name it by key
        keys_by_rank = {i["rank"]: i["key"] for i in items}
        for story_meta_p in sorted((project / week / "stories").glob("*/metadata.json")):
            story = json.loads(story_meta_p.read_text(encoding="utf-8"))
            num = story.get("reel_num")
            if isinstance(num, int) and num in keys_by_rank and not story.get("reel"):
                backup(story_meta_p)
                story["reel"] = keys_by_rank[num]
                write_json(story_meta_p, story)
    save_log()

    # 4. KCT Studio records: catalog, schedule and story map follow the new paths
    renames = [(i["week"], i["old"], i["new"]) for i in plan]
    for name in DATA_FILES:
        path = data_dir / name
        if not path.exists():
            continue
        data = rewrite_json(json.loads(path.read_text(encoding="utf-8")), renames)
        if name == "posting_schedule.json" and isinstance(data, list):
            for it in data:
                if isinstance(it, dict) and it.get("video_rel_path"):
                    it["video_filename"] = Path(it["video_rel_path"]).name
        write_json(path, data)
    log["done"] = True
    save_log()
    return log


def undo(log_path: Path):
    log = json.loads(log_path.read_text(encoding="utf-8"))
    # Edited files first: a reel's metadata.json was saved at its renamed path
    for original, saved in (log.get("file_backups") or {}).items():
        shutil.copy2(saved, original)
    for old, new in reversed(log["renames"]):
        if Path(new).exists() and not Path(old).exists():
            os.rename(new, old)
    print(f"Undone: {len(log['renames'])} renames reversed, {len(log.get('file_backups') or {})} files restored.")


def main():
    parser = argparse.ArgumentParser(description="Rename numbered reel folders to mon_1_..., tue_1_... (see the module docstring).")
    parser.add_argument("--project", help="Project folder (default: the active KCT Studio project)")
    parser.add_argument("--apply", action="store_true", help="Rename (without it, only the plan is printed)")
    parser.add_argument("--undo", help="Reverse a previous run from its rename_log.json")
    args = parser.parse_args()

    if args.undo:
        if server_running():
            sys.exit("KCT Studio is running. Stop it from the tray first, then undo.")
        undo(Path(args.undo))
        return

    if args.project:
        project = Path(args.project)
    else:
        from core.config import config_manager
        project = Path(config_manager.get_active_project())
    weeks = sorted((d for d in project.iterdir() if d.is_dir() and WEEK.match(d.name)), key=lambda d: int(d.name[1:]))
    plan = [item for w in weeks for item in plan_week(w)]
    clashes = [i for i in plan if (project / i["week"] / "reels" / i["new"]).exists()]
    for item in plan:
        print(f"{item['week']}/reels/{item['old']}  ->  {item['new']}   (#{item['number']})")
    print(f"\n{len(plan)} reel folders in {len({i['week'] for i in plan})} weeks.")
    if clashes:
        sys.exit(f"Stopped: {len(clashes)} new names already exist, e.g. {clashes[0]['week']}/reels/{clashes[0]['new']}")
    if not args.apply:
        print("Dry run: nothing was changed. Stop KCT Studio, then run again with --apply.")
        return
    if server_running():
        sys.exit("KCT Studio is running (port 7860). Stop it from the tray first (and let any render finish).")
    if not plan:
        print("Nothing to rename.")
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log = apply(project, plan, DATA_DIR / "backups" / f"reel_rename_{stamp}")
    from core.week_links import export_week_links  # loads the rewritten catalog
    for week in sorted({i["week"] for i in plan}):
        if (project / week / "published_links.json").exists():
            export_week_links(project, week)
    print(f"Renamed {len(plan)} reel folders. Undo with: python scripts/rename_reels_by_day.py --undo "
          f"\"{Path(log['backup_dir']) / 'rename_log.json'}\"")


if __name__ == "__main__":
    main()
