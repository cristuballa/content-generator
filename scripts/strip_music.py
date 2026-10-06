"""
Removes the background music bed from rendered videos and from the generators' cached audio mixes.

The music came from Demucs stems of an unlicensed recording, which risks copyright claims and blocks monetization.
The generators now master narration only; this script brings existing files in line:

- Cached mixes (temp/*_master_soundtrack.wav, temp/*_master_audio.wav) are re-mastered from the clean narration
  next to them, or moved to the backup folder when that narration is gone (the next render re-synthesizes).
- Stories: the music track is replaced with silence.
- Reels / long-form / ad outros with their clean narration still on disk: the audio is replaced by the voice-only
  master (video stream copied, nothing re-encoded). Reels with an ad outro are re-joined from the fixed parts.
- Everything else: with --demucs the narration is separated from the finished mix (Demucs, ComfyUI venv).

Each original audio track is saved to <project>/_backups/music_removed_<time>/ as .m4a first, so every change can be
undone. Files touched in the last 10 minutes (a render in progress) are skipped.

    python scripts/strip_music.py --dry-run
    python scripts/strip_music.py [--demucs] [--project C:\\Projects\\BHSR]
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

PIPELINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PIPELINE_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from core.config import config_manager  # noqa: E402

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"
DEMUCS_PYTHON = Path(r"C:\Users\User\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Scripts\python.exe")
VOICE_CHAIN = ("highpass=f=75,lowpass=f=7200,equalizer=f=220:t=q:w=1.2:g=2.5,equalizer=f=3400:t=q:w=1.8:g=-4.5,"
               "equalizer=f=5500:t=q:w=1.5:g=-5.0,deesser=i=0.6:m=0.5:f=0.5,"
               "compand=attacks=0.01:decays=0.08:points=-80/-80|-22/-10|-10/-3|0/0,volume=3.2")
LOUDNORM = "loudnorm=I=-11.5:TP=-0.5:LRA=5"
VOICE_TAG = "voice only"
RECENT_SEC = 600
MATCH_SEC = 1.5
CF = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


def run(cmd):
    subprocess.run([str(c) for c in cmd], check=True, capture_output=True, creationflags=CF)


def probe(path: Path) -> dict:
    out = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration:stream=codec_type:stream_tags=title,name",
                          "-of", "default=noprint_wrappers=1", str(path)], capture_output=True, text=True, creationflags=CF).stdout
    info = {"duration": 0.0, "audio_title": "", "has_audio": False}
    for line in out.splitlines():
        if line.startswith("duration="):
            try:
                info["duration"] = float(line.split("=", 1)[1])
            except ValueError:
                pass
        elif line == "codec_type=audio":
            info["has_audio"] = True
        elif line.startswith(("TAG:title=", "TAG:name=")):  # MP4 keeps the stream title as the handler "name"
            info["audio_title"] = line.split("=", 1)[1]
    return info


def recent(path: Path) -> bool:
    return time.time() - path.stat().st_mtime < RECENT_SEC


def master_voice(src: Path, dst: Path, chain: str = VOICE_CHAIN):
    tmp = dst.with_name(dst.stem + "_tmpmaster.wav")
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", src,
         "-filter_complex", f"[0:a]{chain + ',' if chain else ''}{LOUDNORM}[out]", "-map", "[out]", "-ar", "44100", tmp])
    tmp.replace(dst)


def replace_audio(video: Path, audio: Path = None):
    """Swaps the video's audio for `audio` (or silence), copying the video stream untouched."""
    tmp = video.with_name(video.stem + "_tmpmux" + video.suffix)
    cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", video]
    if audio is None:
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"]
    else:
        cmd += ["-i", audio]
    cmd += ["-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest",
            "-metadata:s:a:0", f"title={VOICE_TAG}", "-movflags", "+faststart", tmp]
    run(cmd)
    tmp.replace(video)


def concat(parts, out: Path):
    lst = out.with_name(out.stem + "_concat.txt")
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
    tmp = out.with_name(out.stem + "_tmpconcat" + out.suffix)
    try:
        run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy",
             "-metadata:s:a:0", f"title={VOICE_TAG}", tmp])
        tmp.replace(out)
    finally:
        lst.unlink(missing_ok=True)


