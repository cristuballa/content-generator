"""
=============================================================================
BIBLE HIDDEN SECRETS REVEALED — MASTER 16:9 VIDEO GENERATOR (generate_video.py)
=============================================================================
Universal, single root generator for all 16:9 long-form documentary episodes.
Standard: 16:9 Landscape (1920x1080 Full HD), YouTube Master Quality
- Resolution: 1920x1080 (16:9 Full HD), 24 FPS
- Motion: Smooth Ken Burns frame-by-frame easing zoom/pan (apply_motion_16x9)
- Captions: Safe-zone (Y=85%) rounded black badge with white text & active gold word highlight
- Audio: Broadcast-mastered narration only (no background music)
- Visuals: FLUX.1 Schnell GGUF photorealistic 16:9 scene images (1344x768) + ComfyUI pipeline
- Metadata: Dynamically ingests metadata.json, script_30min.txt, and visual scene cues
- Streaming: Injects -movflags +faststart for instant web streaming
=============================================================================
CLI Usage:
  python generate_video.py --week 1
  python generate_video.py --week 2
  python generate_video.py --week 2 --images-only
  python generate_video.py --week 2 --force-rebuild
  python generate_video.py --week 2 --speed 1.05
  python generate_video.py --list
=============================================================================
"""

import os
import sys
import re
import math
import time
import json
import shutil
import difflib
import argparse
import subprocess
import urllib.request
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

if sys.platform == "win32":
    try:
        import ctypes
        # Set process priority to BELOW_NORMAL to keep system responsive
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
    except Exception:
        pass

# =============================================================================
# ENVIRONMENT & PATH CONFIGURATION
# =============================================================================
BHSR_ROOT = Path(r"C:\Projects\BHSR") if Path(r"C:\Projects\BHSR").exists() else Path(__file__).resolve().parent
if BHSR_ROOT.name == "scripts":
    BHSR_ROOT = BHSR_ROOT.parent

BHSR_YOUTUBE_DIR = Path(r"C:\Projects\BHSR-Youtube")
SHARED_ASSETS = BHSR_ROOT / "shared_assets"

COMFY_DIR = r"C:\Users\User\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"
COMFY_PYTHON = os.path.join(COMFY_DIR, r".venv\Scripts\python.exe")
COMFY_URL = "http://127.0.0.1:8188"
COMFY_OUTPUT_DIR = os.path.join(COMFY_DIR, "output")

def find_vibevoice_paths():
    cand_pythons = [
        BHSR_ROOT / ".venv_vibevoice" / "Scripts" / "python.exe",
        Path(r"C:\Projects\BHSR\.venv_vibevoice\Scripts\python.exe"),
        Path(r"C:\Projects\Bible Hidden Secrets Revealed\.venv_vibevoice\Scripts\python.exe"),
    ]
    cand_scripts = [
        BHSR_ROOT / "vibevoice_engine.py",
        Path(r"C:\Projects\BHSR\vibevoice_engine.py"),
        Path(r"C:\Projects\Bible Hidden Secrets Revealed\vibevoice_engine.py"),
    ]
    vv_py = next((str(p) for p in cand_pythons if p.exists()), str(cand_pythons[0]))
    vv_script = next((str(s) for s in cand_scripts if s.exists()), str(cand_scripts[0]))
    return vv_py, vv_script

VIBEVOICE_PYTHON, VIBEVOICE_SCRIPT = find_vibevoice_paths()

DEFAULT_VOICE_PT = str(SHARED_ASSETS / "cloned_voice_021.pt")
if not os.path.exists(DEFAULT_VOICE_PT):
    cand_pt = BHSR_ROOT / "cloned_voice_021.pt"
    if cand_pt.exists():
        DEFAULT_VOICE_PT = str(cand_pt)

LOCAL_LOGO = str(SHARED_ASSETS / "transparent_logo.png")
if not os.path.exists(LOCAL_LOGO):
    LOCAL_LOGO = str(BHSR_ROOT / "shared_assets" / "transparent_logo.png")

# Narration EQ / de-ess / compression applied before loudness normalisation (voice only, no music bed)
VOICE_MASTER_CHAIN = "highpass=f=75,lowpass=f=7200,equalizer=f=220:t=q:w=1.2:g=2.5,equalizer=f=3400:t=q:w=1.8:g=-4.5,equalizer=f=5500:t=q:w=1.5:g=-5.0,deesser=i=0.6:m=0.5:f=0.5,compand=attacks=0.01:decays=0.08:points=-80/-80|-22/-10|-10/-3|0/0,volume=3.2"

# Auto-switch to ComfyUI environment if running from python lacking whisper / imageio
if __name__ == "__main__" and "--list" not in sys.argv:
    try:
        import whisper
        import imageio
    except ImportError:
        target_py = COMFY_PYTHON if os.path.exists(COMFY_PYTHON) else VIBEVOICE_PYTHON
        if os.path.exists(target_py) and os.path.normpath(sys.executable).lower() != os.path.normpath(target_py).lower():
            sys.exit(subprocess.call([target_py] + sys.argv))

try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = shutil.which("ffmpeg") or r"C:\Users\User\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg.exe"

if FFMPEG_EXE and os.path.dirname(FFMPEG_EXE):
    os.environ["PATH"] = os.path.dirname(FFMPEG_EXE) + os.pathsep + os.environ.get("PATH", "")

# 16:9 Standard Dimensions
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080
FLUX_WIDTH = 1344
FLUX_HEIGHT = 768
FPS = 24

# Mapping from weekly / episode index to BHSR-Youtube folders
BHSR_EPISODE_MAP = {
    1: "3-What_Happened_Before_Genesis",
    2: "4-The_Watchers_and_Nephilim",
    3: "5-The_Enigma_of_Melchizedek",
    4: "6-The_Stargate_of_Babel_Nimrod",
    5: "7-The_Curse_of_Ham_and_Canaan",
    6: "8-Jacobs_Midnight_Duel_Peniel",
    7: "9-The_Covenant_of_Pieces",
    8: "10-The_Seraph_and_the_Garden",
    9: "11-The_Red_Heifer_Third_Temple",
    10: "12-The_Giants_of_Bashan_Og",
    11: "13-Ezekiels_Merkabah_Ophanim",
    12: "14-The_Witch_of_Endor",
    13: "15-The_Demon_Azazel",
    14: "16-The_King_of_Tyre_Cherub",
    15: "17-The_Resurrection_of_Dry_Bones",
    16: "18-The_War_for_Persia_Michael",
    17: "19-The_Transfiguration_Mount_Hermon",
    18: "20-The_Four_Horsemen_Apocalypse",
    19: "21-The_Lost_Ark_Jeremiahs_Vault",
    20: "22-The_24_Elders_Sea_of_Glass",
    21: "23-The_Two_Witnesses_Enoch_Elijah",
    22: "24-The_War_in_Heaven_Dragon",
    23: "25-The_New_Jerusalem_Hypercube",
    24: "1-David_and_Goliath",
    25: "2-Noahs_Ark"
}

