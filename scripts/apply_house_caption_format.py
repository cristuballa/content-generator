"""
Rewrites every metadata file in the project to the house caption format:

    HOOK IN CAPITALS / scripture references / description / hashtags

- metadata.json / episode_metadata.json (long-form, reels, stories): all platform captions are rebuilt from the
  file's own hook, scriptures, description and hashtags; merch blocks are dropped; pinned_comment becomes the links
  comment that is posted after publishing.
- metadata.txt (older reels): rewritten with TITLE / HOOK / DESCRIPTION / HASHTAGS sections plus the rebuilt
  captions; EDITING notes are kept.
- Week summary and Substack metadata.json: merch blocks removed, pinned_comment updated.

A zip backup of every metadata file is written to <project>/_backups/ first.

    python scripts/apply_house_caption_format.py --dry-run
    python scripts/apply_house_caption_format.py [--project C:\\Projects\\BHSR]
"""

import argparse
import json
import re
import sys
import time
import zipfile
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.config import config_manager  # noqa: E402
from core.social_dispatcher import DEFAULT_BHRS_PINNED_COMMENT, SocialDispatcher as SD  # noqa: E402

CAPTION_KEYS = ("facebook_caption", "youtube_description", "instagram_caption", "tiktok_caption", "threads_caption", "x_post")
VIDEO_KINDS = ("long_form", "reels", "stories")


def kind_of(path: Path, project: Path) -> str:
    parts = path.relative_to(project).parts
    return parts[1] if len(parts) > 2 else "week"


def folder_title(path: Path) -> str:
    return re.sub(r"^\d+[_\-]", "", path.parent.name).replace("_", " ").strip().title()


def rewrite_json(path: Path, kind: str):
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        return None
    before = json.dumps(data, ensure_ascii=False, sort_keys=True)

    if kind in VIDEO_KINDS:
        sibling = path.with_name("episode_metadata.json")
        if path.name == "metadata.json" and sibling.exists():
            # The episode file often carries the full hashtag list that was actually posted
            richer = json.loads(sibling.read_text(encoding="utf-8")).get("hashtags") or []
            if isinstance(richer, list) and len(richer) > len(data.get("hashtags") or []):
                data["hashtags"] = richer
        caps = SD.build_platform_captions(data, fallback_title=folder_title(path), include_timestamps=(kind == "long_form"))
        for key in CAPTION_KEYS + ("pinned_comment",):
            data[key] = caps[key]
    else:
        for key in CAPTION_KEYS:
            if isinstance(data.get(key), str):
                data[key] = SD.strip_promo_text(data[key])
        if "pinned_comment" in data:
            data["pinned_comment"] = DEFAULT_BHRS_PINNED_COMMENT
    data.pop("merch_block", None)

    if json.dumps(data, ensure_ascii=False, sort_keys=True) == before:
        return None
    indent = 4 if re.search(r"^\{\s*\n {4}\"", raw) else 2
    return json.dumps(data, indent=indent, ensure_ascii=False) + ("\n" if raw.endswith("\n") else "")


def rewrite_txt(path: Path):
    raw = path.read_text(encoding="utf-8", errors="replace")
    meta = SD.parse_metadata_txt(raw)
    meta["title"] = meta.get("title") or folder_title(path)
    caps = SD.build_platform_captions(meta, fallback_title=meta["title"], include_timestamps=False)
    first = raw.splitlines()[0].strip() if raw.strip() else ""
    editing = re.search(r"^EDITING:.*\Z", raw, flags=re.MULTILINE | re.DOTALL)

    out = [first, ""] if first.upper().startswith("EPISODE") else []
    out += [f"TITLE: {meta['title']}", f"HOOK: {caps['hook']}"]
    if caps["scriptures"]:
        out.append(f"SCRIPTURES: {caps['scriptures']}")
    has_content = bool(caps["body"] or caps["hashtags_string"])
    if has_content:
        out += ["DESCRIPTION:", caps["body"], "", "HASHTAGS:", caps["hashtags_string"]]
    out += ["", "PINNED COMMENT:", DEFAULT_BHRS_PINNED_COMMENT, ""]
    if has_content:
        out.append(f"YOUTUBE SHORTS TITLE: {meta.get('youtube_shorts_title') or meta['title']}")
        for label, key in (("YOUTUBE DESCRIPTION", "youtube_description"), ("FACEBOOK CAPTION", "facebook_caption"),
                           ("INSTAGRAM CAPTION", "instagram_caption"), ("THREADS CAPTION", "threads_caption"),
                           ("TIKTOK CAPTION", "tiktok_caption")):
            out += [f"{label}:", caps[key], ""]
    if editing:
        out.append(editing.group(0).rstrip())
    text = "\n".join(out).rstrip() + "\n"

    # Safety: the rewritten file must produce exactly the same captions when read back
    again = SD.build_platform_captions(SD.parse_metadata_txt(text), fallback_title=meta["title"], include_timestamps=False)
    if any(again[k] != caps[k] for k in CAPTION_KEYS):
        raise ValueError("captions differ after round-trip")
    return None if text == raw else text


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=config_manager.get_active_project())
    parser.add_argument("--dry-run", action="store_true", help="report what would change without writing")
    args = parser.parse_args()
    project = Path(args.project)

    files = sorted(
        p for pattern in ("W*/**/metadata.json", "W*/**/episode_metadata.json", "W*/metadata.json", "W*/**/metadata.txt")
        for p in project.glob(pattern) if "temp" not in p.parts
    )
    files = list(dict.fromkeys(files))
    print(f"Project: {project}  ({len(files)} metadata files)")

    changes, errors = {}, []
    for path in files:
        try:
            new = rewrite_txt(path) if path.suffix == ".txt" else rewrite_json(path, kind_of(path, project))
            if new is not None:
                changes[path] = new
        except Exception as e:
            errors.append((path, str(e)))

    by_kind = {}
    for path in changes:
        key = f"{kind_of(path, project)}/{path.name}"
        by_kind[key] = by_kind.get(key, 0) + 1
    print(f"Files to update: {len(changes)}")
    for key, count in sorted(by_kind.items()):
        print(f"  {count:4d}  {key}")
    for path, err in errors:
        print(f"  SKIPPED {path.relative_to(project)}: {err}")

    if args.dry_run or not changes:
        print("Dry run: nothing written." if args.dry_run else "Nothing to change.")
        return

    backup_dir = project / "_backups"
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / f"metadata_before_house_format_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(backup, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            zf.write(path, path.relative_to(project).as_posix())
    print(f"Backup: {backup}")

    for path, text in changes.items():
        path.write_text(text, encoding="utf-8")
    print(f"Updated {len(changes)} files.")


if __name__ == "__main__":
    main()
