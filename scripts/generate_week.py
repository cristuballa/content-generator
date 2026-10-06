"""
Renders a whole week in the right order: every long-form episode, then the reels, then the stories (stories borrow
the reels' artwork, so they come last).

A video is skipped only when it is current. For long-form and reels that means its cached narration was recorded from
the script as it is now (same words, same books line, same pronunciations) and the recording finished. Stories, which
have no narration, are current when the video is newer than their script and metadata. Missing videos are rendered and
outdated ones re-rendered (finished images are reused).

    python scripts/generate_week.py --week 5 [--project C:\\Projects\\BHSR] [--dry-run] [--force]
"""

import argparse
import importlib.util
import subprocess
import sys
import time
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_ROOT))
from core.reels import ordered_reels, reel_key  # noqa: E402  (posting order of mon_1, mon_2, tue_1... reel folders)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

NOT_EPISODES = {"images", "temp", "__pycache__"}


def find_script(project: Path, name: str) -> Path:
    for cand in (project / name, project / "scripts" / name, PIPELINE_ROOT / "scripts" / name):
        if cand.exists():
            return cand
    raise FileNotFoundError(f"{name} not found in {project} or {PIPELINE_ROOT / 'scripts'}")


def load_generator(path: Path):
    """Imports a generator so its own script cleaning decides what the narration should be (None if it can't load)."""
    try:
        spec = importlib.util.spec_from_file_location(f"_week_{path.stem}", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception as e:
        print(f"[notice] could not load {path.name} ({e}); falling back to file dates", flush=True)
        return None


def long_form_episodes(lf_dir: Path):
    if not lf_dir.exists():
        return []
    return sorted(d for d in lf_dir.iterdir()
                  if d.is_dir() and d.name.lower() not in NOT_EPISODES and not d.name.startswith(("_", "sample")))


def item_folders(parent: Path):
    """Reel / story folders in generator order (the generators address them by position)."""
    if not parent.exists():
        return []
    return sorted(d for d in parent.iterdir() if d.is_dir() and d.name.lower() not in ("temp", "temp_slides"))


def newer_than(sources, video_mtime: float) -> bool:
    return any(p.exists() and p.stat().st_mtime > video_mtime for p in sources)


def narration_state(recorded_script: Path, raw_voice_glob: str, expected) -> str:
    """'stale' when the cached narration was made from another script or never finished, else 'current'."""
    if recorded_script.read_text(encoding="utf-8", errors="replace").strip() != expected.strip():
        return "stale"
    return "current" if list(recorded_script.parent.glob(raw_voice_glob)) else "stale"


def episode_state(ep_dir: Path, gv) -> str:
    finals = list(ep_dir.glob("*_final_16x9.mp4"))
    if not finals:
        return "missing"
    recorded = ep_dir / "temp" / "voice_script.txt"
    if gv and recorded.exists():
        narration, _ = gv.parse_episode_folder(ep_dir)
        expected = gv.prepare_voice_script(gv.ensure_books_cta(narration), gv.PRONUNCIATION_MAP)
        return narration_state(recorded, "*_voice_raw.mp3", expected)
    return "stale" if newer_than([ep_dir / "script_30min.txt"], max(p.stat().st_mtime for p in finals)) else "current"


def reel_state(folder: Path, gr) -> str:
    finals = list(folder.glob("*_final_reel.mp4"))
    if not finals:
        return "missing"
    recorded = sorted((folder / "temp").glob("*_voice_script.txt")) if (folder / "temp").exists() else []
    script = folder / "script.txt"
    if gr and recorded and script.exists():
        narration = gr.clean_script_for_tts(script.read_text(encoding="utf-8", errors="replace"))
        expected = gr.prepare_voice_script(gr.ensure_books_cta(narration))
        return narration_state(recorded[0], "*_raw_voice.wav", expected)
    return "stale" if newer_than([script, folder / "metadata.json"], max(p.stat().st_mtime for p in finals)) else "current"


def story_state(folder: Path) -> str:
    video = folder / "story_video_final.mp4"
    if not video.exists():
        return "missing"
    return "stale" if newer_than([folder / "story_script.md", folder / "metadata.json"], video.stat().st_mtime) else "current"


def run(label: str, cmd, cwd: Path) -> bool:
    print(f"\n{'=' * 78}\n▶ {label}\n  {' '.join(map(str, cmd))}\n{'=' * 78}", flush=True)
    start = time.time()
    code = subprocess.run([str(c) for c in cmd], cwd=str(cwd)).returncode
    print(f"■ {label}: {'done' if code == 0 else f'FAILED (exit {code})'} in {(time.time() - start) / 60:.1f} min", flush=True)
    return code == 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--week", "-w", required=True, help="week number, e.g. 5 or W05")
    parser.add_argument("--project", default=None, help="project folder (default: the active project)")
    parser.add_argument("--force", action="store_true", help="re-render everything, even videos that are current")
    parser.add_argument("--dry-run", action="store_true", help="show what would be rendered, without rendering")
    args = parser.parse_args()

    if args.project:
        project = Path(args.project)
    else:
        sys.path.insert(0, str(PIPELINE_ROOT))
        from core.config import config_manager
        project = Path(config_manager.get_active_project())
    week = int(str(args.week).upper().replace("W", ""))
    week_dir = project / f"W{week:02d}"
    if not week_dir.exists():
        sys.exit(f"Week folder not found: {week_dir}")

    py = sys.executable
    video_gen, reel_gen, story_gen = (find_script(project, n) for n in ("generate_video.py", "generate_reel.py", "generate_story.py"))
    gv, gr = (None, None) if args.force else (load_generator(video_gen), load_generator(reel_gen))
    plan = []  # (label, state, command)

    # 1. Long-form: each episode folder (or the long_form folder itself when there are none). The long-form generator
    #    re-records outdated narration by itself, so --force-rebuild is only passed with --force.
    episodes = long_form_episodes(week_dir / "long_form")
    for i, ep in enumerate(episodes, 1):
        state = "stale" if args.force else episode_state(ep, gv)
        cmd = [py, "-u", video_gen, "--week", week, "--video", i] + (["--force-rebuild"] if args.force else [])
        plan.append((f"Long-form {i}/{len(episodes)}: {ep.name}", state, cmd))
    if not episodes and (week_dir / "long_form").exists():
        plan.append(("Long-form", "missing", [py, "-u", video_gen, "--week", week]))

    # 2. Reels, then 3. stories. Both generators keep an existing video unless --force-rebuild is passed.
    reels = ordered_reels(week_dir / "reels")
    for n, folder in enumerate(reels, 1):
        state = "stale" if args.force else reel_state(folder, gr)
        cmd = [py, "-u", reel_gen, "--week", week, "--reel", reel_key(folder) or n] + (["--force-rebuild"] if state == "stale" else [])
        plan.append((f"Reel {n}/{len(reels)}: {folder.name}", state, cmd))
    stories = item_folders(week_dir / "stories")
    for n, folder in enumerate(stories, 1):
        state = "stale" if args.force else story_state(folder)
        cmd = [py, "-u", story_gen, "--week", week, "--story", n] + (["--force-rebuild"] if state == "stale" else [])
        plan.append((f"Story {n}/{len(stories)}: {folder.name}", state, cmd))

    words = {"missing": "render (no video yet)", "stale": "re-render (script changed since the video was made)"}
    results = []
    for label, state, cmd in plan:
        if state == "current":
            print(f"✔ {label}: up to date, skipped", flush=True)
        elif args.dry_run:
            print(f"• {label}: would {words[state]}", flush=True)
        else:
            results.append((label, run(label, cmd, project)))
    if args.dry_run:
        return

    print(f"\n{'=' * 78}\nWEEK W{week:02d} SUMMARY")
    for label, ok in results:
        print(f"  {'✔' if ok else '✘'} {label}")
    if not results:
        print("  Everything is up to date.")
    print("=" * 78, flush=True)
    sys.exit(0 if all(ok for _, ok in results) else 1)


if __name__ == "__main__":
    main()