def demucs_vocals(video: Path, work: Path) -> Path:
    wav = work / "mix.wav"
    run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", video, "-vn", "-ac", "2", "-ar", "44100", wav])
    run([DEMUCS_PYTHON, "-m", "demucs", "--two-stems", "vocals", "-n", "htdemucs", "-o", work, wav])
    vocals = work / "htdemucs" / "mix" / "vocals.wav"
    out = work / "vocals_master.wav"
    master_voice(vocals, out, chain="")  # the narration already carries its EQ from the original mix
    return out


# ---------------------------------------------------------------------------------------------------------------
def cache_pairs(project: Path):
    """(cached mix, clean narration or None) for every generator temp folder, plus the shared ad outros."""
    for mix in sorted(list(project.glob("W*/**/temp/*_master_soundtrack.wav")) + list(project.glob("W*/**/temp/*_master_audio.wav"))
                      + list(project.glob("shared_assets/temp_ad_*/*_master_soundtrack.wav"))):
        if mix.name.endswith("_master_soundtrack.wav"):
            raw = mix.with_name(mix.name.replace("_master_soundtrack.wav", "_raw_voice.wav"))
        else:
            raw = mix.with_name(mix.name.replace("_master_audio.wav", "_voice_raw.mp3"))
        yield mix, (raw if raw.exists() else None)


def videos(project: Path):
    for week in sorted(project.glob("W[0-9]*")):
        for mp4 in sorted(list(week.glob("long_form/*.mp4")) + list(week.glob("long_form/*/*.mp4"))):
            if "sample" not in mp4.name.lower():
                yield "long_form", mp4
        for mp4 in sorted(week.glob("reels/*/*.mp4")):
            yield "reel", mp4
        for mp4 in sorted(week.glob("stories/*/*.mp4")):
            yield "story", mp4
    for mp4 in sorted(project.glob("shared_assets/ad_outro_*.mp4")):
        yield "ad_outro", mp4


def voice_masters_near(video: Path, kind: str, project: Path):
    if kind == "ad_outro":
        n = video.stem.rsplit("_", 1)[-1]
        temp = project / "shared_assets" / f"temp_ad_{n}"
    else:
        temp = video.parent / "temp"
    if not temp.exists():
        return []
    return sorted(list(temp.glob("*_master_soundtrack.wav")) + list(temp.glob("*_master_audio.wav")))


