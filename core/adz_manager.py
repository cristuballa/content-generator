"""Advertisement Video Manager for C:\\Projects\\Adz-Video.

Manages scanning, listing, resolving, previewing, and deleting advertisement outro videos
used across reels and stories in the pipeline.
"""
import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

logger = logging.getLogger("AdzManager")

DEFAULT_ADZ_DIR = Path(r"C:\Projects\Adz-Video")
DEFAULT_ADZ_IMAGE_DIR = Path(r"C:\Projects\Adz-Image")
FALLBACK_SHARED_DIR = Path(r"C:\Projects\BHSR\shared_assets")

IMAGE_INFO = {
    "watchers_ad_cover.png": {
        "title": "The Watchers & The Word — Book Cover",
        "description": "High-impact front cover art for The Watchers & The Word on Etsy.",
        "is_recommended": True,
        "variant_num": 1
    },
    "watchers_ad_desk.png": {
        "title": "The Watchers & The Word — Desk Display",
        "description": "Cinematic desk setting with the printed book on wooden surface.",
        "is_recommended": False,
        "variant_num": 2
    },
    "watchers_ad_standing.png": {
        "title": "The Watchers & The Word — Standing Showcase",
        "description": "Upright studio view of The Watchers and the Word.",
        "is_recommended": False,
        "variant_num": 3
    },
    "hidden_secrets_ad_desk.png": {
        "title": "Hidden Secrets of the Bible — Desk Display",
        "description": "Bestselling Hidden Secrets book on ancient study desk.",
        "is_recommended": False,
        "variant_num": 4
    },
    "hidden_secrets_ad_standing.png": {
        "title": "Hidden Secrets of the Bible — Standing Showcase",
        "description": "Upright cover showcase for Hidden Secrets of the Bible.",
        "is_recommended": False,
        "variant_num": 5
    },
    "nt_gems_ad_desk.png": {
        "title": "Bible Hidden Gems (New Testament) — Desk Display",
        "description": "New Testament Hidden Gems book showcased on study desk.",
        "is_recommended": False,
        "variant_num": 6
    },
    "nt_gems_ad_standing.png": {
        "title": "Bible Hidden Gems (New Testament) — Standing Showcase",
        "description": "Upright showcase of Bible Hidden Gems: New Testament.",
        "is_recommended": False,
        "variant_num": 7
    },
    "ot_gems_ad_desk.png": {
        "title": "Bible Hidden Gems (Old Testament) — Desk Display",
        "description": "Old Testament Hidden Gems book showcased on study desk.",
        "is_recommended": False,
        "variant_num": 8
    },
    "ot_gems_ad_standing.png": {
        "title": "Bible Hidden Gems (Old Testament) — Standing Showcase",
        "description": "Upright showcase of Bible Hidden Gems: Old Testament.",
        "is_recommended": False,
        "variant_num": 9
    },
    "merch_slide_1_mug.png": {
        "title": "Sacred Merch — Ceramic Coffee Mug",
        "description": "Official Christian faith coffee mug for Etsy.",
        "is_recommended": False,
        "variant_num": 10
    },
    "merch_slide_2_cap.png": {
        "title": "Sacred Merch — Embroidered Cap",
        "description": "Official embroidered faith cap merchandise for Etsy.",
        "is_recommended": False,
        "variant_num": 11
    },
    "merch_slide_3_tee.png": {
        "title": "Sacred Merch — Premium Faith Tee",
        "description": "Official premium Christian faith apparel for Etsy.",
        "is_recommended": False,
        "variant_num": 12
    }
}

