"""
=============================================================================
BIBLE HIDDEN SECRETS REVEALED — MASTER STORY GENERATOR (generate_story.py)
=============================================================================
Master multi-slide 9:16 social story production engine for Instagram Stories,
Facebook Stories, and YouTube Shorts/Stories.

Benchmark Architecture (mirrors generate_reel.py):
  1. CLI & Calling Flexibility:
     - --week (-w): Target week identifier (e.g. 1, W01)
     - --story (-s): Target story index (1 to 5)
     - --episode (-e) / --global-story (-g): Global story index (1 to 780)
     - --all (-a): Process all 5 daily stories for the week
     - --force-rebuild: Force rebuild even if final MP4 exists
     - --thumbnail-only / --thumb-only: Quick mode: regenerate 5 modern slide images
       and thumbnail.png in seconds without re-rendering video
     - --slides-only: Render slide PNGs without video muxing
     - --duration: Per-slide display duration in seconds (default: 3.5s)
     - --audio: Path to custom background soundtrack or stem
  2. Auto-Discovery & Resilient Scaffolding:
     - Resolves story folders dynamically (01_..., 1_..., story_01...)
     - Auto-scaffolds story_script.md & metadata.json if missing from curriculum
     - Intelligently pairs thematic artwork from matching reels and long_form
  3. Visual Standards:
     - Full-bleed unblurred FLUX artwork with cinematic grade (+22% contrast, +28% color)
     - Nothing in the top 14% / bottom 20%: Instagram & Facebook cover them with their own
       progress bar, profile name and reply bar
     - One dark title panel in the middle band: channel seal + red badge, two-tone headline
       (White + Electric Yellow), subtitle and scripture pill
     - Automatic Unicode font switching for Hebrew glyphs (no broken boxes)
     - Honest CTAs only ("Reply YES or NO", "Full documentary on our page"): the API can't add
       real poll/link stickers, and each Story is one video, so "tap for next part" would skip it
  4. Heartbeat & FFmpeg Audio Mastering:
     - ProgressHeartbeat for background liveness
     - Silent audio track by default (no music); optional licensed --audio track with 1.5s fade-out
=============================================================================
"""

import os
import sys
import re
import json
import time
import math
import shutil
import threading
import argparse
import subprocess
from pathlib import Path
from typing import Any, Optional, Dict, List, Union
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# =============================================================================
# ENVIRONMENT & PATH AUTO-DISCOVERY
# =============================================================================
PROJECT_DIR = Path(r"C:\Projects\BHSR") if Path(r"C:\Projects\BHSR").exists() else Path(__file__).resolve().parent
if PROJECT_DIR.name == "scripts":
    PROJECT_DIR = PROJECT_DIR.parent

BHSR_ROOT = PROJECT_DIR

WIDTH = 1080
HEIGHT = 1920
DEFAULT_SLIDE_DURATION = 3.5

# ---- Brand Palette -----------------------------------------------------------
WHITE          = (255, 255, 255)
YELLOW         = (255, 225, 0)
GOLD           = (212, 175, 55)
BLACK          = (0, 0, 0)
RED_FILL       = (220, 20, 20, 245)
RED_OUTLINE    = (255, 90, 90, 255)
DARK_PILL_FILL = (0, 0, 0, 180)
PANEL_FILL     = (8, 10, 16, 178)

# ---- Story safe zones (1080x1920) --------------------------------------------
SAFE_TOP       = int(HEIGHT * 0.14)   # Instagram/Facebook progress bar, profile name, close button
SAFE_BOTTOM    = int(HEIGHT * 0.80)   # reply bar ("Send message") and share buttons
PANEL_CENTER_Y = int(HEIGHT * 0.42)   # title panel sits in the middle band, above the artwork's subject
BRAND_TEXT     = "BIBLE HIDDEN SECRETS REVEALED"

# Logo locations
LOGO_CANDIDATES = [
    Path(r"C:\Projects\Bible Hidden Secrets Revealed\shared_assets\transparent_logo.png"),
    PROJECT_DIR / "shared_assets" / "transparent_logo.png",
    PROJECT_DIR / "reel_output" / "transparent_logo.png",
    Path(__file__).resolve().parent / "transparent_logo.png"
]

def find_logo():
    for p in LOGO_CANDIDATES:
        if p.exists():
            return str(p)
    return None

def find_ffmpeg():
    bin_p = shutil.which("ffmpeg")
    if bin_p:
        return bin_p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    fallback_paths = [
        Path(r"C:\Users\User\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe"),
        Path(r"C:\Users\User\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg.exe"),
        Path(r"C:\Program Files\ffmpeg\bin\ffmpeg.exe")
    ]
    for fp in fallback_paths:
        if fp.exists():
            return str(fp)
    return "ffmpeg"

