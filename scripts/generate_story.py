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
     - Top 4px segmented Story progress bar (completed gold, active white, pending translucent)
     - Top-left red pill badge: [ THE SECRET BIBLE CODE ]
     - Top-right circular gold channel seal watermark
     - Two-tone floating typography (White + Electric Yellow) with drop shadow
     - Automatic Unicode font switching for Hebrew glyphs (no broken boxes)
     - Native Instagram/FB style interactive stickers (Poll: YES/NO, Link: TAP TO WATCH)
     - Translucent dark scripture pill badges & bottom brand footer
  4. Heartbeat & FFmpeg Audio Mastering:
     - ProgressHeartbeat for background liveness
     - Demucs stem audio mixing with smooth 1.5s fade-out
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
    clean = re.sub(r'[:?]', '', title).strip()
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

def create_story_scrim(W, H, is_hook=False):
    """Fast smooth 2D gradient scrim (15ms execution time)."""
    mask = Image.new("L", (32, 64), 0)
    mdraw = ImageDraw.Draw(mask)
    
    # 1. Top gradient for progress bar, badge, and logo legibility
    top_limit = 22 if is_hook else 18
    for y in range(top_limit):
        mdraw.line([(0, y), (32, y)], fill=int(185 * ((top_limit - y) / top_limit)))
        
    # 2. Text backdrop scrim with left-side bias
    for y in range(8, 34):
        y_factor = max(0.0, 1.0 - abs((y - 19) / 13.0) ** 1.8)
        for x in range(32):
            x_factor = max(0.0, ((32 - x) / 32.0) ** 0.8)
            alpha = int(185 * y_factor * x_factor)
            cur = mask.getpixel((x, y))
            if alpha > cur:
                mask.putpixel((x, y), alpha)
                
    # 3. Bottom vignette for stickers / footer
    for y in range(48, 64):
        mdraw.line([(0, y), (32, y)], fill=int(195 * ((y - 48) / 16.0)))
        
    mask_full = mask.resize((W, H), Image.Resampling.BICUBIC)
    overlay = Image.new("RGBA", (W, H), (6, 8, 14, 0))
    overlay.putalpha(mask_full)
    return overlay