BUILTIN_INFO = {
    "ad_outro_1.mp4": {
        "title": "Ad 1: The Watchers & The Word — Book of Enoch Mysteries",
        "description": "Promotes Ezra Keys' new release: The Watchers and the Word: Unlocking the Secrets of the Book of Enoch on Etsy.",
        "script": "If this revelation opened your eyes, go deeper. In our new book, The Watchers and the Word: Unlocking the Secrets of the Book of Enoch by Ezra Keys, we decode the lost mysteries of the heavenly host and ancient Scripture. Available now on Etsy, linked in our bio and comments.",
        "is_recommended": True,
        "variant_num": 1
    },
    "ad_outro_2.mp4": {
        "title": "Ad 2: The Watchers & The Word — Forbidden History of the Watchers",
        "description": "Focuses on the forbidden history of the fallen watchers and ancient biblical texts.",
        "script": "Ready to uncover what was hidden? The Watchers and the Word reveals the forbidden history of the fallen watchers and the ancient biblical texts. Grab your copy of The Watchers and the Word on Etsy. Link in the bio and comments.",
        "is_recommended": False,
        "variant_num": 2
    },
    "ad_outro_3.mp4": {
        "title": "Ad 3: The Watchers & The Word — Deep Spiritual Study",
        "description": "Deep dive into understanding the spiritual realm and ancient texts.",
        "script": "If you want to understand the spiritual realm like never before, get our book, The Watchers and the Word: Unlocking the Secrets of the Book of Enoch by Ezra Keys. Available now on Etsy, linked in the bio and comments below.",
        "is_recommended": False,
        "variant_num": 3
    }
}

def get_adz_image_dir() -> Path:
    """Returns the dedicated directory for advertisement images."""
    d = DEFAULT_ADZ_IMAGE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d

def list_ad_images() -> List[Dict[str, Any]]:
    """Returns the full list of available advertisement images in C:\\Projects\\Adz-Image."""
    img_dir = get_adz_image_dir()
    img_exts = {".png", ".jpg", ".jpeg", ".webp"}
    files = [f for f in img_dir.iterdir() if f.is_file() and f.suffix.lower() in img_exts]

    results = []
    for f in sorted(files, key=lambda x: x.name.lower()):
        size_mb = round(f.stat().st_size / (1024 * 1024), 2)
        builtin = IMAGE_INFO.get(f.name, {})

        title = builtin.get("title")
        if not title:
            clean_stem = f.stem.replace("_", " ").replace("-", " ").title()
            title = clean_stem

        desc = builtin.get("description", "High-resolution 9:16 story ad image for Etsy promotion.")
        is_rec = builtin.get("is_recommended", False)
        variant_num = builtin.get("variant_num")

        results.append({
            "filename": f.name,
            "title": title,
            "description": desc,
            "media_type": "image",
            "duration_str": "Image Slide",
            "size_mb": size_mb,
            "width": 768,
            "height": 1344,
            "is_recommended": is_rec,
            "variant_num": variant_num,
            "image_url": f"/api/adz/image/{f.name}",
            "thumbnail_url": f"/api/adz/image/{f.name}",
            "modified_time": int(f.stat().st_mtime)
        })

    results.sort(key=lambda x: (
        0 if x["is_recommended"] else 1,
        x["variant_num"] if x["variant_num"] is not None else 99,
        x["filename"]
    ))
    return results

def resolve_ad_image(ad_ref: Union[str, int, None]) -> Optional[Path]:
    """Resolves an ad image reference to a valid file in C:\\Projects\\Adz-Image."""
    if ad_ref is None:
        return None
    img_dir = get_adz_image_dir()
    ref_str = str(ad_ref).strip()

    cand = img_dir / ref_str
    if cand.is_file():
        return cand
    cand_png = img_dir / f"{ref_str}.png"
    if cand_png.is_file():
        return cand_png

    if ref_str.isdigit():
        num = int(ref_str)
        imgs = list_ad_images()
        for it in imgs:
            if it.get("variant_num") == num:
                p = img_dir / it["filename"]
                if p.is_file():
                    return p
        if 1 <= num <= len(imgs):
            p = img_dir / imgs[num - 1]["filename"]
            if p.is_file():
                return p

    stem_matches = list(img_dir.glob(f"*{ref_str}*.png"))
    if stem_matches:
        return stem_matches[0]

    return None

def delete_ad_image(filename: str) -> bool:
    """Deletes an advertisement image file from Adz-Image directory."""
    safe_name = Path(filename).name
    target = get_adz_image_dir() / safe_name
    if not target.exists() or not target.is_file():
        return False
    try:
        target.unlink()
        return True
    except Exception as e:
        logger.error(f"Failed to delete ad image {safe_name}: {e}")
        return False