# =============================================================================
# PERIODIC PROGRESS HEARTBEAT (EVERY 60 SECONDS)
# =============================================================================
class ProgressHeartbeat:
    """Emits an unbuffered progress heartbeat every N seconds during long tasks."""
    def __init__(self, task_name: str, interval_sec: int = 60):
        self.task_name = task_name
        self.interval_sec = interval_sec
        self.stop_event = threading.Event()
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._heartbeat_loop, daemon=True)

    def _heartbeat_loop(self):
        while not self.stop_event.wait(self.interval_sec):
            elapsed = int(time.time() - self.start_time)
            mins = elapsed // 60
            secs = elapsed % 60
            elapsed_str = f"{mins}m {secs:02d}s" if mins > 0 else f"{secs}s"
            print(f"[{self.task_name} Progress Heartbeat] Working... ({elapsed_str} elapsed)", flush=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop_event.set()
        elapsed = round(time.time() - self.start_time, 1)
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        dur_str = f"{mins}m {secs:02d}s" if mins > 0 else f"{elapsed:.1f}s"
        print(f"[{self.task_name} Complete] Completed in {dur_str}.", flush=True)

# =============================================================================
# FONTS & HEBREW / UNICODE SUPPORT
# =============================================================================
def has_hebrew(text: str) -> bool:
    return any('\u0590' <= ch <= '\u05ff' for ch in text)

def find_font(size: int, bold: bool = True, text: str = ""):
    if text and has_hebrew(text):
        cand = "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"
        if os.path.exists(cand):
            try:
                return ImageFont.truetype(cand, size)
            except Exception:
                pass
    font_candidates = [
        "C:/Windows/Fonts/impact.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf" if bold else "C:/Windows/Fonts/calibri.ttf",
    ]
    for cand in font_candidates:
        if os.path.exists(cand):
            try:
                return ImageFont.truetype(cand, size)
            except Exception:
                pass
    return ImageFont.load_default()

def fit_font(draw, text, max_w, max_size, min_size=32):
    size = max_size
    font = find_font(size, bold=True, text=text)
    while draw.textlength(text, font=font) > max_w and size > min_size:
        size -= 4
        font = find_font(size, bold=True, text=text)
    return font

def wrap_text(text: str, font, max_width: int, draw: ImageDraw.Draw) -> list:
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = " ".join(current_line + [word])
        w = draw.textlength(test_line, font=font)
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines

def split_story_title(title: str) -> tuple[str, str]:
    """Splits a title cleanly into Line 1 (White) and Line 2 (Yellow)."""
    # "Theology Check: Who created the universe?" splits at the colon (verse colons like 1:1 don't count)
    lead = re.match(r'^(.*?\D):(?!\d)\s*(.+)$', title.strip())
    if lead and len(lead.group(1).split()) <= 5:
        return lead.group(1).upper() + ":", lead.group(2).upper()
    clean = re.sub(r'(?<!\d):(?!\d)|\?', '', title).strip()
    words = clean.split()
    if len(words) <= 2:
        return words[0].upper(), (words[1].upper() if len(words) > 1 else "")
    
    split_markers = ["IN", "BEFORE", "OF", "THE", "INTO", "FOR", "VS", "OVER"]
    split_idx = -1
    for m in split_markers:
        for i, w in enumerate(words):
            if w.upper() == m and i >= 2:
                split_idx = i
                break
        if split_idx != -1:
            break
            
    if split_idx == -1:
        split_idx = max(2, len(words) // 2)
        
    l1 = " ".join(words[:split_idx]).upper()
    l2 = " ".join(words[split_idx:]).upper()
    if "?" in title:
        l2 += "?"
    return l1, l2

def create_story_scrim(W, H):
    """Light top/bottom shading so the apps' own white UI (progress bar, profile name, reply bar) stays legible."""
    column = Image.new("L", (1, 64), 0)
    for y in range(64):
        top = max(0.0, 1.0 - y / 10.0) * 150          # first ~16% of the frame
        bottom = max(0.0, (y - 50) / 14.0) * 170       # last ~22% of the frame
        column.putpixel((0, y), int(max(top, bottom)))
    overlay = Image.new("RGBA", (W, H), (6, 8, 14, 0))
    overlay.putalpha(column.resize((W, H), Image.Resampling.BICUBIC))
    return overlay

def clean_story_cta(text: str) -> str:
    """'Tap below to watch the full premiere!' -> 'Watch the full premiere!' (nothing on a Story is tappable)."""
    clean = re.sub(r'^\s*(?:tap|swipe|click)\s+(?:below|up|here|the link)?\s*to\s+', '', text or "", flags=re.IGNORECASE)
    return clean[:1].upper() + clean[1:] if clean else clean

def clean_story_title(title: str) -> str:
    """Drops internal production labels: 'What Happened Before Genesis? Teaser & Countdown' -> 'What Happened Before Genesis?'"""
    clean = re.sub(r'\s*\((?:day|part)\s*\d+\)\s*', ' ', title or "", flags=re.IGNORECASE)
    clean = re.sub(r'\s*[-–—:]?\s*(?:teaser\s*&\s*(?:mystery\s*)?countdown|study notes|community poll|scripture challenge)\b.*$', '', clean, flags=re.IGNORECASE)
    if "?" in clean:
        clean = clean[:clean.index("?") + 1]
    return clean.strip()

def story_subtitle(metadata: dict, title: str) -> str:
    """Subtitle under the hook: the week's curriculum theme (after its question), else the cleaned story title."""
    theme = metadata.get("curriculum") or metadata.get("curriculum_theme") or metadata.get("theme") or ""
    if theme and "?" in theme:
        theme = theme.split("?", 1)[1].strip()
    return (theme or clean_story_title(title)).strip()

HEBREW_RUN_RE = re.compile(r"[֐-׿]+(?:\s+[֐-׿]+)*")

def visual_order(text: str) -> str:
    """PIL without libraqm draws characters left-to-right, so Hebrew came out reversed: flip each Hebrew run.
    Vowel points are dropped because without libraqm they land beside their letters instead of on them."""
    def flip(m):
        letters = re.sub(r"[֑-ֽֿ-ׇ]", "", m.group(0))
        return letters[::-1]
    return HEBREW_RUN_RE.sub(flip, text)

def draw_shadowed_text(draw, x, y, text, font, fill=WHITE, shadow_fill=BLACK, r=4):
    if has_hebrew(text):
        text = visual_order(text)
    for ox in range(-r, r + 1):
        for oy in range(-r, r + 1):
            if abs(ox) + abs(oy) >= r - 1:
                draw.text((x + ox, y + oy), text, font=font, fill=shadow_fill)
    draw.text((x, y), text, font=font, fill=fill)

# =============================================================================
# AUTO-SCAFFOLDING & PARSING
# =============================================================================
def parse_story_script(md_path: Path):
    """Parses story_script.md into structured slide objects."""
    if not md_path.exists():
        return []
    
    text = md_path.read_text(encoding="utf-8", errors="replace")
    slides = []
    
    chunks = re.split(r'###\s*Slide\s*(\d+)', text, flags=re.IGNORECASE)
    if len(chunks) > 1:
        for idx in range(1, len(chunks), 2):
            slide_num = int(chunks[idx])
            content = chunks[idx + 1]
            
            vis_m = re.search(r'-\s*\*\*Visual:\*\*\s*(.*)', content, re.IGNORECASE)
            text_m = re.search(r'-\s*\*\*On-Screen Text:\*\*\s*(.*)', content, re.IGNORECASE)
            sticker_m = re.search(r'-\s*\*\*Interactive Sticker:\*\*\s*(.*)', content, re.IGNORECASE)
            
            visual = vis_m.group(1).strip() if vis_m else ""
            on_screen = text_m.group(1).strip() if text_m else ""
            sticker = sticker_m.group(1).strip() if sticker_m else ""
            
            if not on_screen and content.strip():
                lines = [l.strip().lstrip("-* ") for l in content.strip().splitlines() if l.strip()]
                on_screen = lines[0] if lines else f"Slide {slide_num}"
                
            slides.append({
                "slide_num": slide_num,
                "visual": visual,
                "text": on_screen,
                "sticker": sticker
            })
    return slides[:5]

def scaffold_story_if_missing(story_dir: Path, week_num: int, story_num: int):
    """Auto-scaffolds story_script.md & metadata.json if missing."""
    script_p = story_dir / "story_script.md"
    meta_p = story_dir / "metadata.json"
    
    if script_p.exists() and meta_p.exists():
        return

    # Try reading curriculum from week folder
    week_dir = story_dir.parent.parent
    curr_file = week_dir / "curriculum_metadata.json"
    curr_data = {}
    if curr_file.exists():
        try:
            curr_data = json.loads(curr_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    title = curr_data.get("story_titles", [None] * 5)[story_num - 1] if story_num <= len(curr_data.get("story_titles", [])) else None
    if not title:
        default_titles = [
            f"Week {week_num:02d} Teaser & Mystery Countdown",
            f"Ancient Hebrew Breakdown (Day 2)",
            f"Theological Deep Dive & Study Notes (Day 3)",
            f"Scripture Challenge & Community Poll (Day 4)",
            f"Cinematic Vision & Flagship Premiere (Day 5)"
        ]
        title = default_titles[story_num - 1] if story_num <= len(default_titles) else f"Week {week_num:02d} Story {story_num}"

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    day_name = days[(story_num - 1) % 5]

    if not meta_p.exists():
        meta = {
            "story_id": f"W{week_num:02d}-S{story_num:02d}",
            "week": week_num,
            "story_num": story_num,
            "day": day_name,
            "title": title,
            "reference": curr_data.get("key_scriptures", "Genesis 1:1, Job 38:4-7"),
            "sound_suggestion": "Cinematic ambient pads / orchestral strings",
            "aspect_ratio": "9:16",
            "resolution": "1080x1920",
            "total_slides": 5
        }
        meta_p.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        print(f"  [Auto-Scaffold] Generated metadata.json -> {meta_p.name}")

    if not script_p.exists():
        lines = [
            f"# Story {story_num}: {title}",
            f"**Week:** W{week_num:02d} | **Day:** {day_name}",
            "",
            "## Slide Breakdown",
            "",
            "### Slide 1",
            "- **Visual:** Dramatic cinematic biblical revelation",
            f"- **On-Screen Text:** What hidden secret exists in Week {week_num:02d}?",
            "",
            "### Slide 2",
            "- **Visual:** Ancient manuscripts and divine council",
            "- **On-Screen Text:** Scripture reveals eternal mysteries framed before creation.",
            "",
            "### Slide 3",
            "- **Visual:** Heavenly host and cosmic light",
            "- **On-Screen Text:** Look closely at what the prophets saw.",
            "",
            "### Slide 4",
            "- **Visual:** Blinding heavenly vision",
            "- **On-Screen Text:** COMMUNITY POLL: Did you know this was in your Bible?",
            "- **Interactive Sticker:** poll: YES vs NO",
            "",
            "### Slide 5",
            "- **Visual:** Master episode thumbnail banner",
            "- **On-Screen Text:** Watch the full documentary premiere on our page!",
            "- **Interactive Sticker:** link",
            ""
        ]
        script_p.write_text("\n".join(lines), encoding="utf-8")
        print(f"  [Auto-Scaffold] Generated story_script.md -> {script_p.name}")

# =============================================================================
# SLIDE IMAGE RENDER ENGINE
# =============================================================================
def render_slide_image(slide: dict, total_slides: int, metadata: dict, week_tag: str, bg_image_path: Path = None) -> Image.Image:
    """Renders a single 1080x1920 Instagram/Facebook story frame in the modern, clean viral style."""
    slide_num = slide["slide_num"]
    on_screen_text = slide["text"]
    sticker = slide.get("sticker", "")
    title = metadata.get("title", f"Story {slide_num}")
    reference = metadata.get("reference", "")

    # 1. Base Image Load & Cover Crop
    if bg_image_path and bg_image_path.exists():
        try:
            art = Image.open(bg_image_path).convert("RGBA")
            bw, bh = art.size
            target_aspect = WIDTH / HEIGHT
            current_aspect = bw / bh
            if current_aspect > target_aspect:
                new_h = HEIGHT
                new_w = int(bw * HEIGHT / bh)
            else:
                new_w = WIDTH
                new_h = int(bh * WIDTH / bw)
            art = art.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - WIDTH) // 2
            top = (new_h - HEIGHT) // 2
            base = art.crop((left, top, left + WIDTH, top + HEIGHT))
            
            # Vivid cinematic pop (zero blur!)
            base = ImageEnhance.Contrast(base).enhance(1.22)
            base = ImageEnhance.Color(base).enhance(1.28)
        except Exception:
            base = Image.new("RGBA", (WIDTH, HEIGHT), (12, 16, 26, 255))
    else:
        base = Image.new("RGBA", (WIDTH, HEIGHT), (12, 16, 26, 255))

    is_hook = (slide_num == 1)
    canvas = Image.alpha_composite(base, create_story_scrim(WIDTH, HEIGHT))
    draw = ImageDraw.Draw(canvas, "RGBA")

    # 2. Content: everything sits in one dark panel in the middle band (see SAFE_TOP / SAFE_BOTTOM).
    #    Instagram & Facebook draw their own progress bar, profile name and reply bar, so nothing is drawn there.
    margin, pad, gap = 48, 40, 24
    inner_x = margin + pad
    inner_w = WIDTH - 2 * (margin + pad)
    on_screen_text = clean_story_cta(on_screen_text)
    is_poll = "poll" in sticker.lower() or "yes" in sticker.lower()
    is_last = slide_num == total_slides or "link" in sticker.lower()
    if is_poll:
        on_screen_text = re.sub(r'^(?:community\s+)?poll\s*:\s*', '', on_screen_text, flags=re.IGNORECASE)

    ops = []  # (height, shapes(layer_draw, y), text(canvas, draw, y)) stacked top-down inside the panel

    # Header row: channel seal + red badge
    badge_font = find_font(52, bold=True)
    badge_text = "THE SECRET BIBLE CODE" if is_hook else f"PART {slide_num} OF {total_slides}"
    badge_w = int(draw.textlength(badge_text, font=badge_font)) + 48
    logo = None
    logo_file = find_logo()
    if logo_file:
        try:
            logo = Image.open(logo_file).convert("RGBA").resize((100, 100), Image.Resampling.LANCZOS)
        except Exception:
            logo = None
    badge_x = inner_x + (118 if logo else 0)

    def header_shapes(ld, y):
        ld.rounded_rectangle([badge_x, y + 12, badge_x + badge_w, y + 88], radius=18, fill=RED_FILL, outline=RED_OUTLINE, width=2)

    def header_text(cv, dr, y):
        if logo:
            cv.paste(logo, (inner_x, y), logo)
        dr.text((badge_x + 24, y + 22), badge_text, font=badge_font, fill=WHITE)

    ops.append((100, header_shapes, header_text))

    def text_lines(lines, font, fill, line_h, r=3):
        def _draw(cv, dr, y):
            for i, line in enumerate(lines):
                draw_shadowed_text(dr, inner_x, y + i * line_h, line, font, fill=fill, r=r)
        return (line_h * len(lines), None, _draw)

    def fitted_lines(text, max_size, min_size):
        font = fit_font(draw, text, inner_w, max_size, min_size=min_size)
        return wrap_text(text, font, inner_w, draw), font

    if is_hook:
        # Hook: the slide's own question as a two-tone headline, the curriculum line as subtitle
        line1, line2 = split_story_title(on_screen_text or clean_story_title(title))
        l1, f1 = fitted_lines(line1, 100, 60)
        ops.append(text_lines(l1, f1, WHITE, int(f1.size * 1.08), r=5))
        if line2:
            l2, f2 = fitted_lines(line2, 100, 60)
            ops.append(text_lines(l2, f2, YELLOW, int(f2.size * 1.08), r=5))
        subtitle = story_subtitle(metadata, title).upper()
        if subtitle:
            sub_font = find_font(46, bold=True)
            ops.append(text_lines(wrap_text(subtitle, sub_font, inner_w, draw)[:2], sub_font, (240, 240, 240), 58))
    else:
        kicker_text = (
            "COMMUNITY POLL" if is_poll else
            "THE FINALE" if is_last else
            "THE ANCIENT SCRIPTURES REVEAL" if slide_num == 2 else
            "THE DEEP REVELATION" if slide_num == 3 else
            "THE HIDDEN DETAIL"
        )
        kicker_font = find_font(52, bold=True)
        ops.append(text_lines([kicker_text], kicker_font, YELLOW, 66))

        # Headline + body, split at a natural break: a short lead before ':', else the first sentence,
        # else the whole slide as the headline when it fits in 3 lines
        words = on_screen_text.split()
        parts = on_screen_text.split(":")
        sentences = re.split(r'(?<=[.!?])\s+', on_screen_text.strip())
        whole_font = find_font(64, bold=True, text=on_screen_text)
        verse_quote = re.match(r"^((?:[1-3]\s?)?[A-Za-z]+\.?\s+\d+:\d+(?:-\d+)?)\s*:\s*(.+)$", on_screen_text.strip())
        if verse_quote:
            # "Colossians 1:16: 'For by Him all things...'" -> reference headline, quote as body
            h_text, body_text = verse_quote.group(1), verse_quote.group(2)
        elif len(parts) > 1 and len(parts[0].split()) <= 6 and not re.search(r'\d$', parts[0]):
            h_text, body_text = parts[0].strip(), ":".join(parts[1:]).strip()
        elif len(sentences) > 1 and len(sentences[0].split()) <= 10:
            h_text, body_text = sentences[0], " ".join(sentences[1:])
        elif len(wrap_text(on_screen_text.upper(), whole_font, inner_w, draw)) <= 3:
            h_text, body_text = on_screen_text, ""
        else:
            split_p = min(6, len(words) // 2)
            h_text, body_text = " ".join(words[:split_p]), " ".join(words[split_p:]).strip()
        h_text = h_text.upper()
        # Largest headline size that still wraps into at most 3 lines
        for size in (80, 74, 68, 62, 56):
            h_font = find_font(size, bold=True, text=h_text)
            h_lines = wrap_text(h_text, h_font, inner_w, draw)
            if len(h_lines) <= 3:
                break
        ops.append(text_lines(h_lines[:3], h_font, WHITE, int(h_font.size * 1.12), r=4))
        ops.append((4, lambda ld, y: ld.line([(inner_x, y), (inner_x + 160, y)], fill=YELLOW + (220,), width=4), None))
        if body_text:
            body_font = find_font(52, bold=True, text=body_text)
            ops.append(text_lines(wrap_text(body_text, body_font, inner_w, draw)[:5], body_font, WHITE, 68))

    # Scripture pill
    if reference:
        sc_font = find_font(50, bold=True)
        first_ref = reference.split(",")[0].strip().upper()
        sc_w = int(draw.textlength(first_ref, font=sc_font)) + 44

        def pill_shapes(ld, y):
            ld.rounded_rectangle([inner_x, y, inner_x + sc_w, y + 76], radius=16, fill=DARK_PILL_FILL, outline=YELLOW + (200,), width=2)

        def pill_text(cv, dr, y):
            dr.text((inner_x + 22, y + 11), first_ref, font=sc_font, fill=YELLOW)

        ops.append((76, pill_shapes, pill_text))

    # CTA under the panel. Each Story is one video, so tapping only skips ahead: no "tap for next part" and
    # no fake poll/link stickers (the API can't add real ones). Replies are the Story's real interaction.
    final_cta = (metadata.get("final_cta") or "FULL DOCUMENTARY ON OUR PAGE").upper()
    cta_text = "REPLY YES OR NO" if is_poll else (final_cta if is_last else "")
    cta_font = find_font(50, bold=True)
    cta_h = 116 if cta_text else 0

    # 3. Layout: centre the panel on PANEL_CENTER_Y, kept inside the safe band together with the CTA
    panel_h = pad * 2 + sum(h for h, _, _ in ops) + gap * (len(ops) - 1)
    cta_space = (cta_h + 36) if cta_text else 0
    panel_top = PANEL_CENTER_Y - panel_h // 2
    panel_top = min(panel_top, SAFE_BOTTOM - 24 - cta_space - panel_h)
    panel_top = max(panel_top, SAFE_TOP + 30)
    panel_box = [margin, panel_top, WIDTH - margin, panel_top + panel_h]

    shapes_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ld = ImageDraw.Draw(shapes_layer)
    ld.rounded_rectangle(panel_box, radius=28, fill=PANEL_FILL, outline=(255, 255, 255, 40), width=2)
    positions = []
    y = panel_top + pad
    for h, shapes, _ in ops:
        positions.append(y)
        if shapes:
            shapes(ld, y)
        y += h + gap
    if cta_text:
        cta_w = int(ld.textlength(cta_text, font=cta_font)) + 80
        cta_x = (WIDTH - cta_w) // 2
        cta_y = panel_box[3] + 36
        ld.rounded_rectangle([cta_x, cta_y, cta_x + cta_w, cta_y + cta_h], radius=24, fill=YELLOW + (240,), outline=WHITE + (240,), width=3)
    canvas = Image.alpha_composite(canvas, shapes_layer)

    draw = ImageDraw.Draw(canvas, "RGBA")
    for (h, _, text_fn), y in zip(ops, positions):
        if text_fn:
            text_fn(canvas, draw, y)
    if cta_text:
        draw.text((cta_x + 40, cta_y + (cta_h - cta_font.size) // 2 - 4), cta_text, font=cta_font, fill=(10, 12, 18))

    return canvas.convert("RGB")

# =============================================================================
# THEMATIC ARTWORK RESOLUTION
# =============================================================================
# -----------------------------------------------------------------------------
# Reel folders: W06/reels/<day>_<n>_<name> (mon_1, mon_2, tue_1...). Posting order is day, then n.
# Older numbered folders (01_name, 146_name) take Monday..Friday in number order, one a day.
# Same rules as core/reels.py in KCT Studio and generate_reel.py: keep them in step.
# -----------------------------------------------------------------------------
REEL_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_REEL_DAY_RE = re.compile(r"^(mon|tue|wed|thu|fri|sat|sun)_(\d+)_(.+)$", re.IGNORECASE)
_REEL_NUMBERED_RE = re.compile(r"^(\d+)[_-](.+)$")


def reel_slots(reels_dir: Path) -> list:
    """(folder, day index 0=Mon, place in the day) for a week's reels, in posting order."""
    if not reels_dir or not reels_dir.is_dir():
        return []
    named, numbered, other = [], [], []
    for d in reels_dir.iterdir():
        if not d.is_dir() or d.name.lower() in ("temp", "temp_slides") or d.name.startswith((".", "__")):
            continue
        m = _REEL_DAY_RE.match(d.name)
        n = _REEL_NUMBERED_RE.match(d.name)
        if m:
            named.append((d, REEL_DAYS.index(m.group(1).lower()), int(m.group(2))))
        elif n:
            numbered.append((int(n.group(1)), d))
        else:
            other.append(d)
    for rank, (_, d) in enumerate(sorted(numbered, key=lambda x: (x[0], x[1].name))):
        named.append((d, rank % 7, rank // 7 + 1))
    named.sort(key=lambda x: (x[1], x[2], x[0].name))
    last = (named[-1][1], named[-1][2]) if named else (0, 0)
    return named + [(d, last[0], last[1] + i + 1) for i, d in enumerate(sorted(other, key=lambda d: d.name))]


def find_reel(reels_dir: Path, which):
    """A reel by its key ("tue_2"), folder name, or position in posting order (1 = first)."""
    slots = reel_slots(reels_dir)
    text = str(which).strip().lower()
    for d, day, n in slots:
        if text in (d.name.lower(), f"{REEL_DAYS[day]}_{n}"):
            return d
    if text.isdigit() and 1 <= int(text) <= len(slots):
        return slots[int(text) - 1][0]
    return None


def story_reel(reels_dir: Path, reel: str = None, reel_num: int = None, story_idx: int = None):
    """The reel a story borrows its art from: its "reel" key (tue_1); else an older reel_num, or the story's own
    number, read as that weekday's first reel (2 = Tuesday's), so adding a second reel to a day never shifts it."""
    if reel:
        found = find_reel(reels_dir, reel)
        if found:
            return found
    n = reel_num or story_idx
    if not n:
        return None
    if 1 <= int(n) <= 7:
        found = find_reel(reels_dir, f"{REEL_DAYS[int(n) - 1]}_1")
        if found:
            return found
    return find_reel(reels_dir, n)


def get_story_background_candidates(story_dir: Path, week_dir: Path, story_idx: int, reel_num: int = None,
                                    reel: str = None) -> list:
    """Intelligently pairs each story with thematic artwork from reels or long form.
    The story's "reel" key (or older reel_num) picks the reel to borrow art from; otherwise story N uses day N's reel."""
    candidates = []

    # 1. Matching reel folder for this story
    reels_dir = week_dir / "reels"
    if reels_dir.exists():
        target_reel = story_reel(reels_dir, reel, reel_num, story_idx)
        if target_reel:
            # Earlier reels name their pictures reelNN_*; narration-timed reels name them scene_NNN
            r_imgs = sorted((target_reel / "images").glob("reel*.png")) + sorted((target_reel / "images").glob("scene_*.png"))
            r_imgs = [img for img in r_imgs if "card" not in img.name]
            if (reel or reel_num) and r_imgs:
                # Several stories share a reel's art: start each one at a different image
                shift = (story_idx * 4) % len(r_imgs)
                r_imgs = r_imgs[shift:] + r_imgs[:shift]
            candidates.extend(r_imgs)
            
    # 2. Long form scene images (week root, or one folder per episode)
    lf_dir = week_dir / "long_form"
    if lf_dir.exists():
        candidates.extend(sorted(list((lf_dir / "images").glob("*.png"))))
        candidates.extend(sorted(list(lf_dir.glob("*/images/*.png"))))
        
    # 3. Fallbacks
    cand_defaults = [
        week_dir / "long_form" / "thumbnail_option_1.jpg",
        week_dir / "long_form" / "thumbnail.png"
    ]
    candidates.extend([c for c in cand_defaults if c.exists()])
    return candidates

def count_week_stories(week_dir: Path) -> int:
    """Number of stories in a week: one per story folder, never fewer than the 5 daily stories."""
    stories_dir = week_dir / "stories"
    subdirs = [d for d in stories_dir.iterdir() if d.is_dir() and d.name.lower() not in ("temp", "temp_slides")] if stories_dir.exists() else []
    return max(5, len(subdirs))

def find_story_folder(week_dir: Path, story_ref: Any) -> Path:
    """Finds the folder for a given story index or key within week_dir/stories."""
    stories_dir = week_dir / "stories"
    stories_dir.mkdir(parents=True, exist_ok=True)
    
    subdirs = [d for d in stories_dir.iterdir() if d.is_dir() and d.name.lower() not in ("temp", "temp_slides")]
    if not subdirs:
        new_dir = stories_dir / f"mon_1_story_{story_ref}"
        new_dir.mkdir(parents=True, exist_ok=True)
        return new_dir

    ref_str = str(story_ref).lower().strip()

    # 0. Direct folder name or prefix match (e.g. "mon_1", "mon_1_before_the_first_day")
    for d in subdirs:
        if d.name.lower() == ref_str or d.name.lower().startswith(f"{ref_str}_") or d.name.lower().startswith(f"{ref_str}-"):
            return d

    story_num = int(ref_str) if ref_str.isdigit() else 1

    # 1. Direct numeric prefix match (legacy e.g. 01_..., 1_..., 1-...)
    prefix = f"0{story_num}"
    for d in subdirs:
        if d.name.startswith(prefix) or d.name.startswith(f"{story_num}_") or d.name.startswith(f"{story_num}-"):
            return d

    # 2. Sort by day order and slot (mon_1..mon_3, tue_1..tue_3, etc.)
    day_order = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4}
    def sort_key(d):
        parts = d.name.split('_')
        d_val = day_order.get(parts[0].lower(), 99)
        n_val = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 99
        return (d_val, n_val, d.name)

    sorted_subdirs = sorted(subdirs, key=sort_key)
    if 1 <= story_num <= len(sorted_subdirs):
        return sorted_subdirs[story_num - 1]

    # Create standard folder if completely missing
    days = ["mon", "tue", "wed", "thu", "fri"]
    day = days[(story_num - 1) % 5]
    slot = ((story_num - 1) // 5) + 1
    new_dir = stories_dir / f"{day}_{slot}_story"
    new_dir.mkdir(parents=True, exist_ok=True)
    return new_dir

# =============================================================================
# AD OUTRO MANAGER & PINNED COMMENTS FOR STORIES
# =============================================================================
ADZ_IMAGE_DIR = Path(r"C:\Projects\Adz-Image")
ADZ_DIR = Path(r"C:\Projects\Adz-Video")

AD_PINNED_COMMENTS = {
    # Ads 1, 2, 3: The Watchers & The Word (Desk, Standing, Cover)
    "watchers": (
        '📖 Get "The Watchers & The Word" on Etsy:\n'
        '👉 https://www.etsy.com/nz/listing/4591934547\n\n'
        '✨ Browse All Books & Sacred Art:\n'
        '👉 https://www.etsy.com/shop/BibleHiddenGems'
    ),
    # Ad 4: Hidden Secrets of the Bible
    "hidden_secrets": (
        '📖 Get "Hidden Secrets of the Bible" on Etsy:\n'
        '👉 https://www.etsy.com/nz/listing/4526030482\n\n'
        '✨ Browse All Books & Sacred Art:\n'
        '👉 https://www.etsy.com/shop/BibleHiddenGems'
    ),
    # Ad 5: Bible Hidden Gems - New Testament
    "nt_gems": (
        '📖 Get "Bible Hidden Gems: New Testament" on Etsy:\n'
        '👉 https://www.etsy.com/nz/listing/4536465297\n\n'
        '✨ Browse All Books & Sacred Art:\n'
        '👉 https://www.etsy.com/shop/BibleHiddenGems'
    ),
    # Ad 6: Bible Hidden Gems - Old Testament
    "ot_gems": (
        '📖 Get "Bible Hidden Gems: Old Testament" on Etsy:\n'
        '👉 https://www.etsy.com/nz/listing/4526027051\n\n'
        '✨ Browse All Books & Sacred Art:\n'
        '👉 https://www.etsy.com/shop/BibleHiddenGems'
    ),
    # Ad 7: Merch & Apparel Carousel
    "merch": (
        '✨ Official Biblical Apparel & Sacred Art on Etsy:\n'
        '👉 https://www.etsy.com/shop/BibleHiddenGems\n\n'
        '📖 Browse Bestselling Bible Books:\n'
        '👉 https://www.etsy.com/shop/BibleHiddenGems'
    ),
    # Fallback when custom ad attached
    "default_ad": (
        '📖 Get Our Bestselling Books on Etsy:\n'
        '👉 https://www.etsy.com/shop/BibleHiddenGems\n\n'
        '✨ Browse All Sacred Apparel & Sacred Art:\n'
        '👉 https://www.etsy.com/shop/BibleHiddenGems'
    ),
    # Clean story (no ad attached)
    "clean": (
        '🛒 OFFICIAL MERCH & SACRED BOOKS:\n'
        '✨ Etsy Store (Merch & Art): https://www.etsy.com/shop/BibleHiddenGems\n'
        '📖 Book 1 (Amazon): https://www.amazon.com/dp/B0H9NX1BL2\n'
        '📖 Book 2 (Amazon): https://www.amazon.com/dp/B0H9S491BG\n\n'
        '👉 Subscribe to Bible Hidden Secrets Revealed for new revelations every week!'
    )
}

def generate_pinned_comment_for_ad(ad_source: Any, ad_clip_name: str = None) -> str:
    """Returns a tailored pinned comment based on the attached ad outro (1 to 7)."""
    if not ad_source and not ad_clip_name:
        return AD_PINNED_COMMENTS["clean"]

    ref = str(ad_clip_name or ad_source).lower().strip()
    if "merch" in ref or "fishers" in ref or ref == "7" or ref.endswith("_7.mp4") or "carousel_7" in ref:
        return AD_PINNED_COMMENTS["merch"]
    elif "ot_gems" in ref or ref == "6" or ref.endswith("_6.mp4"):
        return AD_PINNED_COMMENTS["ot_gems"]
    elif "nt_gems" in ref or ref == "5" or ref.endswith("_5.mp4"):
        return AD_PINNED_COMMENTS["nt_gems"]
    elif "hidden_secrets" in ref or ref == "4" or ref.endswith("_4.mp4"):
        return AD_PINNED_COMMENTS["hidden_secrets"]
    elif "watchers" in ref or ref in ["1", "2", "3"] or any(ref.endswith(f"_{x}.mp4") for x in ["1", "2", "3"]):
        return AD_PINNED_COMMENTS["watchers"]
    else:
        return AD_PINNED_COMMENTS["default_ad"]

def resolve_ad_asset(ad_source: Any) -> Path:
    """Resolves an ad outro reference into an image (C:\\Projects\\Adz-Image) or video (C:\\Projects\\Adz-Video)."""
    ref_str = str(ad_source).strip()

    # 1. Primary check: C:\Projects\Adz-Image (images for stories)
    if ADZ_IMAGE_DIR.exists():
        direct_img = ADZ_IMAGE_DIR / ref_str
        if direct_img.is_file():
            return direct_img
        cand_png = ADZ_IMAGE_DIR / f"{ref_str}.png"
        if cand_png.is_file():
            return cand_png
        cand_jpg = ADZ_IMAGE_DIR / f"{ref_str}.jpg"
        if cand_jpg.is_file():
            return cand_jpg
        if ref_str.isdigit():
            img_files = sorted([f for f in ADZ_IMAGE_DIR.iterdir() if f.is_file() and f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp')])
            num = int(ref_str)
            if 1 <= num <= len(img_files):
                return img_files[num - 1]
        stem_matches = list(ADZ_IMAGE_DIR.glob(f"*{ref_str}*.png")) or list(ADZ_IMAGE_DIR.glob(f"*{ref_str}*.*"))
        if stem_matches:
            return stem_matches[0]

    # 2. Secondary check: C:\Projects\Adz-Video
    if ADZ_DIR.exists():
        direct_vid = ADZ_DIR / ref_str
        if direct_vid.is_file():
            return direct_vid
        cand_mp4 = ADZ_DIR / f"{ref_str}.mp4"
        if cand_mp4.is_file():
            return cand_mp4
        if ref_str.isdigit():
            cand_num = ADZ_DIR / f"ad_outro_{ref_str}.mp4"
            if cand_num.is_file():
                return cand_num
            num_matches = list(ADZ_DIR.glob(f"*_{ref_str}.mp4"))
            if num_matches:
                return num_matches[0]
        stem_matches = list(ADZ_DIR.glob(f"*{ref_str}*.mp4"))
        if stem_matches:
            return stem_matches[0]

    # 3. Check shared_assets in PROJECT_DIR
    shared_dir = PROJECT_DIR / "shared_assets"
    if shared_dir.exists():
        shared_file = shared_dir / ref_str
        if shared_file.is_file():
            return shared_file
        shared_png = shared_dir / f"{ref_str}.png"
        if shared_png.is_file():
            return shared_png
        shared_mp4 = shared_dir / f"{ref_str}.mp4"
        if shared_mp4.is_file():
            return shared_mp4
        stem_matches = list(shared_dir.glob(f"*{ref_str}*.*"))
        if stem_matches:
            return stem_matches[0]

    raise FileNotFoundError(f"Could not find advertisement asset for '{ad_source}' in {ADZ_IMAGE_DIR} or {ADZ_DIR}")

def combine_story_with_ad(story_dir: Path, ad_source: Any, out_mp4: Path) -> Path:
    """Combines a base story video and an ad image from C:\\Projects\\Adz-Image (or video) via ffmpeg."""
    clean_vid = story_dir / f"{story_dir.name}_clean.mp4"
    base_vid = clean_vid if clean_vid.exists() else out_mp4
    if not base_vid.exists():
        cands = [p for p in story_dir.glob("*.mp4") if "clean" not in p.name.lower() and "temp" not in p.name.lower()]
        if cands:
            base_vid = cands[0]
    if not base_vid.exists():
        raise FileNotFoundError(f"Base story video not found in {story_dir.name}")

    if not clean_vid.exists():
        shutil.copy2(base_vid, clean_vid)

    ad_asset_path = resolve_ad_asset(ad_source)
    is_image = ad_asset_path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
    temp_target = story_dir / f"temp_comb_{out_mp4.name}"
    temp_slides_dir = story_dir / "temp_slides"
    temp_slides_dir.mkdir(parents=True, exist_ok=True)

    if is_image:
        print(f"[Combine] Attaching ad image from C:\\Projects\\Adz-Image: {ad_asset_path.name}...", flush=True)
        # 1. Copy ad image into story folder as slide_ad.png
        try: shutil.copy2(ad_asset_path, story_dir / "slide_ad.png")
        except Exception: pass

        # 2. Render 3.5s video slide from the image
        temp_ad_vid = temp_slides_dir / f"ad_slide_{ad_asset_path.stem}.mp4"
        cmd_img = [
            find_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
            "-loop", "1", "-i", str(ad_asset_path),
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", "3.5",
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(temp_ad_vid)
        ]
        subprocess.run(cmd_img, check=True)

        # 3. Concat demux clean story video + ad slide video
        concat_cmd = [
            find_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(clean_vid),
            "-i", str(temp_ad_vid),
            "-filter_complex", "[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(temp_target)
        ]
        subprocess.run(concat_cmd, check=True)
    else:
        print(f"[Combine] Attaching ad video from C:\\Projects\\Adz-Video: {ad_asset_path.name}...", flush=True)
        filter_complex = (
            "[1:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v1];"
            "[0:v][0:a][v1][1:a]concat=n=2:v=1:a=1[v][a]"
        )
        cmd = [
            find_ffmpeg(), "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(clean_vid),
            "-i", str(ad_asset_path),
            "-filter_complex", filter_complex,
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(temp_target)
        ]
        subprocess.run(cmd, check=True)

    if out_mp4.exists():
        try: os.remove(str(out_mp4))
        except Exception: pass
    shutil.move(str(temp_target), str(out_mp4))

    with_ads_p = story_dir / f"{story_dir.name}_with_ads.mp4"
    try: shutil.copy2(out_mp4, with_ads_p)
    except Exception: pass

    meta_p = story_dir / "metadata.json"
    if meta_p.exists():
        try:
            m_data = json.loads(meta_p.read_text(encoding="utf-8"))
            ad_comment = generate_pinned_comment_for_ad(ad_source, ad_asset_path.name)
            m_data["ad_outro"] = {
                "attached": True,
                "type": "image" if is_image else "video",
                "filename": ad_asset_path.name,
                "title": f"Ad: {ad_asset_path.stem.replace('_', ' ').title()}",
                "source_dir": str(ADZ_IMAGE_DIR if is_image else ADZ_DIR),
                "attached_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "pinned_comment": ad_comment
            }
            m_data["pinned_comment"] = ad_comment
            meta_p.write_text(json.dumps(m_data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[Metadata] Pinned comment updated to match attached ad: {ad_asset_path.name}", flush=True)
        except Exception as ex:
            print(f"[Metadata Warning] Could not update metadata.json: {ex}", flush=True)

    size_mb = out_mp4.stat().st_size / (1024 * 1024)
    print(f"[SUCCESS] Fast ad combine completed: {out_mp4.name} ({size_mb:.1f} MB)", flush=True)
    return out_mp4

def remove_ad_from_story(story_dir: Path, out_mp4: Path) -> Path:
    """Removes attached ad outro from story video and restores clean version."""
    clean_vid = story_dir / f"{story_dir.name}_clean.mp4"
    if not clean_vid.exists():
        print(f"[Notice] Clean video {clean_vid.name} not found; checking existing video...", flush=True)
        clean_vid = out_mp4
    else:
        if out_mp4.exists():
            try: os.remove(str(out_mp4))
            except Exception: pass
        shutil.copy2(clean_vid, out_mp4)
        print(f"[SUCCESS] Restored clean story video from {clean_vid.name}", flush=True)

    with_ads_p = story_dir / f"{story_dir.name}_with_ads.mp4"
    if with_ads_p.exists():
        try: os.remove(str(with_ads_p))
        except Exception: pass

    slide_ad = story_dir / "slide_ad.png"
    if slide_ad.exists():
        try: os.remove(str(slide_ad))
        except Exception: pass

    meta_p = story_dir / "metadata.json"
    if meta_p.exists():
        try:
            m_data = json.loads(meta_p.read_text(encoding="utf-8"))
            clean_comment = AD_PINNED_COMMENTS["clean"]
            m_data["ad_outro"] = {
                "attached": False,
                "filename": None,
                "title": None,
                "detached_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
            }
            m_data["pinned_comment"] = clean_comment
            meta_p.write_text(json.dumps(m_data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[Metadata] Pinned comment reset to clean default", flush=True)
        except Exception as ex:
            print(f"[Metadata Warning] Could not update metadata.json: {ex}", flush=True)

    return out_mp4

# =============================================================================
# STORY COMPILER ENGINE
# =============================================================================
def render_story(
    week_num: int,
    story_num: int,
    story_dir: Path,
    force_rebuild: bool = False,
    thumbnail_only: bool = False,
    slides_only: bool = False,
    slide_duration: float = DEFAULT_SLIDE_DURATION,
    custom_audio: str = None,
    combine_ad_only: bool = False,
    remove_ad_only: bool = False,
    comment_only: bool = False,
    ad_num: Any = None
) -> Path:
    """
    Renders or regenerates a 9:16 multi-slide story.
    Supports quick thumbnail-only regeneration, ad combination, and full MP4 compilation.
    """
    week_tag = f"W{week_num:02d}"
    out_mp4 = story_dir / "story_video_final.mp4"
    target_thumb = story_dir / "thumbnail.png"
    
    # Quick Mode 1: Pinned Comment Update Only (No video render)
    if comment_only:
        print(f"\n[Quick Mode] Triggering pinned comment update for {story_dir.name}...", flush=True)
        meta_p = story_dir / "metadata.json"
        if not meta_p.exists():
            print(f"[ERROR] metadata.json not found in {story_dir.name}!", flush=True)
            return None
        try:
            m_data = json.loads(meta_p.read_text(encoding="utf-8"))
            current_ad = m_data.get("ad_outro") or {}
            ad_source = ad_num if ad_num is not None else (current_ad.get("filename") if current_ad.get("attached") else None)
            clip_name = current_ad.get("filename")
            new_comment = generate_pinned_comment_for_ad(ad_source, clip_name)
            m_data["pinned_comment"] = new_comment
            if current_ad.get("attached"):
                current_ad["pinned_comment"] = new_comment
                m_data["ad_outro"] = current_ad
            meta_p.write_text(json.dumps(m_data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[SUCCESS] Pinned comment updated in {meta_p.name}", flush=True)
            return out_mp4
        except Exception as ex:
            print(f"[ERROR] Failed to update pinned comment: {ex}", flush=True)
            return None

    # Quick Mode 2: Remove Ad Outro and restore clean video
    if remove_ad_only:
        print(f"\n[Quick Mode] Removing ad outro and restoring clean story for {story_dir.name}...", flush=True)
        return remove_ad_from_story(story_dir, out_mp4)

    # Quick Mode 3: Fast Ad Combine & Update
    if combine_ad_only:
        print(f"\n[Quick Mode] Fast combining ad '{ad_num or 1}' for {story_dir.name}...", flush=True)
        return combine_story_with_ad(story_dir, ad_num or 1, out_mp4)

    # Check if existing video can be skipped
    if not force_rebuild and not thumbnail_only and out_mp4.exists() and out_mp4.stat().st_size > 100000:
        print(f"[SKIP] Story {story_num} video already rendered: {out_mp4.name} ({out_mp4.stat().st_size // 1024} KB). Use --force-rebuild to regenerate.")
        return out_mp4

    # Ensure scripts and metadata exist
    scaffold_story_if_missing(story_dir, week_num, story_num)
    
    script_path = story_dir / "story_script.md"
    meta_path = story_dir / "metadata.json"
    
    metadata = {}
    if meta_path.exists():
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    slides = parse_story_script(script_path)
    if not slides:
        print(f"[-] No slides found in {script_path}")
        return None
    curriculum = re.search(r'\*\*Curriculum:\*\*\s*(.+)', script_path.read_text(encoding="utf-8", errors="replace"))
    if curriculum and not metadata.get("curriculum"):
        metadata["curriculum"] = curriculum.group(1).strip()

    temp_dir = story_dir / "temp_slides"
    temp_dir.mkdir(parents=True, exist_ok=True)

    week_dir = story_dir.parent.parent
    bg_candidates = get_story_background_candidates(story_dir, week_dir, story_num, reel_num=metadata.get("reel_num"),
                                                    reel=metadata.get("reel"))

    title_display = metadata.get("title", story_dir.name)
    print(f"\n==========================================================================")
    print(f"▶ PRODUCING STORY {week_tag}.{story_num:02d}: {story_dir.name}")
    print(f"Benchmark Standard: 1080x1920 Story + Thematic Dynamic Scrim ({len(slides)} slides)")
    print(f"Title: {title_display}")
    print(f"==========================================================================")

    # 1. Render Slides
    slide_images = []
    with ProgressHeartbeat(f"Story {story_num} Slide Rendering", interval_sec=60):
        for idx, slide in enumerate(slides):
            bg_cand = bg_candidates[idx % len(bg_candidates)] if bg_candidates else None
            slide_img = render_slide_image(
                slide=slide,
                total_slides=len(slides),
                metadata=metadata,
                week_tag=week_tag,
                bg_image_path=bg_cand
            )
            img_out = temp_dir / f"slide_{idx+1}.png"
            slide_img.save(img_out, format="PNG", quality=95)
            slide_images.append(img_out)
            pct = int(((idx + 1) / len(slides)) * 100)
            print(f"  [Render] Slide {idx+1}/{len(slides)} ({pct}%): {slide['text'][:45]}...", flush=True)

    # 2. Sync Cover Thumbnail (Slide 1)
    if slide_images:
        shutil.copy2(slide_images[0], target_thumb)
        print(f"[SUCCESS] Story Thumbnail generated: {target_thumb.name} ({target_thumb.stat().st_size // 1024} KB)", flush=True)

    # Quick Mode: Exit early if thumbnail-only or slides-only
    if thumbnail_only:
        print(f"[Quick Mode] Thumbnail & Slide previews updated in seconds. Skipping video re-render.\n", flush=True)
        shutil.rmtree(temp_dir, ignore_errors=True)
        return target_thumb

    if slides_only:
        print(f"[Slides Mode] All {len(slide_images)} slide images saved in {temp_dir}. Skipping MP4 build.\n", flush=True)
        return temp_dir

    # 3. Compile MP4 Video with FFmpeg
    ffmpeg_bin = find_ffmpeg()
    concat_txt = temp_dir / "concat.txt"
    with open(concat_txt, "w", encoding="utf-8") as f:
        for s_img in slide_images:
            f.write(f"file '{s_img.name}'\n")
            f.write(f"duration {slide_duration}\n")
        if slide_images:
            f.write(f"file '{slide_images[-1].name}'\n")

    # Audio: no background music by default (music beds caused copyright claims). A licensed track can still be
    # passed with --audio; otherwise the video gets a silent track so every platform accepts it.
    audio_stem = Path(custom_audio) if custom_audio and os.path.exists(custom_audio) else None

    total_duration = len(slides) * slide_duration
    print(f"[FFmpeg] Compiling 1080x1920 MP4 ({total_duration:.1f}s) via {ffmpeg_bin}...", flush=True)

    cmd = [
        ffmpeg_bin, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_txt)
    ]

    if audio_stem and audio_stem.exists():
        fade_out_start = max(1.0, total_duration - 1.5)
        cmd.extend([
            "-stream_loop", "-1",
            "-i", str(audio_stem),
            "-filter_complex", f"[1:a]afade=t=in:st=0:d=0.8,afade=t=out:st={fade_out_start:.2f}:d=1.5,volume=0.35[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-t", str(total_duration),
            "-c:a", "aac",
            "-b:a", "192k"
        ])
    else:
        cmd.extend([
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-map", "0:v", "-map", "1:a",
            "-t", str(total_duration),
            "-c:a", "aac", "-b:a", "128k"
        ])

    cmd.extend([
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", "30",
        "-preset", "fast",
        str(out_mp4)
    ])

    with ProgressHeartbeat(f"Story {story_num} Video Encode", interval_sec=60):
        res = subprocess.run(cmd, cwd=str(temp_dir), capture_output=True, text=True)

    if res.returncode != 0:
        print(f"[ERROR] FFmpeg failed: {res.stderr}", flush=True)
        return None

    file_size_mb = out_mp4.stat().st_size / (1024 * 1024)
    print(f"[SUCCESS] Story video created: {out_mp4.name} ({file_size_mb:.2f} MB)", flush=True)
    print(f"Path: {out_mp4}\n", flush=True)

    # Attach ad outro if requested
    if ad_num:
        try:
            out_mp4 = combine_story_with_ad(story_dir, ad_num, out_mp4)
        except Exception as ex:
            print(f"[WARNING] Could not attach ad outro '{ad_num}': {ex}", flush=True)
    
    shutil.rmtree(temp_dir, ignore_errors=True)
    return out_mp4

# =============================================================================
# CLI MAIN ENTRY POINT
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Master Social Story Video Generator (9:16)")
    parser.add_argument("--week", "-w", type=str, default=None, help="Target week (e.g. 1, W01)")
    parser.add_argument("--story", "-s", type=str, default=None, help="Target story index (1 to 15) or key (mon_1)")
    parser.add_argument("--episode", "-e", "--global-story", "-g", type=int, default=None, help="Global story index (1 to 780)")
    parser.add_argument("--all", "-a", action="store_true", help="Generate every story of the week (5, or 15 when posting 3 a day)")
    parser.add_argument("--force-rebuild", action="store_true", help="Force rebuild even if video already exists")
    parser.add_argument("--thumbnail-only", "--thumb-only", action="store_true", help="Regenerate modern story cover thumbnail & slides in seconds")
    parser.add_argument("--slides-only", action="store_true", help="Generate slide images only without MP4 encoding")
    parser.add_argument("--duration", type=float, default=DEFAULT_SLIDE_DURATION, help="Per-slide duration in seconds (default: 3.5s)")
    parser.add_argument("--audio", "-m", type=str, default=None, help="Optional licensed soundtrack (default: no music, silent track)")
    parser.add_argument("--combine-ad", "--ad-only", "--regen-ad", action="store_true", help="Fast combine existing story video with ad outro without re-rendering slides")
    parser.add_argument("--remove-ad", "--strip-ad", action="store_true", help="Remove ad outro and restore clean story video")
    parser.add_argument("--comment-only", "--trigger-comment", action="store_true", help="Trigger and sync pinned comment in metadata.json based on attached ad")
    parser.add_argument("--ads", nargs="?", const="1", type=str, default=None, help="Include ad outro (variant 1, 2, 3 or filename in C:\\Projects\\Adz-Video)")
    args = parser.parse_args()

    week_num = None
    story_indices = []

    if args.episode is not None:
        ep = args.episode
        week_num = (ep - 1) // 5 + 1
        story_indices = [(ep - 1) % 5 + 1]
    elif args.week is not None:
        w_str = str(args.week).upper().replace("W", "")
        week_num = int(w_str)
        if args.all or args.story is None:
            story_indices = list(range(1, count_week_stories(BHSR_ROOT / f"W{week_num:02d}") + 1))
        else:
            story_indices = [args.story]
    else:
        parser.print_help()
        sys.exit(1)

    week_tag = f"W{week_num:02d}"
    week_dir = BHSR_ROOT / week_tag
    if not week_dir.exists():
        print(f"[ERROR] Week directory not found: {week_dir}")
        sys.exit(1)

    print(f"\n===========================================================================")
    print(f"MASTER STORY GENERATOR: Week {week_tag}, Stories {story_indices}")
    print(f"===========================================================================")

    completed = []
    for s_idx in story_indices:
        target_sub = find_story_folder(week_dir, s_idx)
        try:
            out_p = render_story(
                week_num=week_num,
                story_num=int(s_idx) if str(s_idx).isdigit() else 1,
                story_dir=target_sub,
                force_rebuild=args.force_rebuild,
                thumbnail_only=args.thumbnail_only,
                slides_only=args.slides_only,
                slide_duration=args.duration,
                custom_audio=args.audio,
                combine_ad_only=args.combine_ad,
                remove_ad_only=args.remove_ad,
                comment_only=args.comment_only,
                ad_num=args.ads
            )
            if out_p:
                completed.append(out_p)
        except Exception as e:
            print(f"[ERROR] Failed to process Story {s_idx}: {e}", flush=True)
            import traceback
            traceback.print_exc()

    print(f"\n===========================================================================")
    print(f"SUMMARY: Successfully processed {len(completed)} / {len(story_indices)} stories for {week_tag}")
    print(f"===========================================================================\n")

if __name__ == "__main__":
    main()