# =============================================================================
# PRONUNCIATION / PHONETIC OVERRIDES
# =============================================================================
PRONUNCIATION_MAP = {
    "Tetelestai": "Teh-tell-es-tie",
    "Ruach Elohim": "Roo-ahk Elohim",
    "Ruach": "Roo-ahk",
    "Bara": "Bah-rah",
    "Asah": "ah-SAH",
    "Merachefet": "meh-rah-KHEH-fet",
    "Yehi Or": "yeh-HEE OR",
    "Imago Dei": "ee-MAH-goh DAY-ee",
    "Logos": "LOH-goss",
    "Shemesh": "sheh-MESH",
    "Yareach": "yah-RAY-akh",
    "Tselem": "TSEH-lem",
    "Demut": "deh-MOOT",
    "Shabbat": "shah-BAHT",
    "Naaman": "Nay-man",
    "Elisha": "Ee-lye-sha",
    "Yam Suph": "Yahm Soof",
    "Melchizedek": "Mel-kiz-eh-dek",
    "Malki-Tzedek": "mahl-kee-TZEH-dek",
    "Nephilim": "Nef-ih-lim",
    "Tamim": "Tah-meem",
    "bene elohim": "beh-nay elohim",
    "Benei Elohim": "beh-nay elohim",
    "graves": "grayvz",
    "Shekinah": "sheh-KYE-nuh",
    "2 Kings": "Second Kings",
    "1 Kings": "First Kings",
    "1 Corinthians": "First Corinthians",
    "2 Corinthians": "Second Corinthians",
    "1 Samuel": "First Samuel",
    "2 Samuel": "Second Samuel",
    "1 Chronicles": "First Chronicles",
    "2 Chronicles": "Second Chronicles",
    "Baal": "BAY-uhl",
    "Bereshit": "beh-reh-SHEET",
    "Elohim": "eh-loh-HEEM",
    "Tohu wa-Bohu": "TOH-hoo wah-BOH-hoo",
    "Tohu wa Bohu": "TOH-hoo wah-BOH-hoo",
    "Heylel": "hay-LEL",
    "phosteres": "foss-TEH-rays",
    "tanninim": "tah-nee-NEEM",
    "shavat": "shah-VAHT",
    "vayehi": "vah-yeh-HEE",
    "yom echad": "yohm eh-KHAHD",
    "maor": "mah-OHR",
    "moadim": "moh-ah-DEEM",
    "Shamash": "shah-MAHSH",
    "katelaben": "kah-TEH-lah-ben",
    "Nisan": "nee-SAHN",
    "1 John": "First John",
    "2 John": "Second John",
    "3 John": "Third John",
    "Qayin": "KAH-yeen",
    "qanah": "kah-NAH",
    "Hevel": "HEH-vel",
    "havalim": "hah-vah-LEEM",
    "minchah": "min-KHAH",
    "robets": "roh-VETS",
    "rabisu": "rah-BEE-soo",
    "teshuqah": "tesh-oo-KAH",
    "shamar": "shah-MAR",
    "demei": "deh-MAY",
    "damim": "dah-MEEM",
    "na va nad": "nah vah NAHD",
    "avon": "ah-VOHN",
    "Mishnah": "MEESH-nah",
    "Sanhedrin": "san-HEH-drin",
    "Jehoiada": "jeh-HOY-ah-dah",
    "Septuagint": "SEP-too-ah-jint",
    "ben Shachar": "ben shah-KHAHR",
    "Tehom": "teh-HOHM",
    "Anakim": "AN-uh-keem",
    "Rephaim": "reh-fah-EEM",
    "Og of Bashan": "AHG of bah-SHAHN",
    "El Elyon": "el el-YOHN",
    "Salem": "sah-LEM",
    "Shemhazai": "shem-hah-ZYE",
    "Azazel": "ah-zah-ZEL",
    "Tartarus": "tar-tah-ROOS",
    "Qumran": "koom-RAHN",
    "Apkallu": "ap-KAH-loo",
    "Protoevangelium": "pro-toh-ee-van-JEH-lee-um",
    "Etemenanki": "eh-teh-meh-nahn-kee",
    "Bab-Ilu": "bahb EE-loo",
    "Rujm el-Hiri": "rooj-m el HEER-ee"
}

ACRONYMS = {"USA", "UK", "DNA", "BC", "AD", "B.C.", "A.D.", "AI"}

# =============================================================================
# BOOKS / MERCH LINE & STALE-VOICE DETECTION
# =============================================================================
# Every video points to the books. Older wordings are upgraded and a missing line is added at render time.
BOOKS_LINE = ("If this blew your mind, it's just one part of what we uncover in our books. "
              "They're linked in the bio and comments, along with our sacred art merch.")
OLD_BOOKS_LINES = (
    "If this study opened your eyes, go deeper. Our books and sacred art merch are linked in the bio and comments.",
    "Our books and sacred art merch are linked in the bio and comments.",
)
CLOSING_LINE_RE = re.compile(r"(?:Until next time|Thank you for watching|Thanks for watching|Follow for more secrets)",
                             re.IGNORECASE)


def ensure_books_cta(narration: str) -> str:
    """Upgrades an older books/merch line, or adds the current one before the closing line (or at the end)."""
    for old in OLD_BOOKS_LINES:
        narration = narration.replace(old, BOOKS_LINE)
    if "linked in the bio and comments" in narration:
        return narration
    closing = None
    for closing in CLOSING_LINE_RE.finditer(narration):
        pass
    if closing and closing.start() >= len(narration) * 0.75:
        return narration[:closing.start()] + BOOKS_LINE + " " + narration[closing.start():]
    return narration.rstrip() + " " + BOOKS_LINE


def retire_stale_audio(temp_dir, paths):
    """Moves an outdated recording (and everything derived from it) to temp/_previous, keeping one generation."""
    prev = Path(temp_dir) / "_previous"
    if prev.exists():
        shutil.rmtree(prev, ignore_errors=True)
    prev.mkdir(parents=True, exist_ok=True)
    for p in map(Path, paths):
        if p.exists():
            shutil.move(str(p), str(prev / p.name))


def cached_script_differs(script_file, voice_script: str) -> bool:
    """True when a cached recording was made from a different script (or pronunciation map) than the current one."""
    script_file = Path(script_file)
    if not script_file.exists():
        return False
    return script_file.read_text(encoding="utf-8", errors="replace").strip() != voice_script.strip()


def prepare_voice_script(text, pron_map=None):
    if pron_map is None:
        pron_map = PRONUNCIATION_MAP
    modified = text
    for orig, phonetic in pron_map.items():
        pattern = r"\b" + re.escape(orig) + r"\b"
        modified = re.sub(pattern, phonetic, modified, flags=re.IGNORECASE)

    modified = re.sub(r'(\d+):(\d+)', r'\1, \2', modified)
    modified = re.sub(r'\s*[—–]\s*', ', ', modified)
    modified = re.sub(r'\s+-\s+', ', ', modified)
    modified = modified.replace("'", "").replace('"', "")

    def fix_all_caps(match):
        w = match.group(0)
        if w in ACRONYMS: return w
        if w == "GOD": return "God"
        if w == "LORD": return "Lord"
        return w.capitalize() if len(w) <= 3 else w.lower()

    modified = re.sub(r'\b[A-Z]{2,}\b', fix_all_caps, modified)
    modified = re.sub(r'\bGOD\b', 'God', modified)
    modified = re.sub(r',\s*,+', ',', modified)
    modified = re.sub(r'\s+', ' ', modified).strip()
    return modified

# =============================================================================
# 16:9 KEN BURNS MOTION PRESETS
# =============================================================================
MOTION_PRESETS = [
    {"type": "slow_push_in", "start_zoom": 1.0, "end_zoom": 1.15, "pan_y": (0.5, 0.42), "pan_x": (0.5, 0.5)},
    {"type": "dramatic_punch_in", "start_zoom": 1.02, "end_zoom": 1.18, "pan_y": (0.46, 0.40), "pan_x": (0.5, 0.5)},
    {"type": "tilt_up", "start_zoom": 1.05, "end_zoom": 1.16, "pan_y": (0.65, 0.38), "pan_x": (0.5, 0.5)},
    {"type": "intense_zoom", "start_zoom": 1.0, "end_zoom": 1.22, "pan_y": (0.45, 0.45), "pan_x": (0.5, 0.5)},
    {"type": "pan_down_collapse", "start_zoom": 1.05, "end_zoom": 1.16, "pan_y": (0.35, 0.65), "pan_x": (0.5, 0.5)},
    {"type": "slow_pull_back", "start_zoom": 1.16, "end_zoom": 1.02, "pan_y": (0.5, 0.5), "pan_x": (0.5, 0.5)},
    {"type": "pan_left_to_right", "start_zoom": 1.08, "end_zoom": 1.12, "pan_y": (0.5, 0.5), "pan_x": (0.4, 0.6)}
]