def get_adz_dir() -> Path:
    """Returns the dedicated directory for advertisement videos."""
    d = DEFAULT_ADZ_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_metadata() -> Dict[str, Any]:
    """Loads metadata.json from Adz-Video folder."""
    meta_p = get_adz_dir() / "metadata.json"
    if meta_p.exists():
        try:
            return json.loads(meta_p.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"Failed to parse ad metadata.json: {e}")
    return {}


def save_metadata(data: Dict[str, Any]) -> None:
    """Saves metadata.json in Adz-Video folder."""
    meta_p = get_adz_dir() / "metadata.json"
    try:
        meta_p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to save ad metadata.json: {e}")


def probe_video(video_path: Path) -> Dict[str, Any]:
    """Extracts duration and dimensions using ffprobe."""
    info = {"duration": 0.0, "width": 0, "height": 0}
    if not video_path.exists():
        return info
    ffprobe = shutil.which("ffprobe") or "ffprobe"
    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "format=duration:stream=width,height",
        "-of", "default=noprint_wrappers=1",
        str(video_path)
    ]
    cf = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=5, creationflags=cf)
        for line in res.stdout.splitlines():
            line = line.strip()
            if line.startswith("duration="):
                try:
                    info["duration"] = round(float(line.split("=", 1)[1]), 1)
                except ValueError:
                    pass
            elif line.startswith("width="):
                try:
                    info["width"] = int(line.split("=", 1)[1])
                except ValueError:
                    pass
            elif line.startswith("height="):
                try:
                    info["height"] = int(line.split("=", 1)[1])
                except ValueError:
                    pass
    except Exception as e:
        logger.debug(f"ffprobe failed for {video_path.name}: {e}")
    return info


def format_duration(seconds: float) -> str:
    """Formats seconds into mm:ss or 0:ss."""
    if not seconds:
        return "--:--"
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


def ensure_existing_ads_copied() -> None:
    """Ensures ad outro videos from shared_assets are copied into Adz-Video folder."""
    adz_dir = get_adz_dir()
    if FALLBACK_SHARED_DIR.exists():
        for src in FALLBACK_SHARED_DIR.glob("ad_outro*.mp4"):
            dest = adz_dir / src.name
            if not dest.exists():
                try:
                    shutil.copy2(src, dest)
                    logger.info(f"Copied {src.name} to {dest}")
                except Exception as e:
                    logger.warning(f"Could not copy {src} to {dest}: {e}")



def list_ad_videos() -> List[Dict[str, Any]]:
    """Returns the full list of available advertisement videos in C:\\Projects\\Adz-Video."""
    ensure_existing_ads_copied()
    adz_dir = get_adz_dir()
    meta = load_metadata()

    # Search for all supported video extensions
    video_exts = {".mp4", ".mov", ".webm", ".mkv"}
    files = [f for f in adz_dir.iterdir() if f.is_file() and f.suffix.lower() in video_exts]

    results = []
    for f in sorted(files, key=lambda x: x.name.lower()):
        size_mb = round(f.stat().st_size / (1024 * 1024), 2)
        probe = probe_video(f)
        dur = probe.get("duration", 0.0)

        f_meta = meta.get(f.name, {})
        builtin = BUILTIN_INFO.get(f.name, {})

        # Friendly title
        title = f_meta.get("title") or builtin.get("title")
        if not title:
            clean_stem = f.stem.replace("_", " ").replace("-", " ").title()
            title = clean_stem

        desc = f_meta.get("description") or builtin.get("description", "")
        script = f_meta.get("script") or builtin.get("script", "")
        is_rec = f_meta.get("is_recommended", builtin.get("is_recommended", False))
        variant_num = builtin.get("variant_num")

        results.append({
            "filename": f.name,
            "title": title,
            "description": desc,
            "script": script,
            "duration": dur,
            "duration_str": format_duration(dur),
            "size_mb": size_mb,
            "width": probe.get("width", 768),
            "height": probe.get("height", 1344),
            "is_recommended": is_rec,
            "variant_num": variant_num,
            "video_url": f"/api/adz/media/{f.name}",
            "thumbnail_url": f"/api/adz/thumbnail/{f.name}",
            "modified_time": int(f.stat().st_mtime)
        })

    # Sort so recommended / built-in come first, then others
    results.sort(key=lambda x: (
        0 if x["is_recommended"] else 1,
        x["variant_num"] if x["variant_num"] is not None else 99,
        x["filename"]
    ))
    return results


