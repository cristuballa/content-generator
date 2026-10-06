"""Thumbnail image preparation shared by the platform uploaders."""
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple

YOUTUBE_MAX_BYTES = 2 * 1024 * 1024   # YouTube rejects custom thumbnails over 2 MB
META_MAX_BYTES = 8 * 1024 * 1024      # Instagram's cover limit (Facebook accepts larger)


def jpeg_copy(src: Optional[Path], max_bytes: int, max_side: int = 1920) -> Tuple[Optional[Path], bool]:
    """(JPEG path within max_bytes, is_temp_copy), or (None, False) when there is no usable image.
    A JPEG already small enough is used as is; anything else becomes a temporary JPEG (quality, then size, reduced
    until it fits)."""
    if not src:
        return None, False
    src = Path(src)
    if not src.is_file():
        return None, False
    if src.suffix.lower() in (".jpg", ".jpeg") and src.stat().st_size <= max_bytes:
        return src, False
    try:
        from PIL import Image
        with Image.open(src) as im:
            img = im.convert("RGB")
        img.thumbnail((max_side, max_side))
        out = Path(tempfile.gettempdir()) / f"kct_thumb_{os.getpid()}_{int(time.time() * 1000)}.jpg"
        for quality in (90, 85, 80, 70, 60):
            img.save(out, "JPEG", quality=quality)
            if out.stat().st_size <= max_bytes:
                return out, True
        while out.stat().st_size > max_bytes and min(img.size) > 360:
            img = img.resize((int(img.width * 0.8), int(img.height * 0.8)))
            img.save(out, "JPEG", quality=70)
        return out, True
    except Exception as e:
        logging.warning(f"[Thumbnails] {src.name} could not be prepared as a JPEG: {e}")
        return None, False