def build_scene_prompt_16x9(sentence: str, title: str = "") -> str:
    s = sentence.strip()
    kw = s.lower()
    style = "dark atmospheric lighting, ancient biblical mystery aesthetic, photorealistic, cinematic composition, 8k resolution, divine golden light"

    if any(w in kw for w in ["open his gospel", "exact same words", "literary coincidence", "accident"]):
        scene = "reverent Apostle John in coarse linen robe writing with reed quill on ancient papyrus scroll in candlelit stone room overlooking Mediterranean Sea at twilight"
    elif any(w in kw for w in ["genesis 1", "tohu wa-bohu", "formless and void", "waters of the deep", "merachefet"]):
        scene = "primordial cosmic ocean of Genesis 1, swirling dark deep waters illuminated by celestial golden luminescence, hovering Holy Spirit aura"
    elif any(w in kw for w in ["let there be light", "yehi or", "fiat lux", "uncreated light"]):
        scene = "explosive cosmic birth of holy uncreated light shattering dark primeval void, divine blinding golden rays piercing cosmic storm clouds"
    elif any(w in kw for w in ["six-day", "cosmic temple", "inauguration", "firmament", "heavens"]):
        scene = "majestic celestial dome and cosmic temple arches overlooking newborn Earth with glowing continents, crystal blue oceans, and golden horizons"
    elif any(w in kw for w in ["divine council", "heavenly council", "council of god", "bene elohim", "benei elohim", "assembly of the holy"]):
        scene = "grand heavenly throne room of the Divine Council, golden light rays, celestial thrones surrounded by radiant winged seraphim and shining angelic dignitaries"
    elif any(w in kw for w in ["morning stars", "sang together", "job 38", "cornerstone of the earth", "foundations of the earth", "footings fastened"]):
        scene = "celestial host of glowing morning stars singing in cosmic harmony as golden foundations and pillars of planet Earth are set in deep starry space"
    elif any(w in kw for w in ["lucifer", "heylel", "shining one", "son of the morning", "day star"]):
        scene = "radiant archangel Lucifer in dazzling light before the fall, shimmering multi-faceted wings adorned with rubies, emeralds, and golden light, standing in heavenly court"
    elif any(w in kw for w in ["ezekiel 28", "anointed cherub", "holy mountain of god", "stones of fire", "walked up and down"]):
        scene = "majestic anointed covering cherub with outstretched luminous wings walking upon the cosmic mountain of God amongst radiant incandescent glowing stones of fire"
    elif any(w in kw for w in ["isaiah 14", "five i wills", "ascend into heaven", "exalt my throne", "mount of assembly", "sides of the north"]):
        scene = "sovereign cosmic peak of the Mount of Assembly in the far north of heaven, celestial throne encircled by nebulae and holy stars of God"
    elif any(w in kw for w in ["iniquity was found", "pride", "corrupted your wisdom", "splendor", "rebellion in heaven"]):
        scene = "dramatic spiritual shift in heaven, radiant cherub harboring dark prideful shadow within golden heart, solemn celestial beings witnessing the unspoken rebellion"
    elif any(w in kw for w in ["cast down", "fall like lightning", "expelled from heaven", "cast you to the earth", "dragon swept"]):
        scene = "epic cosmic catastrophe as rebellious celestial beings fall from radiant heavenly heights like searing bolts of lightning into dark abyssal cosmos"
    elif any(w in kw for w in ["michael", "war in heaven", "dragon and his angels", "warrior angel", "archangel"]):
        scene = "Archangel Michael in brilliant heavenly silver and gold armor wielding a sword of pure divine fire during the epic celestial war in starry heaven"
    elif any(w in kw for w in ["let us make man", "imago dei", "trinitarian council", "image of god", "tselem"]):
        scene = "divine council in heavenly throne room surrounded by majestic winged seraphim, beams of radiant transcendent light shaping sacred human soul"
    elif any(w in kw for w in ["sabbath", "day seven", "rest of christ", "shabbat", "finished"]):
        scene = "Christ triumphant in glowing ivory and gold robes looking over serene cosmic paradise of Eden, peaceful golden sunset and crystal river"
    elif any(w in kw for w in ["watchers", "nephilim", "incursion", "hermon"]):
        scene = "colossal glowing celestial beings descending onto the snowy crags of Mount Hermon at twilight, dramatic purple thunderclouds"
    elif any(w in kw for w in ["melchizedek", "salem", "bread and wine", "abraham"]):
        scene = "high priest Melchizedek in radiant priestly vestments offering bread and silver chalice of wine to Abraham on ancient Jerusalem ridge"
    elif any(w in kw for w in ["babel", "nimrod", "stargate", "ziggurat", "tower"]):
        scene = "towering ancient Mesopotamian ziggurat reaching into swirling starry cosmic vortex, thousands of ancient laborers by torchlight"
    elif any(w in kw for w in ["cross", "calvary", "crucifixion", "tetelestai", "it is finished"]):
        scene = "dramatic silhouette of the holy cross atop Mount Calvary against stormy twilight skies, divine golden celestial rays breaking through"
    elif any(w in kw for w in ["ark of the covenant", "mercy seat", "cherubim", "holy of holies"]):
        scene = "the sacred golden Ark of the Covenant with glowing cherubim wings touching in the ancient candlelit Holy of Holies, Shekinah smoke"
    elif any(w in kw for w in ["principalities", "powers", "rulers", "thrones", "dominions", "heavenly hierarchy"]):
        scene = "visionary depiction of colossal celestial hierarchies and spiritual rulers reigning over cosmic spheres, rings of golden seraphic fire"
    elif any(w in kw for w in ["slain lamb", "covenant", "before the foundation", "eternity past", "logos"]):
        scene = "the pre-incarnate radiant Christ standing at the center of eternal divine light, timeless cosmic mystery before the creation of the universe"
    else:
        clean_words = [w for w in re.sub(r'[^\w\s]', '', s).split() if len(w) > 3 and w.lower() not in ["this", "that", "with", "from", "they", "were", "been", "have", "would", "could", "should", "there", "their", "about", "which", "bible", "secrets", "revealed", "master", "documentary", "hidden", "episode", "chapter", "script", "runtime", "voice"]]
        kw_phrase = " ".join(clean_words[:6])
        scene = f"dramatic ancient biblical revelation illustrating {kw_phrase}, sacred Hebrew atmosphere, dramatic clouds, shafts of celestial light"

    return f"cinematic 16:9 shot, {scene}, {style}"

# =============================================================================
# COMFYUI SERVER & FLUX 16:9 GENERATOR
# =============================================================================
def is_comfyui_running(url=COMFY_URL) -> bool:
    try:
        req = urllib.request.Request(f"{url}/system_stats")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            return resp.status == 200
    except Exception:
        return False

