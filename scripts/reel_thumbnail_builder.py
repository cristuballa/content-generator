"""
=============================================================================
REEL COMPOSITE THUMBNAIL BUILDER (VIRAL YOUTUBE / REELS STYLE)
Bible Hidden Secrets Revealed
=============================================================================
Generates high-converting cinematic 9:16 composite thumbnails for reels:
  - Full-frame FLUX artwork scaled and center-cropped to 9:16
  - Contrast (+25%) & Saturation (+30%) pop for cinematic intensity
  - Top-left red pill badge: "THE SECRET BIBLE CODE" (or custom category/series)
  - Top-right gold circular channel seal watermark
  - Massive Two-Tone Headline:
      * Line 1 in PURE WHITE (e.g. "WHAT DID GOD DO", "WHAT HAPPENED")
      * Line 2 in VIBRANT ELECTRIC YELLOW (e.g. "BEFORE GENESIS?", "IN GENESIS 1:1")
      * Heavy 8-direction black drop-shadow / stroke for 100% legibility
  - Kicker subtitle: "THE BANNED PRE-CREATION WAR EXPOSED" (or custom mystery hook)
  - Translucent scripture pill (e.g. "JOB 38:4-7")
  - Bottom brand label: "BIBLE HIDDEN SECRETS REVEALED"
=============================================================================
"""

import os
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

# ---- Color Palette -----------------------------------------------------------
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
    Path(r"C:\Projects\BHSR\shared_assets\transparent_logo.png"),
    Path(__file__).resolve().parent.parent / "shared_assets" / "transparent_logo.png",
    Path(__file__).resolve().parent / "transparent_logo.png"
]

def _find_logo():
    for p in LOGO_CANDIDATES:
        if p.exists():
            return str(p)
    return None

def _load_font(names, size):
    """Load the first available TrueType font, falling back to default."""
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    return ImageFont.load_default()

def _fit_font(draw, text, font_name, max_w, max_size, min_size=40):
    """Dynamically scales font size down until text fits within max_w."""
    size = max_size
    font = _load_font([font_name], size)
    while draw.textlength(text, font=font) > max_w and size > min_size:
        size -= 4
        font = _load_font([font_name], size)
    return font

