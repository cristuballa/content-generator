"""
Makes every narration script advertise the books and merch, pointing viewers to the bio and the links comment
posted right after publishing (descriptions carry no links any more).

- Reels: the [CTA] section becomes "If this blew your mind, it's just one part of what we uncover in our books. They're
  linked in the bio and comments, along with our sacred art merch. Follow for more secrets hidden in Scripture." (keeping "Watch the full episode on our channel." where the CTA sent viewers to the
  full episode); reels without a [CTA] section get one.
- Long-form: one CTA paragraph before the closing sign-off ("Until next time...", "Thank you for watching...").
- Earlier CTA wordings ("If this study opened your eyes...", "Our books and sacred art merch are linked...") are
  updated to the current one.
- Old "link in the description" / "link in bio" wording is pointed at the comments / channel instead.

A zip backup of every changed script is written to <project>/_backups/ first.

    python scripts/apply_books_merch_cta.py --dry-run
    python scripts/apply_books_merch_cta.py [--project C:\\Projects\\BHSR]
"""

import argparse
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


REEL_EPISODE_SAVE = "Watch the full episode on our channel, and save this so you don't lose this scripture."
REEL_STANDALONE_SAVE = "Save this so you don't lose this scripture."
BOOKS_LINE = ("If this blew your mind, it's just one part of what we uncover in our books. They're linked in the bio and "
              "comments, along with our sacred art merch.")
FOLLOW_LINE = "Follow for more secrets hidden in Scripture."
LONG_FORM_CTA = BOOKS_LINE
REEL_CTA = REEL_STANDALONE_SAVE + " " + BOOKS_LINE + " " + FOLLOW_LINE
ADVERTISES = re.compile(r"\b(?:amazon|etsy|our (?:two )?books|merch)\b", re.IGNORECASE)
SIGN_OFF = re.compile(r"^\W*(?:until next time|thank you for watching|thanks for watching)", re.IGNORECASE)
END_MARKERS = re.compile(r"^\s*(?:WORD COUNT|SOURCES|METADATA|HASHTAGS|TAGS|NOTES)\b", re.IGNORECASE)
NON_NARRATION = re.compile(r"^\s*(?:\[.*\]|\(.*\)|[=\-_~*]{3,}|the music\b.*)\s*$", re.IGNORECASE)

WORDING_FIXES = [
    # Earlier CTA wordings -> current wording (long-form first: it contains the reel sentence)
    (re.compile(r"If this study opened your eyes, go deeper\. Our books and sacred art merch are linked in the bio and comments\."),
     BOOKS_LINE),
    (re.compile(r"Our books and sacred art merch are linked in the bio and comments\. Follow for more secrets hidden in Scripture\."),
     BOOKS_LINE + " " + FOLLOW_LINE),
    (re.compile(r"(?:The links are|Tap the link) in the description below\.", re.IGNORECASE), "They're linked in the bio and comments."),
    (re.compile(r"check the link in bio for the full master documentary", re.IGNORECASE), "watch the full documentary on our channel"),
    (re.compile(r"WATCH FULL EPISODE\s*[—-]\s*LINK IN DESCRIPTION"), "BOOKS & MERCH — LINKS IN THE COMMENTS"),
    # Short-form reel retention upgrades (prioritizing saves & shares before books/merch):
    (re.compile(r"Watch the full episode on our channel\.\s*If this blew your mind, it's just one part of what we uncover in our books\. They're linked in the bio and comments, along with our sacred art merch\. Follow for more secrets hidden in Scripture\."),
     f"{REEL_EPISODE_SAVE} {BOOKS_LINE} {FOLLOW_LINE}"),
    (re.compile(r"(?<!our channel, and )(?<!our channel\. )(?<!save this so you don't lose this scripture\. )If this blew your mind, it's just one part of what we uncover in our books\. They're linked in the bio and comments, along with our sacred art merch\. Follow for more secrets hidden in Scripture\."),
     f"{REEL_STANDALONE_SAVE} {BOOKS_LINE} {FOLLOW_LINE}"),
]


def fix_wording(text: str) -> str:
    for rx, new in WORDING_FIXES:
        text = rx.sub(new, text)
    return text