def ensure_comfyui_running(url=COMFY_URL, max_wait_sec=240) -> bool:
    if is_comfyui_running(url):
        return True
    print("\n[ComfyUI] Server offline. Auto-launching in background...", flush=True)
    comfy_main = os.path.join(COMFY_DIR, "main.py")
    if not (os.path.exists(COMFY_PYTHON) and os.path.exists(comfy_main)):
        print(f"[ComfyUI Warning] Missing executable or main.py at: {COMFY_DIR}", flush=True)
        return False
    cmd = [COMFY_PYTHON, comfy_main, "--listen", "127.0.0.1", "--port", "8188", "--lowvram"]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
    subprocess.Popen(cmd, cwd=COMFY_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    start_time = time.time()
    while time.time() - start_time < max_wait_sec:
        time.sleep(2)
        if is_comfyui_running(url):
            print(f"[ComfyUI] Server online in {time.time()-start_time:.1f}s\n", flush=True)
            return True
    print(f"[ComfyUI Notice] Timed out after {max_wait_sec}s waiting for the server.", flush=True)
    return False

def build_flux_workflow_16x9(prompt_text, width=FLUX_WIDTH, height=FLUX_HEIGHT, steps=4, seed=None):
    if seed is None:
        import random
        seed = random.randint(100000, 999999999)
    return {
        "1": {"inputs": {"unet_name": "flux1-schnell-Q3_K_S.gguf"}, "class_type": "UnetLoaderGGUF"},
        "2": {"inputs": {"clip_name1": "t5xxl_fp8_e4m3fn.safetensors", "clip_name2": "clip_l.safetensors", "type": "flux"}, "class_type": "DualCLIPLoader"},
        "3": {"inputs": {"vae_name": "ae.safetensors"}, "class_type": "VAELoader"},
        "4": {"inputs": {"text": prompt_text, "clip": ["2", 0]}, "class_type": "CLIPTextEncode"},
        "5": {"inputs": {"text": "", "clip": ["2", 0]}, "class_type": "CLIPTextEncode"},
        "6": {"inputs": {"width": width, "height": height, "batch_size": 1}, "class_type": "EmptySD3LatentImage"},
        "7": {
            "inputs": {
                "seed": seed, "steps": steps, "cfg": 1.0, "sampler_name": "euler",
                "scheduler": "simple", "denoise": 1.0, "model": ["1", 0],
                "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0]
            },
            "class_type": "KSampler"
        },
        "8": {"inputs": {"samples": ["7", 0], "vae": ["3", 0]}, "class_type": "VAEDecode"},
        "9": {"inputs": {"filename_prefix": "Doc_16x9_Scene", "images": ["8", 0]}, "class_type": "SaveImage"}
    }

def generate_flux_image_16x9(prompt_text: str, scene_id: str, target_file: Path) -> Path:
    target_file = Path(target_file)
    target_file.parent.mkdir(parents=True, exist_ok=True)

    if not is_comfyui_running():
        ensure_comfyui_running()

    if is_comfyui_running():
        # Submit generation workflow
        try:
            print(f"  [FLUX 16:9] Generating {scene_id} via ComfyUI: \"{prompt_text[:65]}...\"", flush=True)
            workflow = build_flux_workflow_16x9(prompt_text)
            data = json.dumps({"prompt": workflow}).encode("utf-8")
            req = urllib.request.Request(f"{COMFY_URL}/prompt", data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                prompt_id = res["prompt_id"]

            t0 = time.time()
            for wait_i in range(120):
                time.sleep(2.5)
                if wait_i > 0 and wait_i % 6 == 0:
                    print(f"    ... rendering {scene_id} ({int(time.time() - t0)}s elapsed)", flush=True)
                with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}") as resp:
                    history = json.loads(resp.read().decode("utf-8"))
                    if prompt_id in history:
                        outputs = history[prompt_id].get("outputs", {})
                        if "9" in outputs and outputs["9"].get("images"):
                            info = outputs["9"]["images"][0]
                            src_on_disk = os.path.join(COMFY_OUTPUT_DIR, info["filename"])
                            if os.path.exists(src_on_disk):
                                shutil.copy2(src_on_disk, str(target_file))
                            else:
                                url = f"{COMFY_URL}/view?filename={info['filename']}&subfolder={info.get('subfolder', '')}&type={info.get('type', 'output')}"
                                urllib.request.urlretrieve(url, str(target_file))

                            if target_file.exists() and target_file.stat().st_size > 40000:
                                print(f"  ✔ [FLUX Saved] {scene_id}.png in {time.time()-t0:.1f}s ({target_file.stat().st_size // 1024} KB)", flush=True)
                                return target_file
        except Exception as e:
            print(f"  [FLUX Notice] ComfyUI submission skipped for {scene_id}: {e}", flush=True)

    # No placeholder images: a cached placeholder would be reused by every later render
    raise RuntimeError(f"ComfyUI could not generate scene {scene_id} (is it running at http://127.0.0.1:8188?). No placeholder was saved: start ComfyUI and run the render again; finished scenes are kept.")

# =============================================================================
# SCRIPT PARSER & 16:9 SCENE CHOREOGRAPHY
# =============================================================================

# Script headers and production notes ("BIBLE HIDDEN SECRETS REVEALED — 16:9 MASTER DOCUMENTARY SCRIPT",
# "EPISODE: ...", "TARGET RUNTIME: ...", "Heylel -> hay-LEL") must never be narrated or captioned
SCRIPT_HEADER_RE = re.compile(
    r"^(?:BIBLE HIDDEN SECRETS REVEALED\b|.*MASTER DOCUMENTARY SCRIPT|EPISODE\s*(?:\d+\s*[—–-]|:)"
    r"|(?:TITLE|TOPIC|WEEK|REEL|DURATION|FORMAT|VOICEOVER|VOICE|PROJECT|RUNTIME TARGET|TARGET RUNTIME|CADENCE)\s*:"
    r"|PRONUNCIATION\b)"
)
PRONUNCIATION_LINE_RE = re.compile(r"^\S.{0,40}?\s+->\s+\S")
NARRATOR_LABEL_RE = re.compile(r"^\*{0,2}Narrator\*{0,2}\s*:\s*\*{0,2}\s*", re.IGNORECASE)


def is_script_header_line(s: str) -> bool:
    return bool(SCRIPT_HEADER_RE.match(s) or PRONUNCIATION_LINE_RE.match(s))


def strip_narrator_label(s: str) -> str:
    return NARRATOR_LABEL_RE.sub("", s).replace("**", "")

def parse_episode_folder(ep_dir):
    ep_p = Path(ep_dir)
    candidates = [
        ep_p / "script_35min.txt",
        ep_p / "script_30min.txt",
        ep_p / "script.txt",
        ep_p / "script.md",
        ep_p / "narration_script.txt"
    ]
    raw_content = ""
    for c in candidates:
        if c.exists():
            raw_content = c.read_text(encoding="utf-8", errors="replace")
            break

    if not raw_content:
        raise FileNotFoundError(f"No script file found in {ep_dir}")

    # Extract clean narration text
    lines = raw_content.splitlines()
    has_narr_marker = any(re.search(r'NARRATION\s+SCRIPT', l, re.IGNORECASE) for l in lines)
    in_narration = not has_narr_marker
    narr_lines = []

    for line in lines:
        s = line.strip()
        if not s:
            continue
        if re.search(r'NARRATION\s+SCRIPT', s, re.IGNORECASE):
            in_narration = True
            continue
        if not in_narration:
            continue
        if re.match(r'^(WORD COUNT|SOURCES|METADATA|HASHTAGS|TAGS|NOTES):?', s, re.IGNORECASE):
            break
        if re.match(r'^[=\-_~*]{3,}$', s):
            continue
        if re.match(r'^\[.*?\]$', s) or re.match(r'^\(.*?\)$', s):
            continue
        if "CALL TO ACTION" in s or is_script_header_line(s):
            continue

        cleaned = re.sub(r'\[CHAPTER \d+ [—\-] [^\]]+\]', '', strip_narrator_label(s))
        cleaned = re.sub(r'\[.*?\]', '', cleaned)
        cleaned = re.sub(r'\(.*?\)', '', cleaned).strip()
        if cleaned:
            narr_lines.append(cleaned)

    if not narr_lines:
        # Fallback if no narration marker or empty
        for line in lines:
            s = line.strip()
            if not s or re.match(r'^[=\-_~*]{3,}$', s):
                continue
            if re.match(r'^(BIBLE HIDDEN SECRETS|EPISODE:|TARGET RUNTIME:|CADENCE:|VOICE:|WORD COUNT|SOURCES|METADATA|HASHTAGS|TAGS|NOTES):?', s, re.IGNORECASE):
                continue
            if re.match(r'^\[.*?\]$', s) or re.match(r'^\(.*?\)$', s) or is_script_header_line(s):
                continue
            cleaned = re.sub(r'\[.*?\]', '', strip_narrator_label(s))
            cleaned = re.sub(r'\(.*?\)', '', cleaned).strip()
            if cleaned:
                narr_lines.append(cleaned)

    full_narrative = " ".join(narr_lines)
    full_narrative = re.sub(r'\s+', ' ', full_narrative).strip()

    # Look for existing prompts json
    prompts_json_p = ep_p / "prompts_78_scenes.json"
    if not prompts_json_p.exists():
        prompts_json_p = ep_p / "visual_cues.json"

    scenes = []
    if prompts_json_p.exists():
        try:
            p_data = json.loads(prompts_json_p.read_text(encoding="utf-8"))
            if isinstance(p_data, list) and len(p_data) >= 10:
                for idx, item in enumerate(p_data):
                    sid = item.get("id") or f"scene_{idx+1:02d}"
                    prompt = item.get("prompt") or item.get("description", "")
                    weight = float(item.get("weight", 1.0))
                    motion = item.get("motion") or MOTION_PRESETS[idx % len(MOTION_PRESETS)]
                    scenes.append({
                        "id": sid,
                        "prompt": prompt,
                        "weight": weight,
                        "motion": motion
                    })
        except Exception:
            scenes = []

    # If no pre-existing prompts JSON (or less than 10 scenes), construct 40-78 scenes dynamically
    if not scenes:
        raw_sents = re.split(r'(?<=[.!?])\s+', full_narrative)
        sents = [s.strip() for s in raw_sents if len(s.strip()) > 8]

        # Group into pairs or individual sentences to achieve 40-78 scenes
        group_size = 2 if len(sents) >= 70 else 1
        for i in range(0, len(sents), group_size):
            chunk = sents[i:i + group_size]
            chunk_text = " ".join(chunk)
            sid = f"scene_{len(scenes)+1:02d}"
            prompt = build_scene_prompt_16x9(chunk_text)
            w = max(1.0, len(chunk_text.split()) / 12.0)
            scenes.append({
                "id": sid,
                "prompt": prompt,
                "weight": w,
                "motion": MOTION_PRESETS[len(scenes) % len(MOTION_PRESETS)]
            })

        # Save generated prompts so they can be reviewed and reused
        out_prompts_file = ep_p / "prompts_78_scenes.json"
        try:
            out_prompts_file.write_text(json.dumps([{"id": s["id"], "prompt": s["prompt"]} for s in scenes], indent=2), encoding="utf-8")
        except Exception:
            pass

    return full_narrative, scenes

# =============================================================================
# IMAGE VERIFIER & MULTI-SOURCE RETRIEVER
# =============================================================================
def ensure_scene_images(scenes, ep_dir, ep_num):
    images_dir = Path(ep_dir) / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    images_paths = {}

    bhrs_folder_name = BHSR_EPISODE_MAP.get(ep_num)
    bhrs_cand_dirs = []
    if bhrs_folder_name:
        bhrs_cand_dirs.append(BHSR_YOUTUBE_DIR / bhrs_folder_name / "images")
        bhrs_cand_dirs.append(BHSR_ROOT / "legacy_numbered_assets_backup" / bhrs_folder_name / "images")

    missing = []
    for s in scenes:
        sid = s["id"]
        local_p = images_dir / f"{sid}.png"
        if local_p.exists() and local_p.stat().st_size > 40000:
            images_paths[sid] = str(local_p)
            continue

        # Check BHSR-Youtube / legacy backups
        copied = False
        for b_dir in bhrs_cand_dirs:
            if b_dir.exists():
                src_p = b_dir / f"{sid}.png"
                if src_p.exists() and src_p.stat().st_size > 40000:
                    shutil.copy2(src_p, local_p)
                    images_paths[sid] = str(local_p)
                    copied = True
                    break

        if not copied:
            missing.append(s)

    if missing:
        print(f"  [FLUX Pipeline] Generating {len(missing)} missing 16:9 scenes for Episode {ep_num}...", flush=True)
        for s in missing:
            sid = s["id"]
            local_p = images_dir / f"{sid}.png"
            gen_p = generate_flux_image_16x9(s["prompt"], sid, local_p)
            images_paths[sid] = str(gen_p)

    print(f"  ✔ [Images Ready] {len(images_paths)}/{len(scenes)} 16:9 scenes ready in: {images_dir}", flush=True)
    return images_paths

# =============================================================================
# VOICE SYNTHESIS, TIMESTAMPS & MASTER AUDIO MIXING
# =============================================================================
def generate_speech_and_timestamps(narration_text, temp_dir, ep_prefix, speed=1.0, force_rebuild=False):
    import whisper
    import torch

    temp_p = Path(temp_dir)
    temp_p.mkdir(parents=True, exist_ok=True)

    raw_voice_path = str(temp_p / f"{ep_prefix}_voice_raw.mp3")
    transcript_path = str(temp_p / f"{ep_prefix}_transcript.json")
    soundtrack_path = str(temp_p / f"{ep_prefix}_master_audio.wav")

    # 1. Voice Synthesis (VibeVoice with Edge-TTS Fallback)
    voice_script = prepare_voice_script(narration_text, PRONUNCIATION_MAP)
    voice_script_file = str(temp_p / "voice_script.txt")
    if not force_rebuild and (os.path.exists(raw_voice_path) or os.path.exists(soundtrack_path)) \
            and cached_script_differs(voice_script_file, voice_script):
        print("[Voiceover] The script changed since the cached recording: re-recording the narration "
              "(old audio kept in temp/_previous).", flush=True)
        retire_stale_audio(temp_p, [raw_voice_path, raw_voice_path + "_chunks", transcript_path, soundtrack_path])
    voice_needed = force_rebuild or not (os.path.exists(raw_voice_path) or os.path.exists(soundtrack_path))
    if voice_needed:
        total_words = len(narration_text.split())
        print(f"\n=== Synthesizing Full Narration with VibeVoice ({total_words} words, {speed}x pace) ===", flush=True)
        with open(voice_script_file, "w", encoding="utf-8") as f:
            f.write(voice_script)

        vv_success = False
        if os.path.exists(VIBEVOICE_PYTHON) and os.path.exists(VIBEVOICE_SCRIPT):
            try:
                cmd = [
                    VIBEVOICE_PYTHON, "-u", VIBEVOICE_SCRIPT,
                    "--text_file", voice_script_file,
                    "--output", raw_voice_path,
                    "--voice_pt", DEFAULT_VOICE_PT,
                    "--steps", "5",
                    "--speed", str(speed)
                ]
                cf = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
                res = subprocess.run(cmd, check=True, creationflags=cf)
                if os.path.exists(raw_voice_path) and os.path.getsize(raw_voice_path) > 10000:
                    vv_success = True
                    print(f"[VibeVoice Complete] Master voice saved: {raw_voice_path} ({os.path.getsize(raw_voice_path)/1024/1024:.2f} MB)", flush=True)
            except Exception as e:
                print(f"[VibeVoice Warning] VibeVoice synthesis failed ({e}). Falling back to Edge-TTS...", flush=True)

        if not vv_success:
            print("[Edge-TTS Fallback] Synthesizing speech with Microsoft Christopher...", flush=True)
            try:
                import edge_tts
                import asyncio
                async def _run_edge():
                    communicate = edge_tts.Communicate(voice_script, "en-US-ChristopherNeural", rate=f"{int((speed-1.0)*100):+d}%")
                    await communicate.save(raw_voice_path)
                asyncio.run(_run_edge())
                print(f"[Edge-TTS Complete] Voice file saved: {raw_voice_path}", flush=True)
            except Exception as e:
                # Direct CLI fallback
                edge_cmd = ["edge-tts", "--voice", "en-US-ChristopherNeural", "--file", voice_script_file, "--write-media", raw_voice_path]
                subprocess.run(edge_cmd, check=True)
    else:
        print(f"[Voiceover] Using pre-synthesized audio: {raw_voice_path if os.path.exists(raw_voice_path) else soundtrack_path}", flush=True)

    # 2. Whisper Alignment
    audio_for_whisper = raw_voice_path if os.path.exists(raw_voice_path) else soundtrack_path
    if force_rebuild or not os.path.exists(transcript_path):
        print("\n=== Transcribing Full Audio with Whisper ===", flush=True)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Whisper device: {device}", flush=True)
        model = whisper.load_model("base", device=device)
        transcript_result = model.transcribe(audio_for_whisper, word_timestamps=True, fp16=(device=="cuda"))
        with open(transcript_path, "w", encoding="utf-8") as f:
            json.dump(transcript_result, f, indent=2)
        del model
        import gc
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    else:
        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript_result = json.load(f)

    total_duration = transcript_result["segments"][-1]["end"]
    print(f"Audio Duration: {total_duration:.2f}s ({total_duration/60:.2f} mins) across {len(transcript_result['segments'])} segments.", flush=True)

    # 3. Master voice track: narration only, no background music (music beds caused copyright claims)
    if force_rebuild or not os.path.exists(soundtrack_path):
        print("\n=== Mastering Voiceover (voice only, no music) ===", flush=True)
        master_cmd = [
            FFMPEG_EXE, "-y",
            "-hide_banner", "-loglevel", "error",
            "-i", raw_voice_path,
            "-filter_complex", f"[0:a]{VOICE_MASTER_CHAIN},loudnorm=I=-11.5:TP=-0.5:LRA=5[out]",
            "-map", "[out]", "-ar", "44100",
            soundtrack_path
        ]
        cf = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
        subprocess.run(master_cmd, check=True, creationflags=cf)
        print(f"[Audio] Voice master ready: {soundtrack_path}", flush=True)
    else:
        print(f"[Audio] Master soundtrack ready: {soundtrack_path}", flush=True)

    return soundtrack_path, transcript_path, total_duration

# =============================================================================
# 16:9 CAPTION CHUNKING & DYNAMIC MOTION
# =============================================================================
def align_transcript_with_script(script_text, whisper_words):
    def _clean(tok):
        return re.sub(r'[^\w]', '', tok.lower())

    script_tokens = script_text.split()
    clean_script = [_clean(t) for t in script_tokens]
    clean_whisper = [_clean(w["word"]) for w in whisper_words]

    matcher = difflib.SequenceMatcher(None, clean_script, clean_whisper)
    aligned = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for si, wj in zip(range(i1, i2), range(j1, j2)):
                aligned.append({
                    "word": script_tokens[si],
                    "start": whisper_words[wj]["start"],
                    "end": whisper_words[wj]["end"],
                    "status": "exact"
                })
        elif tag == 'replace':
            num_s = i2 - i1
            w_start = whisper_words[j1]["start"]
            w_end = whisper_words[j2-1]["end"]
            dur = (w_end - w_start) / max(num_s, 1)
            for idx, si in enumerate(range(i1, i2)):
                aligned.append({
                    "word": script_tokens[si],
                    "start": round(w_start + idx * dur, 2),
                    "end": round(w_start + (idx + 1) * dur, 2),
                    "status": "corrected"
                })
        elif tag == 'delete':
            prev_end = aligned[-1]["end"] if aligned else 0.0
            next_start = whisper_words[j1]["start"] if j1 < len(whisper_words) else prev_end + 0.3
            num_s = i2 - i1
            dur = max(0.1, (next_start - prev_end) / max(num_s, 1))
            for idx, si in enumerate(range(i1, i2)):
                aligned.append({
                    "word": script_tokens[si],
                    "start": round(prev_end + idx * dur, 2),
                    "end": round(prev_end + (idx + 1) * dur, 2),
                    "status": "interpolated"
                })

    return aligned

def load_chunked_captions_16x9(script_text, transcript_path, max_words=6):
    with open(transcript_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    all_raw_words = []
    for seg in data.get("segments", []):
        for w in seg.get("words", []):
            all_raw_words.append({"word": w["word"].strip(), "start": w["start"], "end": w["end"]})

    aligned_words = align_transcript_with_script(script_text, all_raw_words)

    max_chunk_width = 1300
    word_spacing = 18
    try:
        font_word = ImageFont.truetype("arialbd.ttf", 64)
    except Exception:
        font_word = ImageFont.load_default()

    dummy_img = Image.new("RGB", (VIDEO_WIDTH, VIDEO_HEIGHT))
    draw = ImageDraw.Draw(dummy_img)

    chunks = []
    curr_chunk = []
    curr_w = 0

    for w in aligned_words:
        w_len = draw.textlength(w["word"], font=font_word)
        prev_ended = False
        if curr_chunk:
            last_w = re.sub(r'[^\w.!?]+$', '', curr_chunk[-1]["word"].strip())
            if last_w.endswith(('.', '!', '?')) and not re.search(r' (?:vs|dr|mr|mrs|ms|gen|exod|lev|num|deut)\.$', last_w, re.IGNORECASE):
                prev_ended = True

        if curr_chunk and (prev_ended or len(curr_chunk) >= max_words or (curr_w + word_spacing + w_len) > max_chunk_width):
            chunks.append({
                "start": curr_chunk[0]["start"],
                "end": curr_chunk[-1]["end"],
                "words": [{"word": x["word"].strip(), "start": x["start"], "end": x["end"]} for x in curr_chunk]
            })
            curr_chunk = [w]
            curr_w = w_len
        else:
            curr_chunk.append(w)
            curr_w += (word_spacing if len(curr_chunk) > 1 else 0) + w_len

    if curr_chunk:
        chunks.append({
            "start": curr_chunk[0]["start"],
            "end": curr_chunk[-1]["end"],
            "words": [{"word": x["word"].strip(), "start": x["start"], "end": x["end"]} for x in curr_chunk]
        })
    return chunks

def apply_motion_16x9(img, motion_cfg, t_frac, out_size=(VIDEO_WIDTH, VIDEO_HEIGHT)):
    W, H = out_size
    orig_w, orig_h = img.size
    ease_t = 0.5 * (1.0 - math.cos(math.pi * t_frac))

    start_z = motion_cfg.get("start_zoom", 1.0)
    end_z = motion_cfg.get("end_zoom", 1.15)
    zoom = start_z + (end_z - start_z) * ease_t

    target_ar = W / H
    orig_ar = orig_w / orig_h

    if orig_ar >= target_ar:
        base_h = orig_h
        base_w = int(orig_h * target_ar)
    else:
        base_w = orig_w
        base_h = int(orig_w / target_ar)

    crop_w = int(base_w / zoom)
    crop_h = int(base_h / zoom)

    pan_y = motion_cfg.get("pan_y", (0.5, 0.5))
    pan_x = motion_cfg.get("pan_x", (0.5, 0.5))
    curr_py = pan_y[0] + (pan_y[1] - pan_y[0]) * ease_t
    curr_px = pan_x[0] + (pan_x[1] - pan_x[0]) * ease_t

    shift_y = int((orig_h - crop_h) * curr_py)
    shift_x = int((orig_w - crop_w) * curr_px)
    shift_x = max(0, min(orig_w - crop_w, shift_x))
    shift_y = max(0, min(orig_h - crop_h, shift_y))

    cropped = img.crop((shift_x, shift_y, shift_x + crop_w, shift_y + crop_h))
    return cropped.resize(out_size, Image.Resampling.BILINEAR)

# =============================================================================
# MULTI-CORE 4-WORKER NVENC PARALLEL RENDER WORKER
# =============================================================================
def _render_segment_worker(worker_id, s_frame, e_frame, total_frames, timeline, chunks, images_paths, local_logo_path, part_output_path, progress_list=None):
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
        except Exception:
            pass

    W, H = VIDEO_WIDTH, VIDEO_HEIGHT

    images = {}
    for sid, p in images_paths.items():
        if os.path.exists(p):
            try:
                images[sid] = Image.open(p).convert("RGB")
            except Exception:
                pass

    if not images:
        # Create an emergency canvas so worker doesn't bail
        fallback_img = Image.new("RGB", (W, H), (12, 16, 26))
        images["default"] = fallback_img

    default_img = next(iter(images.values()))

    logo_img = None
    if local_logo_path and os.path.exists(local_logo_path):
        try:
            logo_img = Image.open(local_logo_path).convert("RGBA").resize((110, 110), Image.Resampling.LANCZOS)
            r, g, b, a = logo_img.split()
            a = a.point(lambda p: int(p * 0.65))
            logo_img.putalpha(a)
        except Exception:
            pass

    try:
        font_word = ImageFont.truetype("arialbd.ttf", 66)
    except Exception:
        font_word = ImageFont.load_default()

    grad_h = int(H * 0.28)
    grad_mask = Image.new("L", (W, grad_h))
    draw_m = ImageDraw.Draw(grad_mask)
    for y in range(grad_h):
        alpha = int(190 * (y / float(grad_h)))
        draw_m.line([(0, y), (W, y)], fill=alpha)
    black_bar = Image.new("RGB", (W, grad_h), (0, 0, 0))

    cmd = [
        FFMPEG_EXE, "-y",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-s", f"{W}x{H}", "-pix_fmt", "rgb24",
        "-r", str(FPS), "-i", "-",
        "-c:v", "h264_nvenc", "-preset", "p4", "-cq", "19", "-pix_fmt", "yuv420p",
        part_output_path
    ]
    cf = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
    pipe_proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=cf)

    timeline_idx = 0
    start_t = s_frame / float(FPS)
    while timeline_idx < len(timeline) - 1 and start_t >= timeline[timeline_idx]["end"]:
        timeline_idx += 1

    chunk_idx = 0
    while chunk_idx < len(chunks) - 1 and start_t > chunks[chunk_idx]["end"] + 0.3:
        chunk_idx += 1

    dummy_img = Image.new("RGB", (1, 1))
    draw_dummy = ImageDraw.Draw(dummy_img)

    last_chunk_key = None
    cached_pill = None
    cached_pill_pos = (0, 0)
    cached_word_widths = []
    cached_start_x = 0

    for frame_idx in range(s_frame, e_frame):
        curr_time = frame_idx / float(FPS)

        while timeline_idx < len(timeline) - 1 and curr_time >= timeline[timeline_idx]["end"]:
            timeline_idx += 1
        active_scene = timeline[timeline_idx]

        scene_dur = active_scene["end"] - active_scene["start"]
        scene_t = (curr_time - active_scene["start"]) / max(scene_dur, 0.1)
        scene_t = max(0.0, min(1.0, scene_t))

        img = images.get(active_scene["id"], default_img)
        frame = apply_motion_16x9(img, active_scene["motion"], scene_t, (W, H))
        frame.paste(black_bar, (0, H - grad_h), mask=grad_mask)

        if logo_img:
            frame.paste(logo_img, (60, 50), logo_img)

        while chunk_idx < len(chunks) - 1 and curr_time > chunks[chunk_idx]["end"] + 0.3:
            chunk_idx += 1

        active_chunk = None
        for ci in range(max(0, chunk_idx - 1), min(len(chunks), chunk_idx + 2)):
            c = chunks[ci]
            if c["start"] - 0.1 <= curr_time <= c["end"] + 0.2:
                active_chunk = c
                break

        if active_chunk:
            c_words = active_chunk["words"]
            chunk_key = id(active_chunk)
            word_spacing = 18
            caption_y = int(H * 0.85)

            if last_chunk_key != chunk_key:
                last_chunk_key = chunk_key
                cached_word_widths = [draw_dummy.textlength(w["word"], font=font_word) for w in c_words]
                total_cw = sum(cached_word_widths) + word_spacing * (len(c_words) - 1)
                cached_start_x = (W - total_cw) / 2

                pill_pad_x = 32
                pill_pad_y = 16
                pill_left = max(0, int(cached_start_x - pill_pad_x))
                half_h = int(font_word.size * 0.66)
                pill_top = max(0, int(caption_y - half_h - pill_pad_y))
                pill_right = min(W, int(cached_start_x + total_cw + pill_pad_x))
                pill_bottom = min(H, int(caption_y + half_h - 4 + pill_pad_y))
                pw = pill_right - pill_left
                ph = pill_bottom - pill_top

                cached_pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
                p_draw = ImageDraw.Draw(cached_pill)
                p_draw.rounded_rectangle([(0, 0), (pw, ph)], radius=22, fill=(0, 0, 0, 165))
                cached_pill_pos = (pill_left, pill_top)

            if cached_pill:
                frame.paste(cached_pill, cached_pill_pos, cached_pill)

            draw = ImageDraw.Draw(frame)
            active_idx = -1
            for i, w in enumerate(c_words):
                if w["start"] - 0.05 <= curr_time <= w["end"] + 0.10:
                    active_idx = i
                    break

            cur_x = cached_start_x
            for i, w_obj in enumerate(c_words):
                w_str = w_obj["word"]
                w_len = cached_word_widths[i]

                if i == active_idx:
                    draw.text((cur_x, caption_y), w_str, font=font_word, fill=(255, 230, 20, 255), stroke_width=4, stroke_fill=(0, 0, 0, 255), anchor="lm")
                else:
                    draw.text((cur_x, caption_y), w_str, font=font_word, fill=(255, 255, 255, 240), stroke_width=3, stroke_fill=(0, 0, 0, 230), anchor="lm")

                cur_x += w_len + word_spacing

        pipe_proc.stdin.write(frame.tobytes())

        if (frame_idx - s_frame) % 24 == 0 and progress_list is not None:
            progress_list[worker_id] = (frame_idx - s_frame + 1)

    if progress_list is not None:
        progress_list[worker_id] = (e_frame - s_frame)

    pipe_proc.stdin.close()
    pipe_proc.wait()

# =============================================================================
# MASTER 16:9 VIDEO BUILDER
# =============================================================================
def build_16x9_video(ep_dir, ep_num=1, speed=1.0, images_only=False, force_rebuild=False):
    ep_p = Path(ep_dir).resolve()
    
    # Extract clean prefix & title
    meta_p = ep_p.parent / "metadata.json" if ep_p.name == "long_form" else ep_p / "metadata.json"
    if not meta_p.exists():
        meta_p = ep_p / "episode_metadata.json"

    ep_title = f"Week {ep_num:02d}"
    if meta_p.exists():
        try:
            m = json.loads(meta_p.read_text(encoding="utf-8"))
            ep_title = m.get("documentary", {}).get("title", ep_title)
        except Exception:
            pass

    clean_slug = re.sub(r'[^\w]+', '_', ep_title.lower()).strip('_')[:40]
    ep_prefix = f"W{ep_num:02d}_{clean_slug}"

    print("\n" + "=" * 78)
    print(f"BIBLE HIDDEN SECRETS REVEALED — 16:9 MASTER DOCUMENTARY")
    print(f"Release: Week {ep_num:02d} | Title: {ep_title}")
    print(f"Directory: {ep_p}")
    print("=" * 78, flush=True)

    narration_text, scenes = parse_episode_folder(ep_p)
    narration_text = ensure_books_cta(narration_text)
    print(f"[Script] Narrative: {len(narration_text.split())} words, {len(scenes)} visual scenes.")

    images_paths = ensure_scene_images(scenes, ep_p, ep_num)

    if images_only:
        print(f"\n✔ [Images Verified] All {len(images_paths)} scenes ready in: {ep_p}/images")
        return None

    temp_dir = ep_p / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    soundtrack_path, transcript_path, total_duration = generate_speech_and_timestamps(
        narration_text, str(temp_dir), ep_prefix, speed=speed, force_rebuild=force_rebuild
    )

    total_frames = int(total_duration * FPS) + 12
    total_weights = sum(s["weight"] for s in scenes)
    curr_t = 0.0
    timeline = []

    for s in scenes:
        dur = (s["weight"] / total_weights) * total_duration
        timeline.append({
            "id": s["id"],
            "start": curr_t,
            "end": curr_t + dur,
            "motion": s["motion"]
        })
        curr_t += dur
    timeline[-1]["end"] = max(timeline[-1]["end"], total_duration + 1.0)

    chunks = load_chunked_captions_16x9(narration_text, transcript_path)
    print(f"[Captions] Created {len(chunks)} safe-zone subtitle chunks.")

    # Multi-Core NVENC Rendering
    raw_temp_video = str(temp_dir / f"{ep_prefix}_video_raw.mp4")
    num_workers = min(4, os.cpu_count() or 4)
    frames_per_worker = math.ceil(total_frames / num_workers)
    part_files = [str(temp_dir / f"{ep_prefix}_part_{i}.mp4") for i in range(num_workers)]

    import multiprocessing as mp
    manager = mp.Manager()
    progress_list = manager.list([0] * num_workers)

    print(f"\n=== Rendering {total_frames} Frames with {num_workers}-Core NVENC Engine ===", flush=True)
    t0 = time.time()
    procs = []

    for i in range(num_workers):
        sf = i * frames_per_worker
        ef = min(total_frames, (i + 1) * frames_per_worker)
        if sf >= total_frames:
            continue
        p = mp.Process(target=_render_segment_worker, args=(
            i, sf, ef, total_frames, timeline, chunks, images_paths, LOCAL_LOGO, part_files[i], progress_list
        ))
        p.start()
        procs.append(p)

    while any(p.is_alive() for p in procs):
        time.sleep(2.0)
        done_frames = sum(progress_list)
        pct = (done_frames / total_frames) * 100
        elapsed = max(0.1, time.time() - t0)
        fps_eff = done_frames / elapsed
        rem_frames = max(0, total_frames - done_frames)
        eta_sec = rem_frames / max(fps_eff, 0.01)
        print(f"  [Parallel NVENC 4-Core] {done_frames}/{total_frames} frames ({pct:.1f}%) | {fps_eff:.1f} fps | ETA: {eta_sec/60:.1f}m", flush=True)

    for p in procs:
        p.join()

    # Concatenate parts losslessly
    concat_txt = str(temp_dir / f"{ep_prefix}_concat_parts.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for p_file in part_files:
            if os.path.exists(p_file):
                f.write(f"file '{p_file}'\n")

    print("\n[Concat] Losslessly stitching video parts with stream copy...", flush=True)
    subprocess.run([
        FFMPEG_EXE, "-y",
        "-f", "concat", "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        raw_temp_video
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for p_file in part_files + [concat_txt]:
        if os.path.exists(p_file):
            try: os.remove(p_file)
            except Exception: pass

    # Master audio/video muxing with -movflags +faststart
    final_output = str(ep_p / f"{ep_prefix}_final_16x9.mp4")
    print(f"\n=== Muxing Full HD 16:9 Video with Master Audio into Final Master ===", flush=True)
    cmd = [
        FFMPEG_EXE, "-y",
        "-i", raw_temp_video,
        "-i", soundtrack_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "256k",
        "-shortest",
        "-movflags", "+faststart",
        final_output
    ]
    cf = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
    subprocess.run(cmd, check=True, creationflags=cf)

    if os.path.exists(raw_temp_video):
        try: os.remove(raw_temp_video)
        except Exception: pass

    dur_mins = total_duration / 60.0
    print(f"\n=============================================================================")
    print(f"🎉 MASTER 16:9 DOCUMENTARY COMPLETED SUCCESSFULLY!")
    print(f"📁 Output Video: {final_output}")
    print(f"⏱ Video Duration: {dur_mins:.1f} mins ({total_duration:.1f}s)")
    print(f"⏱ Total Render Time: {time.time()-t0:.1f}s")
    print(f"=============================================================================\n", flush=True)
    return final_output

# =============================================================================
# CLI ARGUMENT DISPATCHER & EPISODE RESOLVER
# =============================================================================
def find_episode_info(target_identifier, video_num=None):
    clean_num = None
    try:
        m = re.search(r'\d+', str(target_identifier))
        if m:
            clean_num = int(m.group(0))
    except Exception:
        pass

    # 1. Weekly folder in BHSR_ROOT: W01, W02, ...
    if clean_num is not None:
        w_path = BHSR_ROOT / f"W{clean_num:02d}" / "long_form"
        if w_path.is_dir():
            subdirs = sorted([d for d in w_path.iterdir() if d.is_dir() and d.name.lower() not in ["images", "temp", "__pycache__", "sample_2min_before_genesis"]])
            if subdirs:
                if video_num is not None:
                    target_sub = None
                    for d in subdirs:
                        if d.name.startswith(f"0{video_num}") or d.name.startswith(f"{video_num}_") or d.name.startswith(f"{video_num}-"):
                            target_sub = d
                            break
                    if not target_sub and 1 <= video_num <= len(subdirs):
                        target_sub = subdirs[video_num - 1]
                    if target_sub:
                        return str(target_sub), clean_num
                # Default to first subfolder if subdirs exist
                return str(subdirs[0]), clean_num
            return str(w_path), clean_num

    # 2. Direct folder in BHSR_ROOT
    direct_w = BHSR_ROOT / str(target_identifier) / "long_form"
    if direct_w.is_dir():
        num = clean_num or 1
        subdirs = sorted([d for d in direct_w.iterdir() if d.is_dir() and d.name.lower() not in ["images", "temp", "__pycache__", "sample_2min_before_genesis"]])
        if subdirs:
            if video_num is not None and 1 <= video_num <= len(subdirs):
                return str(subdirs[video_num - 1]), num
            return str(subdirs[0]), num
        return str(direct_w), num

    # 3. BHSR-Youtube project folder
    if BHSR_YOUTUBE_DIR.exists():
        for d in BHSR_YOUTUBE_DIR.iterdir():
            if d.is_dir() and (str(target_identifier).lower() in d.name.lower() or (clean_num and d.name.startswith(f"{clean_num}-"))):
                return str(d), clean_num or 1

    return None, None

def list_episodes():
    print(f"\n{'='*78}")
    print(f" BIBLE HIDDEN SECRETS REVEALED: WEEKLY DOCUMENTARIES (16:9)")
    print(f"{'='*78}")
    print(f"{'Week':<6} | {'Title':<45} | {'Status'}")
    print(f"{'-'*78}")

    for w in range(1, 157):
        w_dir = BHSR_ROOT / f"W{w:02d}"
        lf_dir = w_dir / "long_form"
        if not w_dir.is_dir():
            continue

        title = f"Week {w}"
        meta_file = w_dir / "metadata.json"
        if meta_file.exists():
            try:
                m = json.loads(meta_file.read_text(encoding="utf-8"))
                title = m.get("documentary", {}).get("title", title)[:45]
            except Exception:
                pass

        subdirs = sorted([d for d in lf_dir.iterdir() if d.is_dir() and d.name.lower() not in ["images", "temp", "__pycache__", "sample_2min_before_genesis"]]) if lf_dir.is_dir() else []
        has_video = any(f.suffix == ".mp4" and "temp" not in f.parts for f in lf_dir.rglob("*.mp4")) if lf_dir.is_dir() else False
        has_script = any(f.name.startswith("script") for f in lf_dir.rglob("*")) if lf_dir.is_dir() else False
        status = "COMPLETED" if has_video else ("IN PRODUCTION" if has_script else "PLANNED")
        if subdirs:
            title = f"{title} ({len(subdirs)} cuts)"

        if has_video or has_script or w <= 52:
            print(f"W{w:02d}    | {title:<45} | {status}")

    print(f"{'='*78}\n")

def main():
    parser = argparse.ArgumentParser(description="Bible Hidden Secrets Revealed 16:9 Master Video Generator")
    parser.add_argument("--week", "-w", help="Week release number (e.g. 1, 2, W01, W02)")
    parser.add_argument("--episode", "-e", help="Episode number or name")
    parser.add_argument("--video", "-v", type=int, default=None, help="Video subfolder / cut index (e.g. 1, 2)")
    parser.add_argument("--images-only", action="store_true", help="Only verify or generate FLUX 16:9 images")
    parser.add_argument("--force-rebuild", action="store_true", help="Force rebuild all images, audio, and video")
    parser.add_argument("--speed", type=float, default=1.0, help="Voiceover pace multiplier (e.g. 1.05)")
    parser.add_argument("--list", action="store_true", help="List all available documentary releases and status")

    raw_args = sys.argv[1:]
    target_ep = None
    for a in raw_args:
        m_w = re.match(r'^--w(?:eek)?[-_]?(\d+)$', a, re.IGNORECASE)
        if m_w:
            target_ep = m_w.group(1)
            break
        m_e = re.match(r'^--ep[-_]?(\d+)$', a, re.IGNORECASE)
        if m_e:
            target_ep = m_e.group(1)
            break

    args, unknown = parser.parse_known_args()

    if args.list:
        list_episodes()
        return

    selected_ep = target_ep or args.week or args.episode
    if not selected_ep:
        print("\n[!] Please specify a week or episode. Examples:")
        print("    python generate_video.py --week 1")
        print("    python generate_video.py --week 2 --force-rebuild")
        print("    python generate_video.py --week 2 --video 1")
        print("    python generate_video.py --week 2 --video 2")
        print("    python generate_video.py --week 2 --images-only")
        print("    python generate_video.py --list\n")
        return

    ep_dir, ep_num = find_episode_info(selected_ep, video_num=args.video)
    if not ep_dir or not os.path.isdir(ep_dir):
        print(f"[Error] Could not locate episode matching '{selected_ep}' in {BHSR_ROOT}")
        list_episodes()
        return

    build_16x9_video(
        ep_dir=ep_dir,
        ep_num=ep_num or 1,
        speed=args.speed,
        images_only=args.images_only,
        force_rebuild=args.force_rebuild
    )

if __name__ == "__main__":
    main()