def split_headline(title: str, line1: str = None, line2: str = None) -> tuple[str, str]:
    """
    Intelligently splits title into Line 1 (White) and Line 2 (Yellow)
    if explicit lines are not passed.
    """
    if line1 and line2:
        return line1.strip().upper(), line2.strip().upper()
    
    clean_title = title.replace("?", "").strip()
    words = clean_title.split()
    if len(words) <= 2:
        return words[0].upper(), (words[1].upper() if len(words) > 1 else "")
    
    # Priority keywords for the split
    split_markers = ["BEFORE", "IN THE", "IN", "RE-WROTE", "DISQUALIFICATION", "HIDDEN", "REVEALED", "FROM", "AGAINST"]
    split_idx = -1
    for m in split_markers:
        m_word = m.split()[0].upper()
        for i, w in enumerate(words):
            if w.upper() == m_word and i >= 2:
                split_idx = i
                break
        if split_idx != -1:
            break
            
    if split_idx == -1:
        split_idx = max(2, len(words) // 2)
        
    l1 = " ".join(words[:split_idx]).upper()
    l2 = " ".join(words[split_idx:]).upper()
    
    # Preserve question mark if appropriate
    is_question = "?" in title or any(w.lower() in ["what", "why", "how", "who", "where", "did", "was", "is"] for w in words[:2])
    if is_question and not l2.endswith("?"):
        l2 += "?"
        
    return l1, l2

def _create_cinematic_scrim(W, H):
    """Generates ultra-fast smooth 2D gradient backdrop scrim."""
    mask = Image.new("L", (32, 64), 0)
    mdraw = ImageDraw.Draw(mask)
    
    # 1. Top gradient for badge and logo legibility (Y: 0 to 14)
    for y in range(14):
        mdraw.line([(0, y), (32, y)], fill=int(175 * ((14 - y) / 14)))
        
    # 2. Text backdrop scrim (Y: 8 to 36) with heavy left-side bias
    for y in range(8, 38):
        y_factor = max(0.0, 1.0 - abs((y - 21) / 15.0) ** 1.8)
        for x in range(32):
            x_factor = max(0.0, ((32 - x) / 32.0) ** 0.85)
            alpha = int(210 * y_factor * x_factor)
            cur = mask.getpixel((x, y))
            if alpha > cur:
                mask.putpixel((x, y), alpha)
                
    # 3. Bottom vignette for brand footer (Y: 54 to 64)
    for y in range(54, 64):
        mdraw.line([(0, y), (32, y)], fill=int(185 * ((y - 54) / 10.0)))
        
    mask_full = mask.resize((W, H), Image.Resampling.BICUBIC)
    overlay = Image.new("RGBA", (W, H), (5, 6, 12, 0))
    overlay.putalpha(mask_full)
    return overlay

def generate_composite_reel_thumbnail(
    base_img_path: str,
    title: str = "WHAT DID GOD DO BEFORE GENESIS?",
    week_tag: str = "THE SECRET BIBLE CODE",
    scripture: str = "",
    subtitle: str = "",
    brand: str = BRAND_TEXT,
    out_path: str = None,
    out_size: tuple = (1080, 1920),
    badge_text: str = None,
    line1: str = None,
    line2: str = None,
    kicker: str = None,
    **kwargs
) -> str:
    """
    Generate a viral YouTube/Reels-style 9:16 composite thumbnail.
    """
    W, H = out_size
    scale = W / 1080.0
    
    if out_path is None:
        if base_img_path:
            out_path = os.path.join(os.path.dirname(base_img_path), "thumbnail.jpg")
        else:
            out_path = "thumbnail.jpg"

    # 1. Base Image Load & Cover Crop
    if base_img_path and os.path.exists(base_img_path):
        try:
            art = Image.open(base_img_path).convert("RGBA")
            art_ratio = art.width / art.height
            out_ratio = W / H
            if art_ratio > out_ratio:
                new_h = H
                new_w = int(art.width * H / art.height)
            else:
                new_w = W
                new_h = int(art.height * W / art.width)
            art = art.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left = (new_w - W) // 2
            top = (new_h - H) // 2
            base = art.crop((left, top, left + W, top + H))
            
            # Contrast & Color boost for that punchy YouTube thumbnail grade
            base = ImageEnhance.Contrast(base).enhance(1.25)
            base = ImageEnhance.Color(base).enhance(1.30)
        except Exception as e:
            print(f"[Thumbnail Warning] Could not load base image {base_img_path}: {e}")
            base = Image.new("RGBA", (W, H), (12, 16, 26, 255))
    else:
        base = Image.new("RGBA", (W, H), (12, 16, 26, 255))

    # 2. Cinematic Scrim Overlay
    scrim = _create_cinematic_scrim(W, H)
    canvas = Image.alpha_composite(base, scrim)
    draw = ImageDraw.Draw(canvas, "RGBA")

    # 3. Fonts
    font_badge_size = int(56 * scale)
    font_sub_size   = int(52 * scale)
    font_brand_size = int(34 * scale)
    font_scrip_size = int(42 * scale)
    max_title_size  = int(122 * scale)

    font_badge = _load_font(["impact.ttf", "arialbd.ttf"], font_badge_size)
    font_sub   = _load_font(["arialbd.ttf", "impact.ttf"], font_sub_size)
    font_brand = _load_font(["arialbd.ttf", "arial.ttf"], font_brand_size)
    font_scrip = _load_font(["arialbd.ttf", "arial.ttf"], font_scrip_size)

    start_x = int(75 * scale)
    start_y = int(220 * scale)

    # 4. Red Pill Badge (Top Left)
    effective_badge = badge_text or (week_tag if week_tag and not "WEEK" in week_tag.upper() else "THE SECRET BIBLE CODE")
    bw = draw.textlength(effective_badge, font=font_badge)
    pill_h = int(84 * scale)
    pill_w = int(bw + 56 * scale)
    pill_box = [start_x, start_y, start_x + pill_w, start_y + pill_h]
    
    pill_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pill_layer)
    pdraw.rounded_rectangle(pill_box, radius=int(18 * scale), fill=RED_FILL, outline=RED_OUTLINE, width=max(2, int(3 * scale)))
    canvas = Image.alpha_composite(canvas, pill_layer)
    draw = ImageDraw.Draw(canvas, "RGBA")
    draw.text((start_x + int(28 * scale), start_y + int(10 * scale)), effective_badge, font=font_badge, fill=WHITE)

    # 5. Channel Logo Watermark (Top Right)
    logo_file = _find_logo()
    if logo_file:
        try:
            logo_size = int(125 * scale)
            logo = Image.open(logo_file).convert("RGBA").resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            canvas.paste(logo, (W - logo_size - int(65 * scale), start_y - int(25 * scale)), logo)
            draw = ImageDraw.Draw(canvas, "RGBA")
        except Exception:
            pass

    # 6. Two-Tone Headline
    headline_1, headline_2 = split_headline(title, line1=line1, line2=line2)
    max_text_w = int(W * 0.88)
    
    font_l1 = _fit_font(draw, headline_1, "impact.ttf", max_text_w, max_title_size, min_size=int(72 * scale))
    font_l2 = _fit_font(draw, headline_2, "impact.ttf", max_text_w, max_title_size, min_size=int(72 * scale))

    # Calculate Y coordinates
    y1 = start_y + int(130 * scale)
    shadow_r = max(4, int(7 * scale))

    # Line 1: Pure White with heavy 8-directional drop shadow
    for ox in range(-shadow_r, shadow_r + 1):
        for oy in range(-shadow_r, shadow_r + 1):
            if abs(ox) + abs(oy) > 3:
                draw.text((start_x + ox, y1 + oy), headline_1, font=font_l1, fill=BLACK)
    draw.text((start_x, y1), headline_1, font=font_l1, fill=WHITE)

    # Line 2: Vibrant Electric Yellow
    line1_h = font_l1.size if hasattr(font_l1, "size") else int(110 * scale)
    y2 = y1 + int(line1_h * 1.08)
    for ox in range(-shadow_r - 1, shadow_r + 2):
        for oy in range(-shadow_r - 1, shadow_r + 2):
            if abs(ox) + abs(oy) > 3:
                draw.text((start_x + ox, y2 + oy), headline_2, font=font_l2, fill=BLACK)
    draw.text((start_x, y2), headline_2, font=font_l2, fill=YELLOW)

    # 7. Subtitle / Kicker
    effective_kicker = kicker or subtitle or ""
    effective_kicker = effective_kicker.upper()
    # Largest subtitle size that fits in at most two lines (wrapped below)
    for sub_size in (font_sub_size, int(46 * scale), int(40 * scale)):
        font_sub = _load_font(["arialbd.ttf", "impact.ttf"], sub_size)
        words, lines_needed, current = effective_kicker.split(), 1, ""
        for word in words:
            test = f"{current} {word}".strip()
            if current and draw.textlength(test, font=font_sub) > max_text_w:
                lines_needed, current = lines_needed + 1, word
            else:
                current = test
        if lines_needed <= 2:
            break

    line2_h = font_l2.size if hasattr(font_l2, "size") else int(110 * scale)
    y3 = y2 + int(line2_h * 1.18)
    sub_shadow = max(2, int(4 * scale))
    # A subtitle still too wide at the minimum size wraps onto a second line instead of running off the edge
    sub_lines, current = [], ""
    for word in effective_kicker.split():
        test = f"{current} {word}".strip()
        if current and draw.textlength(test, font=font_sub) > max_text_w:
            sub_lines.append(current)
            current = word
        else:
            current = test
    sub_lines.append(current)
    sub_line_h = int(font_sub.size * 1.2) if hasattr(font_sub, "size") else int(48 * scale)
    for i, line in enumerate(sub_lines[:2]):
        ly = y3 + i * sub_line_h
        for ox in range(-sub_shadow, sub_shadow + 1):
            for oy in range(-sub_shadow, sub_shadow + 1):
                draw.text((start_x + ox, ly + oy), line, font=font_sub, fill=(0, 0, 0, 240))
        draw.text((start_x, ly), line, font=font_sub, fill=(240, 240, 240))

    # 8. Scripture Pill (Below Subtitle)
    if scripture:
        # Only the first reference: lists are separated by ',' or '/'
        first_ref = re.split(r"[,/;]", scripture)[0].strip().upper()
        sw = draw.textlength(first_ref, font=font_scrip)
        sc_h = int(64 * scale)
        sc_w = int(sw + 48 * scale)
        sc_y = y3 + (len(sub_lines[:2]) - 1) * sub_line_h + int(74 * scale)
        sc_box = [start_x, sc_y, start_x + sc_w, sc_y + sc_h]
        
        sc_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        sc_draw = ImageDraw.Draw(sc_layer)
        sc_draw.rounded_rectangle(sc_box, radius=int(12 * scale), fill=DARK_PILL_FILL, outline=YELLOW + (200,), width=max(1, int(2 * scale)))
        canvas = Image.alpha_composite(canvas, sc_layer)
        draw = ImageDraw.Draw(canvas, "RGBA")
        draw.text((start_x + int(24 * scale), sc_y + int(10 * scale)), first_ref, font=font_scrip, fill=YELLOW)

    # 9. Brand Footer
    bw = draw.textlength(brand, font=font_brand)
    bx = (W - bw) // 2
    draw.text((bx, H - int(100 * scale)), brand, font=font_brand, fill=GOLD + (220,))

    # Save output
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    canvas.convert("RGB").save(out_path, "JPEG", quality=95)
    return str(out_path)

if __name__ == "__main__":
    import sys
    print("Reel Composite Thumbnail Builder module loaded.")