def resolve_ad_video(ad_ref: Union[str, int, None]) -> Optional[Path]:
    """Resolves an ad reference (integer variant, filename, or stem) to an actual video file path."""
    if ad_ref is None:
        return None

    adz_dir = get_adz_dir()
    ref_str = str(ad_ref).strip()

    # 1. Check exact filename in Adz-Video
    cand = adz_dir / ref_str
    if cand.is_file():
        return cand

    # 2. Check if ref is a variant number e.g. "1" or 1 -> ad_outro_1.mp4
    if ref_str.isdigit():
        num = int(ref_str)
        by_num = adz_dir / f"ad_outro_{num}.mp4"
        if by_num.is_file():
            return by_num
        # Check by index in listed videos
        vids = list_ad_videos()
        if 1 <= num <= len(vids):
            by_idx = adz_dir / vids[num - 1]["filename"]
            if by_idx.is_file():
                return by_idx

    # 3. Check with .mp4 appended
    cand_mp4 = adz_dir / f"{ref_str}.mp4"
    if cand_mp4.is_file():
        return cand_mp4

    # 4. Fallback to shared_assets directory in BHSR
    if FALLBACK_SHARED_DIR.exists():
        shared_cand = FALLBACK_SHARED_DIR / ref_str
        if shared_cand.is_file():
            return shared_cand
        if ref_str.isdigit():
            shared_num = FALLBACK_SHARED_DIR / f"ad_outro_{ref_str}.mp4"
            if shared_num.is_file():
                return shared_num

    return None


def delete_ad_video(filename: str) -> bool:
    """Deletes an advertisement video file from Adz-Video directory."""
    safe_name = Path(filename).name
    target = get_adz_dir() / safe_name
    if not target.exists() or not target.is_file():
        return False
    try:
        target.unlink()
        meta = load_metadata()
        if safe_name in meta:
            del meta[safe_name]
            save_metadata(meta)
        thumb = get_adz_dir() / ".thumbnails" / f"{target.stem}_thumb.jpg"
        if thumb.exists():
            try: thumb.unlink()
            except Exception: pass
        return True
    except Exception as e:
        logger.error(f"Failed to delete ad video {safe_name}: {e}")
        return False


def get_or_create_thumbnail(filename: str) -> Optional[Path]:
    """Generates and caches a preview thumbnail frame for an ad video."""
    safe_name = Path(filename).name
    video_p = get_adz_dir() / safe_name
    if not video_p.exists():
        video_p = resolve_ad_video(safe_name)
    if not video_p or not video_p.is_file():
        return None

    thumb_dir = get_adz_dir() / ".thumbnails"
    thumb_dir.mkdir(parents=True, exist_ok=True)
    thumb_file = thumb_dir / f"{video_p.stem}_thumb.jpg"

    if thumb_file.exists() and thumb_file.stat().st_size > 1000:
        if thumb_file.stat().st_mtime >= video_p.stat().st_mtime:
            return thumb_file

    ffmpeg = shutil.which("ffmpeg") or "ffmpeg"
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", "00:00:01.000",
        "-i", str(video_p),
        "-vframes", "1",
        "-q:v", "2",
        str(thumb_file)
    ]
    cf = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0
    try:
        subprocess.run(cmd, timeout=5, creationflags=cf)
        if thumb_file.exists() and thumb_file.stat().st_size > 500:
            return thumb_file
    except Exception as e:
        logger.warning(f"Failed to extract ad thumbnail frame for {filename}: {e}")
    return None