def draw_shadowed_text(draw, x, y, text, font, fill=WHITE, shadow_fill=BLACK, r=4):
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
        title = default_titles[story_num - 1]

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    day_name = days[story_num - 1]

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
            "- **On-Screen Text:** Tap below to watch the full documentary premiere!",
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
    scrim = create_story_scrim(WIDTH, HEIGHT, is_hook=is_hook)
    canvas = Image.alpha_composite(base, scrim)
    draw = ImageDraw.Draw(canvas, "RGBA")

    # 2. Segmented Story Progress Bars (Y: 36)
    margin = 32
    bar_y = 36
    bar_h = 5
    gap = 8
    total_gaps = (total_slides - 1) * gap
    bar_w = (WIDTH - (margin * 2) - total_gaps) // total_slides

    for i in range(total_slides):
        bx1 = margin + i * (bar_w + gap)
        bx2 = bx1 + bar_w
        if i + 1 < slide_num:
            fill_col = (255, 225, 0, 240)    # gold completed
        elif i + 1 == slide_num:
            fill_col = (255, 255, 255, 255)  # white active
        else:
            fill_col = (255, 255, 255, 65)   # pending
        draw.rounded_rectangle([bx1, bar_y, bx2, bar_y + bar_h], radius=3, fill=fill_col)

    # 3. Header Bar: Red Pill Badge (Top Left) & Channel Logo (Top Right)
    badge_y = 66
    badge_font = find_font(28, bold=True)
    badge_text = f"THE SECRET BIBLE CODE • PART {slide_num}" if not is_hook else "THE SECRET BIBLE CODE"
    bw = draw.textlength(badge_text, font=badge_font)
    pill_box = [margin, badge_y, margin + int(bw) + 36, badge_y + 46]
    
    pill_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pill_layer)
    pdraw.rounded_rectangle(pill_box, radius=12, fill=RED_FILL, outline=RED_OUTLINE, width=2)
    canvas = Image.alpha_composite(canvas, pill_layer)
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.text((margin + 18, badge_y + 8), badge_text, font=badge_font, fill=WHITE)

    # Channel Logo (Top Right)
    logo_file = find_logo()
    if logo_file:
        try:
            logo = Image.open(logo_file).convert("RGBA").resize((84, 84), Image.Resampling.LANCZOS)
            canvas.paste(logo, (WIDTH - margin - 84, badge_y - 12), logo)
            draw = ImageDraw.Draw(canvas, "RGBA")
        except Exception:
            pass

    # 4. Slide Content (Floating, Breathable, High-Contrast Typography)
    start_x = margin + 12
    max_text_w = WIDTH - (margin * 2) - 24

    if is_hook:
        # Hook Slide: Clean, punchy 2-line title
        hook_candidate = title if (len(title.split()) <= 8) else on_screen_text
        line1, line2 = split_story_title(hook_candidate)
        font_h1 = fit_font(draw, line1, max_text_w, 104, min_size=64)
        font_h2 = fit_font(draw, line2, max_text_w, 104, min_size=64)
        font_kicker = find_font(34, bold=True)

        y1 = 200
        draw_shadowed_text(draw, start_x, y1, line1, font_h1, fill=WHITE, r=6)

        line1_h = font_h1.size if hasattr(font_h1, "size") else 96
        y2 = y1 + int(line1_h * 1.10)
        draw_shadowed_text(draw, start_x, y2, line2, font_h2, fill=YELLOW, r=6)

        kicker_text = "THE SECRET PRE-CREATION WAR EXPOSED"
        line2_h = font_h2.size if hasattr(font_h2, "size") else 96
        y3 = y2 + int(line2_h * 1.20)
        draw_shadowed_text(draw, start_x, y3, kicker_text, font_kicker, fill=(240, 240, 240), r=4)

        # Scripture Pill
        if reference:
            sc_font = find_font(26, bold=True)
            first_ref = reference.split(",")[0].strip().upper()
            sw = draw.textlength(first_ref, font=sc_font)
            sc_box = [start_x, y3 + 55, start_x + int(sw) + 32, y3 + 97]
            sc_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            sc_draw = ImageDraw.Draw(sc_layer)
            sc_draw.rounded_rectangle(sc_box, radius=10, fill=DARK_PILL_FILL, outline=YELLOW + (200,), width=2)
            canvas = Image.alpha_composite(canvas, sc_layer)
            draw = ImageDraw.Draw(canvas, "RGBA")
            draw.text((start_x + 16, y3 + 63), first_ref, font=sc_font, fill=YELLOW)

    else:
        # Narrative Slides: Clean, readable floating cards with two-tone header
        y_cursor = 190
        kicker_text = "THE ANCIENT SCRIPTURES REVEAL" if slide_num == 2 else ("THE DEEP REVELATION" if slide_num == 3 else ("COMMUNITY POLL" if "poll" in sticker.lower() else "THE FINALE"))
        
        # Topic kicker
        kicker_font = find_font(28, bold=True)
        draw_shadowed_text(draw, start_x, y_cursor, kicker_text, kicker_font, fill=YELLOW, r=3)
        y_cursor += 42

        # Extract headline and body text
        sentences = on_screen_text.split(":")
        if len(sentences) > 1 and len(sentences[0].split()) <= 6:
            h_text = sentences[0].strip().upper()
            body_text = ":".join(sentences[1:]).strip()
        else:
            words = on_screen_text.split()
            split_p = min(6, len(words) // 2) if len(words) > 8 else len(words)
            h_text = " ".join(words[:split_p]).upper()
            body_text = " ".join(words[split_p:]).strip()

        h_font = fit_font(draw, h_text, max_text_w, 74, min_size=46)
        draw_shadowed_text(draw, start_x, y_cursor, h_text, h_font, fill=WHITE, r=5)
        h_h = h_font.size if hasattr(h_font, "size") else 70
        y_cursor += int(h_h * 1.15)

        # Thin gold accent line
        draw.line([(start_x, y_cursor), (start_x + 160, y_cursor)], fill=YELLOW + (220,), width=3)
        y_cursor += 28

        # Body text with Hebrew Unicode font support
        if body_text:
            body_font = find_font(42, bold=True, text=body_text)
            body_lines = wrap_text(body_text, body_font, max_text_w, draw)
            for line in body_lines[:5]:
                draw_shadowed_text(draw, start_x, y_cursor, line, body_font, fill=WHITE, r=4)
                y_cursor += 58

        # Scripture Pill
        if reference:
            y_cursor += 15
            sc_font = find_font(26, bold=True)
            first_ref = reference.split(",")[0].strip().upper()
            sw = draw.textlength(first_ref, font=sc_font)
            sc_box = [start_x, y_cursor, start_x + int(sw) + 32, y_cursor + 42]
            sc_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            sc_draw = ImageDraw.Draw(sc_layer)
            sc_draw.rounded_rectangle(sc_box, radius=10, fill=DARK_PILL_FILL, outline=YELLOW + (200,), width=2)
            canvas = Image.alpha_composite(canvas, sc_layer)
            draw = ImageDraw.Draw(canvas, "RGBA")
            draw.text((start_x + 16, y_cursor + 8), first_ref, font=sc_font, fill=YELLOW)

    # 5. Interactive Bottom Stickers
    sticker_y = 1430
    if "poll" in sticker.lower() or "yes" in sticker.lower():
        # Sleek Instagram Poll Sticker
        poll_box = [margin, sticker_y, WIDTH - margin, sticker_y + 190]
        poll_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        pld = ImageDraw.Draw(poll_layer)
        pld.rounded_rectangle(poll_box, radius=22, fill=(16, 20, 30, 220), outline=(60, 75, 110, 200), width=2)
        
        q_font = find_font(26, bold=True)
        pld.text((margin + 28, sticker_y + 22), "TAP TO CAST YOUR VOTE:", font=q_font, fill=(200, 215, 240, 230))
        
        # Option A (YES)
        pld.rounded_rectangle([margin + 24, sticker_y + 68, WIDTH // 2 - 12, sticker_y + 154], radius=16, fill=(16, 185, 129, 230), outline=(52, 211, 153, 255), width=2)
        btn_font = find_font(36, bold=True)
        pld.text((margin + 120, sticker_y + 90), "YES  (84%)", font=btn_font, fill=WHITE)
        
        # Option B (NO)
        pld.rounded_rectangle([WIDTH // 2 + 12, sticker_y + 68, WIDTH - margin - 24, sticker_y + 154], radius=16, fill=(239, 68, 68, 230), outline=(248, 113, 113, 255), width=2)
        pld.text((WIDTH // 2 + 105, sticker_y + 90), "NO  (16%)", font=btn_font, fill=WHITE)
        
        canvas = Image.alpha_composite(canvas, poll_layer)
        draw = ImageDraw.Draw(canvas, "RGBA")

    elif "link" in sticker.lower() or "watch" in sticker.lower() or slide_num == 5:
        # Sleek Instagram Link Sticker
        link_box = [margin + 40, sticker_y + 30, WIDTH - margin - 40, sticker_y + 140]
        link_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        lld = ImageDraw.Draw(link_layer)
        lld.rounded_rectangle(link_box, radius=24, fill=YELLOW + (240,), outline=WHITE + (240,), width=3)
        
        link_font = find_font(40, bold=True)
        link_text = "TAP TO WATCH FULL EPISODE >>"
        lw = lld.textlength(link_text, font=link_font)
        lld.text(((WIDTH - lw) // 2, sticker_y + 62), link_text, font=link_font, fill=(10, 12, 18))
        
        canvas = Image.alpha_composite(canvas, link_layer)
        draw = ImageDraw.Draw(canvas, "RGBA")

    else:
        # Subtle Swipe Prompt
        swipe_box = [margin + 80, sticker_y + 60, WIDTH - margin - 80, sticker_y + 130]
        sw_layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        swd = ImageDraw.Draw(sw_layer)
        swd.rounded_rectangle(swipe_box, radius=18, fill=(16, 20, 30, 190), outline=YELLOW + (120,), width=1)
        
        sw_font = find_font(28, bold=True)
        sw_text = "SWIPE TO UNCOVER NEXT REVELATION >>" if is_hook else "TAP / SWIPE FOR NEXT PART >>"
        sw_w = swd.textlength(sw_text, font=sw_font)
        swd.text(((WIDTH - sw_w) // 2, sticker_y + 78), sw_text, font=sw_font, fill=YELLOW + (240,))
        
        canvas = Image.alpha_composite(canvas, sw_layer)
        draw = ImageDraw.Draw(canvas, "RGBA")

    # 6. Brand Footer
    brand_font = find_font(24, bold=True)
    bw = draw.textlength(BRAND_TEXT, font=brand_font)
    draw.text(((WIDTH - bw) // 2, 1845), BRAND_TEXT, font=brand_font, fill=GOLD + (220,))

    return canvas.convert("RGB")

# =============================================================================
# THEMATIC ARTWORK RESOLUTION
# =============================================================================
def get_story_background_candidates(story_dir: Path, week_dir: Path, story_idx: int) -> list:
    """Intelligently pairs each story with thematic artwork from reels or long form."""
    candidates = []
    
    # 1. Matching reel folder for this story
    reels_dir = week_dir / "reels"
    if reels_dir.exists():
        sub_reels = sorted([d for d in reels_dir.iterdir() if d.is_dir()])
        if story_idx <= len(sub_reels):
            target_reel = sub_reels[story_idx - 1]
            r_imgs = sorted(list((target_reel / "images").glob("reel*.png")))
            r_imgs = [img for img in r_imgs if "card" not in img.name]
            candidates.extend(r_imgs)
            
    # 2. Long form scene images
    lf_img_dir = week_dir / "long_form" / "images"
    if lf_img_dir.exists():
        candidates.extend(sorted(list(lf_img_dir.glob("*.png"))))
        
    # 3. Fallbacks
    cand_defaults = [
        week_dir / "long_form" / "thumbnail_option_1.jpg",
        week_dir / "long_form" / "thumbnail.png"
    ]
    candidates.extend([c for c in cand_defaults if c.exists()])
    return candidates

def find_story_folder(week_dir: Path, story_num: int) -> Path:
    """Finds the folder for a given story index within week_dir/stories."""
    stories_dir = week_dir / "stories"
    stories_dir.mkdir(parents=True, exist_ok=True)
    
    prefix = f"0{story_num}"
    subdirs = sorted([d for d in stories_dir.iterdir() if d.is_dir() and "temp" not in d.name.lower()])
    
    for d in subdirs:
        if d.name.startswith(prefix) or d.name.startswith(f"{story_num}_") or d.name.startswith(f"{story_num}-"):
            return d
            
    if story_num <= len(subdirs):
        return subdirs[story_num - 1]
        
    # Create standard folder if completely missing
    days = ["monday", "tuesday", "wednesday", "thursday", "friday"]
    day = days[story_num - 1] if story_num <= 5 else f"day_{story_num}"
    new_dir = stories_dir / f"0{story_num}_{day}_story"
    new_dir.mkdir(parents=True, exist_ok=True)
    return new_dir

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
    custom_audio: str = None
) -> Path:
    """
    Renders or regenerates a 9:16 multi-slide story.
    Supports quick thumbnail-only regeneration and full MP4 compilation.
    """
    week_tag = f"W{week_num:02d}"
    out_mp4 = story_dir / "story_video_final.mp4"
    target_thumb = story_dir / "thumbnail.png"
    
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

    temp_dir = story_dir / "temp_slides"
    temp_dir.mkdir(parents=True, exist_ok=True)

    week_dir = story_dir.parent.parent
    bg_candidates = get_story_background_candidates(story_dir, week_dir, story_num)

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

    # Select audio track
    audio_stem = None
    if custom_audio and os.path.exists(custom_audio):
        audio_stem = Path(custom_audio)
    else:
        stem_candidates = [
            BHSR_ROOT / "demucs_stems" / "htdemucs" / "original_audio" / "other.wav",
            BHSR_ROOT / "demucs_stems" / "htdemucs" / "original_audio" / "ambient.wav",
            PROJECT_DIR / "shared_assets" / "ambient_music.wav"
        ]
        audio_stem = next((p for p in stem_candidates if p.exists()), None)

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
        cmd.extend(["-t", str(total_duration)])

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
    
    shutil.rmtree(temp_dir, ignore_errors=True)
    return out_mp4

# =============================================================================
# CLI MAIN ENTRY POINT
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Master Social Story Video Generator (9:16)")
    parser.add_argument("--week", "-w", type=str, default=None, help="Target week (e.g. 1, W01)")
    parser.add_argument("--story", "-s", type=int, default=None, help="Target story index (1 to 5)")
    parser.add_argument("--episode", "-e", "--global-story", "-g", type=int, default=None, help="Global story index (1 to 780)")
    parser.add_argument("--all", "-a", action="store_true", help="Generate all 5 daily stories for the week")
    parser.add_argument("--force-rebuild", action="store_true", help="Force rebuild even if video already exists")
    parser.add_argument("--thumbnail-only", "--thumb-only", action="store_true", help="Regenerate modern story cover thumbnail & slides in seconds")
    parser.add_argument("--slides-only", action="store_true", help="Generate slide images only without MP4 encoding")
    parser.add_argument("--duration", type=float, default=DEFAULT_SLIDE_DURATION, help="Per-slide duration in seconds (default: 3.5s)")
    parser.add_argument("--audio", "-m", type=str, default=None, help="Path to custom soundtrack audio file")
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
            story_indices = [1, 2, 3, 4, 5]
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
                story_num=s_idx,
                story_dir=target_sub,
                force_rebuild=args.force_rebuild,
                thumbnail_only=args.thumbnail_only,
                slides_only=args.slides_only,
                slide_duration=args.duration,
                custom_audio=args.audio
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