def update_reel(text: str) -> str:
    text = fix_wording(text)
    lines = text.splitlines()
    cta = next((i for i, l in enumerate(lines) if re.match(r"\s*\[CTA\b", l, re.IGNORECASE)), None)
    if cta is not None:
        end = cta + 1
        while end < len(lines) and not lines[end].strip().startswith(("[", "===")):
            end += 1
        old_body = " ".join(lines[cta + 1:end])
        if ADVERTISES.search(old_body) and "save this so you don't lose this scripture" in old_body:
            return text
        new_body = (REEL_EPISODE_SAVE + " " if re.search(r"full episode", old_body, re.IGNORECASE) else REEL_STANDALONE_SAVE + " ") + BOOKS_LINE + " " + FOLLOW_LINE
        return "\n".join(lines[:cta + 1] + [new_body, ""] + lines[end:]).rstrip() + "\n"
    if ADVERTISES.search(text):
        return text
    # No [CTA] section: add one after the narration (before a trailing ===== / WORD COUNT block)
    insert_at = len(lines)
    for i, line in enumerate(lines):
        if line.strip().startswith("===") and any(END_MARKERS.match(l) for l in lines[i + 1:i + 3]):
            insert_at = i
            break
    while insert_at > 0 and not lines[insert_at - 1].strip():
        insert_at -= 1
    return "\n".join(lines[:insert_at] + ["", "[CTA]", REEL_CTA, ""] + lines[insert_at:]).rstrip() + "\n"


def update_long_form(text: str) -> str:
    text = fix_wording(text)
    if ADVERTISES.search(text):
        return text
    lines = text.splitlines()
    stop = next((i for i, l in enumerate(lines) if END_MARKERS.match(l)), len(lines))
    narration = [i for i in range(stop) if lines[i].strip() and not NON_NARRATION.match(lines[i])]
    if not narration:
        return text
    last = narration[-1]
    insert_at = last if SIGN_OFF.match(lines[last]) else last + 1
    block = [LONG_FORM_CTA, ""] if insert_at == last else ["", LONG_FORM_CTA, ""]
    return "\n".join(lines[:insert_at] + block + lines[insert_at:]).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=config_manager.get_active_project())
    parser.add_argument("--start-week", type=int, default=1, help="Starting week number (e.g. 3 for W03 onward)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    project = Path(args.project)

    def week_num(p: Path) -> int:
        for part in p.parts:
            m = re.match(r"^W(\d+)$", part, re.IGNORECASE)
            if m:
                return int(m.group(1))
        return 0

    reels = sorted(project.glob("W*/reels/*/script*.txt"))
    long_form = sorted(set(
        list(project.glob("W*/long_form/*/script*.txt")) + list(project.glob("W*/long_form/script*.txt"))
        + list(project.glob("W*/long_form/*/script*.md"))
    ))
    if args.start_week > 1:
        reels = [p for p in reels if week_num(p) >= args.start_week]
        long_form = [p for p in long_form if week_num(p) >= args.start_week]
    changes = {}
    for path, fn in [(p, update_reel) for p in reels] + [(p, update_long_form) for p in long_form]:
        raw = path.read_text(encoding="utf-8", errors="replace")
        new = fn(raw)
        if new != raw:
            changes[path] = new
    n_reels = sum(1 for p in changes if "reels" in p.parts)
    print(f"Scripts to update: {len(changes)} (reels {n_reels}, long-form {len(changes) - n_reels}) "
          f"of {len(reels)} reels / {len(long_form)} long-form")
    if args.dry_run or not changes:
        print("Dry run: nothing written." if args.dry_run else "Nothing to change.")
        return

    backup_dir = project / "_backups"
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / f"scripts_before_books_cta_{time.strftime('%Y%m%d_%H%M%S')}.zip"
    with zipfile.ZipFile(backup, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in changes:
            zf.write(path, path.relative_to(project).as_posix())
    for path, text in changes.items():
        path.write_text(text, encoding="utf-8")
    print(f"Backup: {backup}\nUpdated {len(changes)} scripts.")


if __name__ == "__main__":
    main()