def plan(project: Path, use_demucs: bool):
    caches = []
    for mix, raw in cache_pairs(project):
        caches.append(("skip-recent" if recent(mix) else ("remaster" if raw else "retire"), mix, raw))
    fixable_masters = {mix for action, mix, raw in caches if action == "remaster"}
    durations = {}

    def dur(p):
        if p not in durations:
            durations[p] = probe(p)["duration"]
        return durations[p]

    jobs = []
    for kind, mp4 in videos(project):
        if recent(mp4):
            jobs.append(("skip-recent", kind, mp4, None))
            continue
        info = probe(mp4)
        if info["audio_title"] == VOICE_TAG or not info["has_audio"] and kind != "story":
            jobs.append(("done", kind, mp4, None))
            continue
        if kind == "story":
            jobs.append(("silence", kind, mp4, None))
            continue
        masters = [m for m in voice_masters_near(mp4, kind, project) if m in fixable_masters]
        match = next((m for m in masters if abs(dur(m) - info["duration"]) <= MATCH_SEC), None)
        if match:
            jobs.append(("voice", kind, mp4, match))
            continue
        clean = mp4.with_name(mp4.name.replace("_final_reel.mp4", "_clean.mp4")) if kind == "reel" else None
        if clean and clean != mp4 and clean.exists() and any(abs(dur(m) - probe(clean)["duration"]) <= MATCH_SEC for m in masters):
            jobs.append(("rejoin-ad", kind, mp4, clean))
            continue
        jobs.append(("demucs" if use_demucs else "needs-demucs", kind, mp4, None))
    return caches, jobs


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default=config_manager.get_active_project())
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--demucs", action="store_true", help="separate narration from the mix where no clean narration exists")
    parser.add_argument("--include-recent", action="store_true", help="also process files written in the last 10 minutes "
                        "(only when no render is running)")
    args = parser.parse_args()
    project = Path(args.project)
    global RECENT_SEC
    if args.include_recent:
        RECENT_SEC = 0
    if args.demucs and not DEMUCS_PYTHON.exists():
        sys.exit(f"Demucs Python not found: {DEMUCS_PYTHON}")

    caches, jobs = plan(project, args.demucs)
    count = lambda rows, a: sum(1 for r in rows if r[0] == a)  # noqa: E731
    print(f"Cached mixes: {len(caches)} | re-master {count(caches, 'remaster')} | retire (no narration) "
          f"{count(caches, 'retire')} | in use now {count(caches, 'skip-recent')}")
    print(f"Videos: {len(jobs)} | silence (stories) {count(jobs, 'silence')} | voice swap {count(jobs, 'voice')} | "
          f"re-join with ad {count(jobs, 'rejoin-ad')} | Demucs {count(jobs, 'demucs')} | "
          f"need --demucs {count(jobs, 'needs-demucs')} | already voice-only {count(jobs, 'done')} | "
          f"in use now {count(jobs, 'skip-recent')}")
    if args.dry_run:
        for action, kind, mp4, src in jobs:
            if action not in ("done",):
                print(f"  {action:<13} {mp4.relative_to(project).as_posix()}")
        print("Dry run: nothing written.")
        return

    backup = project / "_backups" / f"music_removed_{time.strftime('%Y%m%d_%H%M%S')}"
    backup.mkdir(parents=True, exist_ok=True)

    # 1. Caches: re-master from clean narration, or retire so the next render re-synthesizes
    for action, mix, raw in caches:
        rel = mix.relative_to(project)
        if action == "remaster":
            master_voice(raw, mix)
        elif action == "retire":
            dest = backup / "retired_caches" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(mix), str(dest))
    print("Caches done.", flush=True)

    # 2. Videos (ad outros first so reels can be re-joined from the fixed outro)
    order = {"ad_outro": 0, "long_form": 1, "reel": 2, "story": 3}
    done, failed = 0, []
    for action, kind, mp4, src in sorted(jobs, key=lambda j: order[j[1]]):
        if action not in ("silence", "voice", "rejoin-ad", "demucs"):
            continue
        rel = mp4.relative_to(project)
        try:
            dest = backup / "original_audio" / rel.with_suffix(".m4a")
            dest.parent.mkdir(parents=True, exist_ok=True)
            if probe(mp4)["has_audio"]:
                run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error", "-i", mp4, "-vn", "-c:a", "copy", dest])
            if action == "silence":
                replace_audio(mp4)
            elif action == "voice":
                replace_audio(mp4, src)
            elif action == "rejoin-ad":
                clean = src
                masters = voice_masters_near(clean, "reel", project)
                master = next(m for m in masters if abs(probe(m)["duration"] - probe(clean)["duration"]) <= MATCH_SEC)
                if probe(clean)["audio_title"] != VOICE_TAG:
                    replace_audio(clean, master)
                extra = probe(mp4)["duration"] - probe(clean)["duration"]
                outros = sorted(project.glob("shared_assets/ad_outro_*.mp4"), key=lambda o: abs(probe(o)["duration"] - extra))
                if not outros or abs(probe(outros[0])["duration"] - extra) > 2.0:
                    raise RuntimeError("could not identify the ad outro")
                concat([clean, outros[0]], mp4)
            elif action == "demucs":
                with tempfile.TemporaryDirectory() as work:
                    replace_audio(mp4, demucs_vocals(mp4, Path(work)))
            done += 1
            print(f"  ✔ {action:<10} {rel.as_posix()}", flush=True)
        except Exception as e:  # keep going; the original audio is in the backup
            failed.append((rel.as_posix(), str(e)[:200]))
            print(f"  ✘ {action:<10} {rel.as_posix()}: {str(e)[:200]}", flush=True)

    print(f"\nUpdated {done} videos. Original audio tracks: {backup}")
    if failed:
        print(f"{len(failed)} failed:")
        for rel, err in failed:
            print("  ", rel, "-", err)


if __name__ == "__main__":
    main()
