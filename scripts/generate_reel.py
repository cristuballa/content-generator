"""
=============================================================================
BIBLE HIDDEN SECRETS REVEALED — MASTER REEL VIDEO GENERATOR (generate_reel.py)
=============================================================================
Universal, single root generator for all reels across the entire application.
Standard: Episode 57 / Week 1 Reel 1 Benchmark Standard
- Resolution: Native 768x1344 (9:16 vertical, FLUX native)
- Motion: Smooth Ken Burns frame-by-frame easing zoom/pan (apply_motion)
- Captions: Safe-zone (Y=74%) rounded black badge with white text & active gold word highlight
- Audio: Broadcast-mastered narration only (no background music)
- Visuals: FLUX.1 Schnell GGUF photorealistic scene images + text cards with scene background
- Metadata: Dynamically ingests metadata.json, script.txt, and scene configs from each reel folder
=============================================================================
CLI Usage:
  python generate_reel.py --week 1 --reel 4
  python generate_reel.py --week 1 --reel 5
  python generate_reel.py --week 1 --all
  python generate_reel.py --episode 4
  Flags: --force-rebuild, --images-only, --ads [1|2|3], --speed [float]
=============================================================================
"""

import os
import sys
import re
import json
import time
import math
import shutil
import asyncio
import difflib
import argparse
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Union, Optional, List, Dict
import numpy as np

from PIL import Image, ImageDraw, ImageFont

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

if sys.platform == "win32":
    try:
        import ctypes
        # Set process priority to BELOW_NORMAL to keep system and UI completely responsive
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x00004000)
    except Exception:
        pass

# Clamp CPU thread storms to prevent laptop thermal throttling to 1.0 GHz
os.environ.setdefault("OMP_NUM_THREADS", "4")
os.environ.setdefault("MKL_NUM_THREADS", "4")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "4")

SUBPROCESS_CREATIONFLAGS = (subprocess.CREATE_NO_WINDOW | 0x00004000) if sys.platform == "win32" else 0

# =============================================================================
# ENVIRONMENT & PYTHON PATH AUTO-SWITCHING
# =============================================================================
PROJECT_DIR = Path(r"C:\Projects\BHSR") if Path(r"C:\Projects\BHSR").exists() else Path(__file__).resolve().parent
if PROJECT_DIR.name == "scripts":
    PROJECT_DIR = PROJECT_DIR.parent
ADZ_DIR = Path(r"C:\Projects\Adz-Video")


def find_vibevoice_paths():
    cand_pythons = [
        PROJECT_DIR / ".venv_vibevoice" / "Scripts" / "python.exe",
        Path(r"C:\Projects\BHSR\.venv_vibevoice\Scripts\python.exe"),
        Path(r"C:\Projects\Bible Hidden Secrets Revealed\.venv_vibevoice\Scripts\python.exe"),
    ]
    cand_scripts = [
        PROJECT_DIR / "vibevoice_engine.py",
        Path(r"C:\Projects\BHSR\vibevoice_engine.py"),
        Path(r"C:\Projects\Bible Hidden Secrets Revealed\vibevoice_engine.py"),
    ]
    vv_py = next((str(p) for p in cand_pythons if p.exists()), str(cand_pythons[0]))
    vv_script = next((str(s) for s in cand_scripts if s.exists()), str(cand_scripts[0]))
    return vv_py, vv_script

VIBEVOICE_PYTHON, VIBEVOICE_SCRIPT = find_vibevoice_paths()
COMFY_DIR = r"C:\Users\User\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI"
COMFY_PYTHON = os.path.join(COMFY_DIR, r".venv\Scripts\python.exe")
COMFY_URL = "http://127.0.0.1:8188"

# Auto-switch to vibevoice virtualenv if whisper is missing in current environment
if __name__ == "__main__":
    try:
        import whisper
        import imageio
    except ImportError:
        target_py = VIBEVOICE_PYTHON if os.path.exists(VIBEVOICE_PYTHON) else COMFY_PYTHON
        if os.path.exists(target_py) and os.path.normpath(sys.executable).lower() != os.path.normpath(target_py).lower():
            sys.exit(subprocess.call([target_py] + sys.argv))

try:
    import imageio
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = shutil.which("ffmpeg") or r"C:\Users\User\AppData\Local\Comfy-Desktop\ComfyUI-Installs\ComfyUI\ComfyUI\.venv\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg.exe"

if FFMPEG_EXE and os.path.dirname(FFMPEG_EXE):
    os.environ["PATH"] = os.path.dirname(FFMPEG_EXE) + os.pathsep + os.environ.get("PATH", "")

WIDTH = 768
HEIGHT = 1344
FPS = 30

LOCAL_LOGO = str(PROJECT_DIR / "shared_assets" / "transparent_logo.png")
if not os.path.exists(LOCAL_LOGO):
    LOCAL_LOGO = str(PROJECT_DIR / "reel_output" / "transparent_logo.png")

# =============================================================================
# PERIODIC PROGRESS HEARTBEAT (EVERY 60 SECONDS)
# =============================================================================
import threading

class ProgressHeartbeat:
    """Emits an unbuffered progress heartbeat every N seconds (default: 60s) during long tasks."""
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
# PRONUNCIATION & BIBLE FORMATTING MAPS
# =============================================================================
PRONUNCIATION_MAP = {
    "Tetelestai": "Teh-tell-es-tie",
    "Heylel": "hay-LEL",
    "Shachar": "shah-KHAR",
    "Nachash": "nah-KHAHSH",
    "Nechoshet": "neh-KHOH-shet",
    "Nechashim": "neh-khah-SHEEM",
    "Nehushtan": "neh-HOOSH-tahn",
    "malum": "MAH-loom",
    "Yehi Or": "yeh-HEE OR",
    "Merachefet": "meh-rah-KHEH-fet",
    "tohu": "TOH-hoo",
    "yom": "yohm",
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
    "Ruach Elohim": "Roo-ahk Elohim",
    "Ruach": "Roo-ahk",
    "Bereshit": "Beh-ray-sheet",
    "Bara": "Bah-rah",
    "Naaman": "Nay-man",
    "Elisha": "Ee-lye-sha",
    "Yam Suph": "Yahm Soof",
    "Melchizedek": "Mel-kiz-eh-dek",
    "Nephilim": "Nef-ih-lim",
    "Tamim": "Tah-meem",
    "bene elohim": "beh-nay elohim",
    "Bene Elohim": "Beh-nay Elohim",
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
    "zera": "ZEH-rah",
    "eybah": "ay-VAH",
    "shuph": "SHOOF",
    "hu": "HOO",
    "autos": "ow-TOS",
    "Targum": "TAR-goom",
    "Targums": "TAR-gooms",
    "Neofiti": "neh-oh-FEE-tee",
    "Irenaeus": "eye-ren-AY-us",
    "gulgulta": "gool-GOOL-tah",
    "Shiloh": "SHY-loh",
    "Chavvah": "khah-VAH",
    "tebah": "tay-VAH",
    "Shiphrah": "SHIF-rah",
    "Puah": "POO-ah",
    "Athaliah": "ath-uh-LYE-uh",
    "Jehosheba": "jeh-HOSH-eh-bah",
    "Agagite": "AY-gag-ite",
    "Jeconiah": "jek-oh-NYE-ah",
    "Coniah": "koh-NYE-ah",
    "suntribo": "soon-TREE-boh",
    "Mariamne": "mar-ee-AM-nee",
    "Macrobius": "mah-KROH-bee-us",
    "Hammedatha": "ham-eh-DAY-thah",
    "Sisera": "SIS-er-ah",
    "Abimelech": "ah-BIM-eh-lek",
    "Thebez": "THEE-bez",
    "Jechonias": "jek-oh-NYE-as",
    "Ahaziah": "ay-hah-ZYE-ah",
    "Lamech": "LAY-mek",
    "Mordecai": "MOR-deh-kye",
    "Jael": "JAY-el",
    "Protoevangelium": "proh-toh-ee-van-JEH-lee-um",
    "Shemihazah": "sheh-mee-hah-ZAH",
    "Ohyah": "oh-YAH",
    "Hahyah": "hah-YAH",
    "Mahaway": "mah-hah-WAY",
    "Utnapishtim": "oot-nah-PISH-tim",
    "tartaroo": "tar-tah-ROH-oh",
    "Paneas": "pah-NEE-as",
    "Banias": "bah-NEE-as",
    "Sirion": "SIR-ee-on",
    "Shenir": "SHEE-ner",
    "Baalhermon": "BAY-al-HER-mon",
    "oiketerion": "oy-kay-TAY-ree-on",
    "kerusso": "kay-ROO-soh",
    "Kokabiel": "koh-KAH-bee-el",
    "Baraqiel": "bah-RAH-kee-el",
    "abussos": "AH-boos-sos",
    "herem": "KHEH-rem",
    "Ardis": "AR-dis",
    "Dudael": "DOO-dah-el",
    "arche": "ar-KAY",
    "Irin": "ee-REEN",
    "gibborim": "gee-boh-REEM",
    "Azazel": "ah-ZAH-zel",
    "Hermon": "HER-mon",
    "Apkallu": "ap-KAH-loo",
    "Hobabish": "hoh-BAH-bish",
    "Humbaba": "hoom-BAH-bah",
    "Turfan": "toor-FAHN",
    "Milik": "MEE-lik",
    "Qumran": "koom-RAHN",
    "chamas": "khah-MAHS",
    "Anakims": "AN-ak-imz",
    "Ahiman": "ah-HY-man",
    "Sheshai": "SHESH-eye",
    "Talmai": "TAL-my",
    "Emims": "EE-mimz",
    "Zamzummims": "zam-ZUM-imz",
    "Rephaims": "REF-ay-imz",
    "Rephaim": "REF-ay-im",
    "Kirjatharba": "KEER-jath-AR-bah",
    "Jephunneh": "jeh-FUN-eh",
    "Ishbibenob": "ISH-by-BEE-nob",
    "Sibbechai": "SIB-eh-kye",
    "Elhanan": "el-HAY-nan",
    "Lahmi": "LAH-mee",
    "Abishai": "ah-BISH-eye",
    "Zeruiah": "zer-oo-EYE-ah",
    "Shimeah": "SHIM-ee-ah",
    "Masoretic": "mas-oh-RET-ik",
    "Ugarit": "OO-gah-reet",
    "Atrahasis": "ah-trah-HAH-sis",
    "Enlil": "EN-lil",
    "Manichaeism": "MAN-ih-kee-iz-um",
    "Manichaeans": "man-ih-KEE-unz",
    "Kenezite": "KEN-ez-ite",
    "Kenizzites": "KEN-iz-ites",
    "Chedorlaomer": "KED-or-lay-OH-mer",
    "Ashteroth": "ASH-teh-roth",
    "Karnaim": "kar-NAY-im",
    "Machpelah": "mak-PEE-lah",
    "Mamre": "MAM-ree",
    "Gittite": "GIT-ite",
    "Zoan": "ZOH-an",
    "Debir": "DEE-bur",
    "Sirach": "SY-rak",
    "Uruk": "OO-rook",
    "Jozef": "YOH-zef",
    "Gilgamesh": "GIL-gah-mesh",
    "Mani": "MAH-nee",
    "Asael": "AH-sah-el",
    "Hadudo": "hah-DOO-doh",
    "Yoma": "YOH-mah",
    "Nachmanides": "nahk-MAN-ih-deez",
    "Ibn Ezra": "IB-un EZ-rah",
    "seirim": "seh-ee-REEM",
    "Raphael": "RAF-ay-el",
    "apopompaios": "ah-poh-pom-PIE-os",
    "Tyndale": "TIN-dul",
    "Segan": "seh-GAHN",
    "Gamla": "GAHM-lah",
    "Zakkai": "zah-KYE",
    "Johanan": "joh-HAY-nan",
    "Talmud": "TAHL-mood",
    "Tacitus": "TASS-ih-tus",
    "Hekal": "hay-KAHL",
    "Abihu": "ah-BYE-hew",
    "Nadab": "NAY-dab",
    "Caiaphas": "KYE-ah-fus",
    "Rashi": "RAH-shee",
    "Kippur": "kee-POOR",
    "Uza": "OO-zah",
    "Azael": "AH-zah-el",
    "Zacharias": "zak-ah-RYE-us",
    "hilasterion": "hil-ah-STAIR-ee-on",
    "gezerah": "geh-zeh-RAH",
    "Jeroboam": "jair-oh-BOH-am",
    "Gadarenes": "GAD-ah-reenz",
    "Sadducees": "SAD-yoo-seez",
    "Iddo": "ID-oh",
    "menorah": "meh-NOR-ah",
    "tsuk": "TSOOK",
    "Elah": "EE-lah",
    "gopher": "GOH-fer",
    "kopher": "KOH-fer",
    "kaphar": "kah-FAR",
    "kupru": "KOOP-roo",
    "qinnim": "kin-NEEM",
    "tsohar": "TSOH-har",
    "Methuselah": "meh-THOO-zeh-lah",
    "mabbul": "mah-BOOL",
    "Ararat": "AIR-ah-rat",
    "Urartu": "oo-RAR-too",
    "Noe": "NOH-ee",
    "Japheth": "JAY-feth",
    "antitypos": "AN-tee-tee-pos",
    "Rabbah": "RAH-bah",
    "Finkel": "FINK-ul",
    "qeshet": "KEH-shet",
    "berit": "beh-REET",
    "mizbeach": "miz-BAY-akh",
    "nichoach": "nee-KHO-akh",
    "Enuma Elish": "eh-NOO-mah EH-lish",
    "Marduk": "MAR-dook",
    "Chebar": "KEE-bar",
    "Jehoiachin": "jeh-HOY-ah-kin",
    "Patmos": "PAT-mos",
    "kyklothen": "KOO-kloh-then",
    "smaragdos": "smah-RAG-dos",
    "toxon": "TOK-son",
    "sardius": "SAR-dee-us",
    "Esaias": "eh-ZAY-us",
    "Nippur": "nip-POOR",
    "Pliny": "PLIN-ee",
    "chalcedony": "kal-SED-oh-nee",
    "Juda": "JOO-dah",
    "Lystra": "LIS-trah",
    "Mizraim": "miz-RAY-im",
    "Phut": "FUTT",
    "Megillah": "meh-GIL-ah",
    "Gibeonites": "GIB-ee-on-ites",
    "Syrophenician": "sy-roh-feh-NISH-un",
    "Rachab": "RAY-kab",
    "Madai": "MAY-dye",
    "Javan": "JAY-van",
    "Kittim": "KIT-im",
    "Tarshish": "TAR-shish",
    "Ashkenaz": "ASH-keh-naz",
    "Caphtorim": "kaf-TOR-im",
    "Casluhim": "KAS-loo-him",
    "Philistim": "fih-LIS-tim",
    "Girgasite": "GUR-gah-site",
    "Arvadite": "AR-vad-ite",
    "Zemarite": "ZEM-ah-rite",
    "Hamathite": "HAY-math-ite",
    "Arphaxad": "ar-FAX-ad",
    "Joktan": "JOK-tan",
    "Ras Shamra": "rahs SHAHM-rah",
    "Asherah": "ah-SHEER-ah",
    "Molech": "MOH-lek",
    "Ittai": "IT-eye",
    "Elamites": "EE-lam-ites",
    "Peleset": "PEL-eh-set",
    "Medinet Habu": "meh-DEE-net HAH-boo",
    "Ramesses": "RAM-eh-seez",
    "Caphtor": "KAF-tor",
    "Ebedmelech": "EE-bed-MEE-lek",
    "Kition": "KIT-ee-on",
    "Gimirrai": "gim-ih-RYE",
    "Sukkah": "SOO-kah",
    "Talitha": "TAL-ih-thah",
    "cumi": "KOO-mee",
    "Eloi": "ay-LOH-ee",
    "sabachthani": "sah-bahk-TAH-nee",
    "Areni": "ah-REN-ee",
    "Nimrod": "NIM-rod",
    "Shinar": "SHY-nar",
    "Erech": "EE-rek",
    "Accad": "AK-ad",
    "Calneh": "KAL-neh",
    "Calah": "KAY-lah",
    "Resen": "REE-sen",
    "Nimrud": "nim-ROOD",
    "gibbor": "gib-BOR",
    "Etemenanki": "eh-teh-meh-NAHN-kee",
    "ziggurat": "ZIG-oo-rat",
    "ziggurats": "ZIG-oo-rats",
    "Nabopolassar": "nab-oh-poh-LAS-ar",
    "Herodotus": "heh-ROD-oh-tus",
    "Enmerkar": "en-MER-kar",
    "Aratta": "ah-RAT-ah",
    "balal": "bah-LAHL",
    "Bab-ili": "bahb-EE-lee",
    "Hammurabi": "ham-oo-RAH-bee",
    "Esagila": "eh-sah-GEE-lah",
    "Nebuchadnezzar": "neb-oo-kad-NEZ-ar",
    "Belshazzar": "bel-SHAZ-ar",
    "Nabonidus": "nab-oh-NY-dus",
    "Upharsin": "oo-FAR-sin",
    "Peres": "PEH-res",
    "helel": "hay-LAYL",
    "Bethel": "BETH-el",
    "Ashurbanipal": "ah-shur-BAH-nee-pal",
    "Ninurta": "nih-NOOR-tah",
    "Ekur": "EH-koor",
    "Belteshazzar": "bel-teh-SHAZ-ar",
    "Merodach": "MER-oh-dak",
    "Kalhu": "KAL-hoo",
    "Woolley": "WOOL-ee",
    "Akkadian": "ah-KAY-dee-an"
}

ACRONYMS = {"USA", "UK", "DNA", "BC", "AD", "B.C.", "A.D.", "AI"}

BIBLE_BOOKS_BASE = {
    'genesis': 'Genesis', 'gen': 'Genesis', 'exodus': 'Exodus', 'exod': 'Exodus',
    'leviticus': 'Leviticus', 'lev': 'Leviticus', 'numbers': 'Numbers', 'num': 'Numbers',
    'deuteronomy': 'Deuteronomy', 'deut': 'Deuteronomy', 'joshua': 'Joshua', 'josh': 'Joshua',
    'judges': 'Judges', 'ruth': 'Ruth', 'samuel': 'Samuel', 'sam': 'Samuel',
    'kings': 'Kings', 'kgs': 'Kings', 'chronicles': 'Chronicles', 'chron': 'Chronicles',
    'ezra': 'Ezra', 'nehemiah': 'Nehemiah', 'neh': 'Nehemiah', 'esther': 'Esther',
    'job': 'Job', 'psalm': 'Psalms', 'psalms': 'Psalms', 'ps': 'Psalms',
    'proverbs': 'Proverbs', 'prov': 'Proverbs', 'ecclesiastes': 'Ecclesiastes',
    'isaiah': 'Isaiah', 'isa': 'Isaiah', 'jeremiah': 'Jeremiah', 'jer': 'Jeremiah',
    'lamentations': 'Lamentations', 'ezekiel': 'Ezekiel', 'ezek': 'Ezekiel',
    'daniel': 'Daniel', 'dan': 'Daniel', 'hosea': 'Hosea', 'joel': 'Joel',
    'amos': 'Amos', 'jonah': 'Jonah', 'micah': 'Micah', 'nahum': 'Nahum',
    'habakkuk': 'Habakkuk', 'hab': 'Habakkuk', 'zephaniah': 'Zephaniah',
    'haggai': 'Haggai', 'zechariah': 'Zechariah', 'zech': 'Zechariah',
    'malachi': 'Malachi', 'matthew': 'Matthew', 'matt': 'Matthew',
    'mark': 'Mark', 'luke': 'Luke', 'john': 'John', 'acts': 'Acts',
    'romans': 'Romans', 'rom': 'Romans', 'corinthians': 'Corinthians', 'cor': 'Corinthians',
    'galatians': 'Galatians', 'ephesians': 'Ephesians', 'philippians': 'Philippians',
    'colossians': 'Colossians', 'thessalonians': 'Thessalonians', 'timothy': 'Timothy',
    'titus': 'Titus', 'philemon': 'Philemon', 'hebrews': 'Hebrews', 'heb': 'Hebrews',
    'james': 'James', 'jas': 'James', 'peter': 'Peter', 'pet': 'Peter',
    'jude': 'Jude', 'revelation': 'Revelation', 'revelations': 'Revelation', 'rev': 'Revelation'
}
PREFIX_NUMS = {'1': '1', '2': '2', '3': '3', 'first': '1', 'second': '2', 'third': '3'}

MOTIONS_CYCLE = [
    {"type": "slow_push_in", "start_zoom": 1.0, "end_zoom": 1.15, "pan_y": [0.5, 0.4]},
    {"type": "dramatic_punch_in", "start_zoom": 1.02, "end_zoom": 1.18, "pan_y": [0.45, 0.42]},
    {"type": "tilt_up", "start_zoom": 1.05, "end_zoom": 1.16, "pan_y": [0.75, 0.35]},
    {"type": "intense_zoom", "start_zoom": 1.0, "end_zoom": 1.22, "pan_y": [0.4, 0.4]},
    {"type": "pan_down_collapse", "start_zoom": 1.05, "end_zoom": 1.17, "pan_y": [0.3, 0.7]},
    {"type": "slow_pull_back", "start_zoom": 1.18, "end_zoom": 1.02, "pan_y": [0.5, 0.5]},
]

AD_VARIANTS = {
    1: {
        "id": "ad_1_watchers_and_the_word",
        "title": "The Watchers & The Word — Book of Enoch Secrets (Ezra Keys)",
        "graphic": "shared_assets/watchers_ad_desk.png",
        "script": (
            "If this revelation opened your eyes, go deeper. In our new book, The Watchers and the Word: "
            "Unlocking the Secrets of the Book of Enoch by Ezra Keys, we decode the lost mysteries of the heavenly host "
            "and ancient Scripture. Available now on Etsy, linked in our bio and comments."
        ),
        "motion": {"type": "slow_push_in", "start_zoom": 1.0, "end_zoom": 1.05, "pan_y": [0.5, 0.5]}
    },
    2: {
        "id": "ad_2_watchers_fallen_angels",
        "title": "The Watchers & The Word — Forbidden History of the Watchers",
        "graphic": "shared_assets/watchers_ad_standing.png",
        "script": (
            "Ready to uncover what was hidden? The Watchers and the Word reveals the forbidden history "
            "of the fallen watchers and the ancient biblical texts. Grab your copy of The Watchers and the Word "
            "on Etsy. Link in the bio and comments."
        ),
        "motion": {"type": "slow_push_in", "start_zoom": 1.0, "end_zoom": 1.05, "pan_y": [0.5, 0.5]}
    },
    3: {
        "id": "ad_3_watchers_spiritual_realm",
        "title": "The Watchers & The Word — Deep Spiritual Study",
        "graphic": "shared_assets/watchers_ad_cover.png",
        "script": (
            "If you want to understand the spiritual realm like never before, get our book, The Watchers and the Word: "
            "Unlocking the Secrets of the Book of Enoch by Ezra Keys. Available now on Etsy, "
            "linked in the bio and comments below."
        ),
        "motion": {"type": "slow_push_in", "start_zoom": 1.0, "end_zoom": 1.05, "pan_y": [0.5, 0.5]}
    }
}

# =============================================================================
# PINNED COMMENTS PER AD OUTRO VARIANT
# =============================================================================
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
    # Ad 7: Fishers of Men Official Merch Carousel
    "merch": (
        '👕 Get the Official "Fishers of Men" Collection on Etsy:\n'
        '👉 https://www.etsy.com/nz/listing/4536166831\n\n'
        '✨ Browse All Books & Sacred Art:\n'
        '👉 https://www.etsy.com/shop/BibleHiddenGems'
    ),
    # Default fallback
    "default_ad": (
        '📖 Get "The Watchers & The Word" on Etsy:\n'
        '👉 https://www.etsy.com/nz/listing/4591934547\n\n'
        '✨ Browse All Books & Sacred Art:\n'
        '👉 https://www.etsy.com/shop/BibleHiddenGems'
    ),
    # Clean Video (No Ad Attached)
    "clean": (
        '💬 What was the biggest revelation for you in this video? Share your thoughts below!\n\n'
        '✨ Browse All Books & Sacred Art:\n'
        '👉 https://www.etsy.com/shop/BibleHiddenGems'
    )
}


def generate_pinned_comment_for_ad(ad_source: Any = None, ad_clip_name: str = None) -> str:
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



# =============================================================================
# SCRIPT PARSER & VOICE PREPARATION
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


def strip_books_cta(narration: str) -> str:
    """
    Dual-layer short-form strategy: removes any hardcoded books/merch ad lines from clean reel narration.
    The advertisement lives strictly in the optional dedicated Ad Outro clip (ad_outro_*.mp4)
    rather than being baked into the core video voiceover and captions.
    """
    for old in (BOOKS_LINE, *OLD_BOOKS_LINES):
        narration = narration.replace(old, "")
    patterns = [
        r"If this (?:revelation )?blew your mind[^\.]*\.[^\.]*sacred art merch\.",
        r"If this (?:revelation )?blew your mind[^\.]*\.[^\.]*in our books\.",
        r"They're linked in the bio and comments, along with our sacred art merch\.",
        r"It's linked in the bio and comments, along with our sacred art merch\.",
        r"Our books and sacred art merch are linked in the bio and comments\.",
    ]
    for pat in patterns:
        narration = re.sub(pat, "", narration, flags=re.IGNORECASE)
    narration = re.sub(r"\s{2,}", " ", narration).strip()
    return narration


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


def clean_script_for_tts(raw_text: str, phonetic: bool = True) -> str:
    """
    Strips metadata headers, divider lines, and stage cues to extract pure narration.
    phonetic=True applies PRONUNCIATION_MAP for the voice; captions use phonetic=False so they show the real words.
    """
    lines = raw_text.splitlines()
    narr_lines = []

    has_narr_marker = any(re.search(r'NARRATION\s+SCRIPT', l, re.IGNORECASE) for l in lines)
    in_narration = not has_narr_marker

    for line in lines:
        s = line.strip()
        if not s:
            continue

        if re.match(r'^(WORD COUNT|SOURCES|METADATA|HASHTAGS|TAGS|NOTES):?', s, re.IGNORECASE):
            break

        if re.search(r'NARRATION\s+SCRIPT', s, re.IGNORECASE):
            in_narration = True
            continue

        if re.match(r'^[=\-_~*]{3,}$', s):
            continue

        if not in_narration:
            continue

        if re.match(r'^\[.*?\]$', s) or re.match(r'^\(.*?\)$', s) or is_script_header_line(s):
            continue

        cleaned = re.sub(r'\[.*?\]', '', strip_narrator_label(s))
        cleaned = re.sub(r'\(.*?\)', '', cleaned).strip()
        if cleaned:
            narr_lines.append(cleaned)

    if not narr_lines:
        cleaned = re.sub(r'\[.*?\]', '', raw_text)
        narr_lines = [l.strip() for l in cleaned.splitlines() if l.strip() and not is_script_header_line(l.strip())]

    full_narr = " ".join(narr_lines)
    for orig, phon in (PRONUNCIATION_MAP.items() if phonetic else ()):
        pattern = r"\b" + re.escape(orig) + r"\b"
        full_narr = re.sub(pattern, phon, full_narr, flags=re.IGNORECASE)

    # The voice reads "14:12" as "14, 12"; captions keep the reference as written (Isaiah 14:12)
    if phonetic:
        full_narr = re.sub(r'(\d+):(\d+)', r'\1, \2', full_narr)
    full_narr = re.sub(r'\s*[—–]\s*', ', ', full_narr)
    full_narr = full_narr.replace("'", "'").replace('"', '')
    full_narr = re.sub(r'\s+', ' ', full_narr).strip()
    return full_narr

def split_into_sentences(text: str) -> list:
    """Splits text into clean individual sentences without breaking em-dashes."""
    text = text.replace('\r\n', ' ').replace('\n', ' ')
    text = text.replace('—', ' - ').replace('–', ' - ')
    text = re.sub(r'\s+', ' ', text).strip()
    raw_sents = re.split(r'(?<=[.!?])\s+|(?<=[.!?]["\'])\s+', text)
    sentences = [s.strip().strip('"').strip("'") for s in raw_sents if len(s.strip()) > 0]
    return sentences

def prepare_voice_script(text: str) -> str:
    modified = text
    for orig, phonetic in PRONUNCIATION_MAP.items():
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
# DYNAMIC METADATA & SCENE CONFIG RESOLVER
# =============================================================================
# -----------------------------------------------------------------------------
# Reel folders: W06/reels/<day>_<n>_<name> (mon_1, mon_2, tue_1...). Posting order is day, then n.
# Older numbered folders (01_name, 146_name) take Monday..Friday in number order, one a day.
# Same rules as core/reels.py in KCT Studio: keep them in step.
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


def ordered_reels(reels_dir: Path) -> list:
    """A week's reel folders in posting order."""
    return [d for d, _, _ in reel_slots(reels_dir)]


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


def reel_key(folder: Path):
    """"mon_2" for W06/reels/mon_2_name."""
    for d, day, n in reel_slots(folder.parent):
        if d.name == folder.name:
            return f"{REEL_DAYS[day]}_{n}"
    return None


def find_reel_folder(week_dir: Path, which) -> Path:
    return find_reel(week_dir / "reels", which)


def _recorded_reel_number(folder: Path):
    """A reel's "Bible Secrets #NNN" number: metadata.json global_episode, or an older metadata.txt's EPISODE line."""
    try:
        num = json.loads((folder / "metadata.json").read_text(encoding="utf-8")).get("global_episode")
        if num is not None:
            return int(num)
    except (OSError, ValueError, TypeError):
        pass
    try:
        m = re.search(r"^EPISODE\s+(\d+)", (folder / "metadata.txt").read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
        if m:
            return int(m.group(1))
    except OSError:
        pass
    return None


def reel_global_number(target_dir: Path) -> int:
    """The reel's global number. A new reel without one gets the next free number, saved in its metadata.json so it
    never changes (reels are no longer numbered (week - 1) * 5 + n, since a week can hold any number of them)."""
    num = _recorded_reel_number(target_dir)
    if num is not None:
        return num
    # An older numbered folder (01_name) keeps the number it always had: (week - 1) * 5 + its rank
    week = re.match(r"^W(\d+)$", target_dir.parent.parent.name, re.IGNORECASE)
    if week and _REEL_NUMBERED_RE.match(target_dir.name):
        numbered = [d for d in ordered_reels(target_dir.parent) if _REEL_NUMBERED_RE.match(d.name)]
        if target_dir in numbered:
            return (int(week.group(1)) - 1) * 5 + numbered.index(target_dir) + 1
    taken = [_recorded_reel_number(d) for d in PROJECT_DIR.glob("W*/reels/*") if d.is_dir()]
    num = max([n for n in taken if n is not None], default=0) + 1
    meta_p = target_dir / "metadata.json"
    try:
        meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
        meta["global_episode"] = num
        meta_p.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    except (OSError, ValueError):
        pass
    return num


def find_reel_by_number(num: int):
    """(week number, folder) of the reel whose global number is num."""
    for d in sorted(PROJECT_DIR.glob("W*/reels/*")):
        if d.is_dir() and _recorded_reel_number(d) == num:
            m = re.match(r"^W(\d+)$", d.parent.parent.name, re.IGNORECASE)
            if m:
                return int(m.group(1)), d
    return None

def build_scene_prompt(sentence: str, title: str = "") -> str:
    s = sentence.strip()
    kw = s.lower()
    style = "cinematic vertical 9:16 shot, epic biblical aesthetic, highly detailed, dramatic atmospheric lighting, 8k resolution, photorealistic"

    # Context-aware visual scene descriptions matching narration accurately
    if any(w in kw for w in ["open his gospel", "exact same words", "literary coincidence", "accident"]):
        scene = "reverent Apostle John in coarse linen robe writing with reed quill on ancient papyrus scroll in candlelit stone room overlooking Mediterranean Sea at twilight"
    elif any(w in kw for w in ["theological revelation", "mediterranean world", "shook", "explosive"]):
        scene = "ancient Mediterranean coastal city with glowing marble temple colonnades under dramatic celestial sunset and storm clouds"
    elif any(w in kw for w in ["genesis 1:1", "moses", "historical event", "created the heavens", "heavens and the earth"]):
        scene = "majestic biblical panorama of the creation of heavens and earth, swirling celestial nebulae above deep primeval ocean, divine golden atmosphere"
    elif any(w in kw for w in ["unveiled", "eternal person", "behind the creation"]):
        scene = "Christ the pre-incarnate sovereign Word standing in transcendent celestial aura of divine amber light, holy heavenly glory"
    elif any(w in kw for w in ["beginning was the word", "word was with god", "word was god"]):
        scene = "heavenly realm of eternal light, divine radiant vision of the Holy Word of God in celestial glory surrounded by golden cherubim"
    elif any(w in kw for w in ["became flesh", "dwelt among us", "divine person", "incarnation"]):
        scene = "sacred cinematic portrait of Jesus Christ in radiant ivory white and deep crimson robes, holy divine radiance on ancient Jerusalem hillside at dusk"
    elif any(w in kw for w in ["abstract energy", "united both traditions"]):
        scene = "sacred biblical synthesis: ancient Hebrew Torah scroll meeting Greek philosophical scrolls in divine golden stone study, heavenly revelation light"
    elif any(w in kw for w in ["impersonal cosmic force", "maintaining order", "universe"]):
        scene = "intricate glowing celestial armillary sphere and astronomical astrolabe aligning with rotating galaxies in the cosmic night sky"
    elif any(w in kw for w in ["logos", "greek", "philosophy", "divine reason"]):
        scene = "ancient Greek marble colonnade and observatory courtyard at twilight, scholars looking at vast rotating cosmic star constellations"
    elif any(w in kw for w in ["dabar yahweh", "living word", "shattered darkness", "wonders", "jewish theology"]):
        scene = "dramatic biblical revelation of the living Dabar Yahweh: fiery golden Paleo-Hebrew divine light shattering deep celestial darkness with lightning and glory"
    elif any(w in kw for w in ["let there be light", "voice speaking", "speaking reality"]):
        scene = "mighty cosmic voice of God over dark primordial oceans of Genesis 1, explosive shockwave of holy golden light breaking across ocean waves"
    elif any(w in kw for w in ["without him was not anything", "john 1:3", "room for doubt"]):
        scene = "cosmic blueprint of creation: glowing golden hand of Christ tracing the orbits of swirling planets, moons, and constellations in the starry cosmos"
    elif any(w in kw for w in ["commander", "executing the will", "father's command", "summoned"]):
        scene = "Lord Jesus Christ as the sovereign cosmic Commander seated upon sapphire throne in celestial throne room surrounded by majestic winged seraphim"
    elif any(w in kw for w in ["architect", "manger", "bethlehem", "every galaxy", "heartbeat", "soul"]):
        scene = "Christ the supreme celestial Architect shaping glowing spiral galaxies and star constellations with radiant hands against backdrop of ancient Bethlehem star"
    elif any(w in kw for w in ["cross", "calvary", "crucifixion", "gave his life", "creator who gave"]):
        scene = "dramatic silhouette of the holy cross of Christ atop Mount Calvary against stormy twilight skies with divine golden celestial rays breaking through clouds"
    elif any(w in kw for w in ["lucifer", "covering cherub", "guardian cherub", "stones of fire", "precious stone", "seal of perfection", "adorned"]):
        scene = "magnificent celestial archangel Lucifer with six majestic wings adorned with glowing chrysolite and gold walking among burning stones of fire in heaven"
    elif any(w in kw for w in ["fall like lightning", "cast down", "satan fall", "stripped of his authority", "into darkness", "rebellion", "five fatal"]):
        scene = "dramatic cosmic scene: radiant star falling like a brilliant streak of lightning from the gates of heaven down into dark starry chasm"
    elif any(w in kw for w in ["morning star", "mount of assembly", "stars of god", "throne above the stars", "destroy the works"]):
        scene = "Lord Jesus Christ the radiant Morning Star ascending in divine majesty and triumph, golden sunrise illuminating heavenly mountains of God"
    elif any(w in kw for w in ["job 38", "whirlwind", "foundations", "where were you"]):
        scene = "mighty swirling celestial whirlwind with lightning breaking through dark cosmic storm clouds, divine voice speaking over the ancient cosmos"
    elif any(w in kw for w in ["morning stars singing", "sons of god", "shouted for joy", "sang together"]):
        scene = "celestial divine council in heaven, multitude of glowing angelic seraphim and radiant morning stars singing in cosmic harmony before the throne"
    elif any(w in kw for w in ["bene elohim", "council", "seraphim", "angelic", "audience", "statues"]):
        scene = "celestial courtroom of heaven, burning fiery seraphim with majestic feathered wings assembled before the ancient of days in radiant light"
    elif any(w in kw for w in ["eden", "adam", "breath", "paradise", "garden"]):
        scene = "lush sacred mountain of God in primeval Eden, majestic ancient cedar trees, crystal rivers of life bathed in golden mist"
    elif any(w in kw for w in ["hebrew", "letter", "bereshit", "bara", "scripture", "written", "scroll"]):
        scene = "ancient weathered Hebrew parchment scroll with glowing Paleo-Hebrew characters carved in Jerusalem stone illuminated by warm candlelight"
    elif any(w in kw for w in ["blew your mind", "our books", "linked in the bio", "sacred art merch", "in the bio"]):
        scene = "stack of antique leather-bound books with gold-embossed spines beside framed sacred art prints on a warm wooden desk, soft candlelight and floating golden particles"
    elif any(w in kw for w in ["watch", "link is in the description", "full episode"]):
        scene = "ancient illuminated Holy Bible open on rustic olive wood desk beside burning brass oil lamp with soft floating golden particles"
    elif any(w in kw for w in ["follow", "subscribe", "secrets hidden"]):
        scene = "majestic sacred scripture library with ancient parchment scrolls, warm glowing candles, and radiant divine golden atmosphere"
    else:
        sentence_text = re.sub(r"\s+", " ", s).strip().rstrip(".!?")[:180]
        about = f" in a Bible documentary about {title}" if title else ""
        scene = f"cinematic biblical illustration of this moment{about}: {sentence_text}, ancient Near Eastern setting, no text or lettering"


    return f"{scene}, {style}"

REEL_IMAGE_STYLE = "cinematic vertical 9:16 shot, epic biblical aesthetic, highly detailed, dramatic atmospheric lighting, 8k resolution, photorealistic"


def load_curated_prompts(target_dir: Path) -> list:
    """Hand-written image prompts for a reel, in narration order: scenes.json as ["...", ...] or {"prompts": [...]}."""
    p = target_dir / "scenes.json"
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        prompts = data.get("prompts") if isinstance(data, dict) else data
        return [str(x).strip() for x in (prompts or []) if str(x).strip()]
    except Exception as e:
        print(f"[Scenes] Could not read {p.name}: {e}", flush=True)
        return []


# =============================================================================
# NARRATION-TIMED SCENES (shared with generate_video.py): each picture shows while its words are heard
# =============================================================================
REEL_MAX_SCENES = 20       # at most 20 pictures a reel; fewer when the narration has fewer beats
REEL_WPM = 130             # measured reel narration pace (~2.17 words/sec), for scenes planned before the voice
REEL_SCENE_MIN_SEC = 3.0
REEL_SCENE_MAX_SEC = 9.0
REEL_LOOK_RULE = "Dramatic, atmospheric cinematic lighting that suits the moment, in rich biblical-era colors."
REEL_FRAMING_RULE = ("- The picture is a tall 9:16 vertical frame: one clear main subject, close and centered, filling "
                     "the frame; no wide panoramas with tiny figures.")
_VIDEO_GEN = None


def video_gen():
    """generate_video.py, next to this file: scene planning, prompt writers and picture bookkeeping."""
    global _VIDEO_GEN
    if _VIDEO_GEN is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("generate_video", Path(__file__).resolve().parent / "generate_video.py")
        _VIDEO_GEN = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_VIDEO_GEN)
    return _VIDEO_GEN


def reel_prompt_guide(gvm) -> str:
    """The long-form prompt rules, for a vertical reel in its own look."""
    guide = gvm.SCENE_PROMPT_GUIDE.replace("{look}", REEL_LOOK_RULE).replace(
        "a Bible documentary video (Bible Hidden Secrets Revealed)", "a vertical short-form Bible reel (Bible Hidden Secrets Revealed)")
    return guide + "\n" + REEL_FRAMING_RULE


def reel_split(total_sec: float):
    """Scene length for a reel of total_sec: about total/20 each (at least 4 s), never more than 20 scenes."""
    target = max(4.0, total_sec / REEL_MAX_SCENES)
    return target, {"max_scenes": REEL_MAX_SCENES, "min_sec": REEL_SCENE_MIN_SEC,
                    "max_sec": max(REEL_SCENE_MAX_SEC, target * 1.6)}


def reel_uses_legacy_scenes(target_dir: Path, replan: bool = False) -> bool:
    """Reels rendered before narration-timed scenes keep their pictures (reelNN_dyn_*.png) unless --replan."""
    if replan or (target_dir / "scene_plan.json").exists():
        return False
    return any((target_dir / "images").glob("reel*_dyn_*.png"))


def curated_prompt_hint(target_dir: Path) -> str:
    """scenes.json picture ideas, passed to the prompt writer as suggestions."""
    curated = load_curated_prompts(target_dir)
    if not curated:
        return ""
    return ("Picture ideas written for this reel earlier, in narration order (use one where it fits a scene's words, "
            "but always show what that scene says):\n" + "\n".join(f"- {c}" for c in curated))


def narration_timed_reel_scenes(target_dir: Path, caption_narr: str, clean_narr: str, temp_dir: Path,
                                plan_only=False, images_only=False, prompt_writer=None, auto_prompts=False,
                                force_images=False):
    """Voice first (or the script, when planning ahead), then scenes cut where the words are (at most 20), a prompt
    per scene from its words, and the pictures. Returns (scenes, image paths, plan, audio or None), or
    "NEEDS_PROMPTS" / "PLANNED"."""
    gvm = video_gen()
    images_dir = target_dir / "images"
    audio = None
    if plan_only or images_only:
        print("[Scenes] Planning the reel's scenes from the script; the voice will time them later.", flush=True)
        target, split = reel_split(len(caption_narr.split()) / (REEL_WPM / 60.0))
        plan = gvm.load_or_build_scene_plan(target_dir, caption_narr, None, None, target, wpm=REEL_WPM, **split)
    else:
        gvm.free_comfyui_memory()
        audio = synthesize_and_align_audio(clean_narr, temp_dir, target_dir.name)
        target, split = reel_split(audio[2])
        plan = gvm.load_or_build_scene_plan(target_dir, caption_narr, temp_dir / f"{target_dir.name}_transcript.json",
                                            audio[2], target, wpm=REEL_WPM, **split)
    voice_ready = plan.get("timing", "recorded") == "recorded"

    missing = [sc for sc in plan["scenes"] if gvm.needs_prompt(sc)]
    writers = gvm.prompt_writer_order(prompt_writer)
    notes = []
    if not missing:
        print(f"[Scene Prompts] All {len(plan['scenes'])} scenes already have prompts: using them as written.", flush=True)
    elif writers:
        print(f"[Scene Prompts] Writing {len(missing)} scene prompts from the narration with "
              f"{' then '.join(gvm.PROMPT_WRITER_NAMES[w] for w in writers)}...", flush=True)
        notes = gvm.write_scene_prompts_with_ai(plan, target_dir, writers, guide=reel_prompt_guide(gvm),
                                                extra_context=curated_prompt_hint(target_dir))
        missing = [sc for sc in plan["scenes"] if gvm.needs_prompt(sc)]
    if missing:
        for sc in missing:
            sc["prompt"] = build_scene_prompt(sc["text"], title=target_dir.name)
        (target_dir / gvm.SCENE_PLAN_FILE).write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"[Scene Prompts] Auto-filled {len(missing)} prompts with built-in rules (will no longer wait for manual prompt writing).", flush=True)
        missing = []
    if plan_only:
        print(f"\n✔ [Scene Plan] {len(plan['scenes'])} reel scenes planned with their prompts. Draw the pictures now "
              f"(--images-only) or render; the voice will time each scene to its words.", flush=True)
        return "PLANNED"

    scenes = [{"id": sc["id"], "prompt": f"{sc['prompt'].strip().rstrip(',.')}, {REEL_IMAGE_STYLE}, no text or lettering",
               "image": sc.get("image"), "motion": MOTIONS_CYCLE[i % len(MOTIONS_CYCLE)], "narration": sc["text"]}
              for i, sc in enumerate(plan["scenes"])]
    gvm.retire_stale_scene_images(scenes, target_dir)
    gvm.place_chosen_images(scenes, target_dir)
    paths = {}
    try:
        for sc in scenes:
            paths[sc["id"]] = generate_scene_image(sc["prompt"], sc["id"], images_dir,
                                                   force=force_images and not sc.get("image"))
    finally:
        gvm.record_scene_prompts(scenes, target_dir)  # finished pictures are kept for the next run
        gvm.free_comfyui_memory()  # Free VRAM immediately so subsequent video encoding and next jobs run clean
    return scenes, paths, plan, audio


def reel_timeline(scenes: list, timed_plan, total_duration: float) -> list:
    """When each picture is on screen. Narration-timed: from its first spoken word to the next scene's. Earlier reels:
    by each scene's share of the words."""
    if timed_plan:
        timeline = [{"id": sc["id"], "motion": scenes[i]["motion"], "start": sc["start"], "end": sc["end"]}
                    for i, sc in enumerate(timed_plan["scenes"])]
        timeline[0]["start"] = 0.0
        timeline[-1]["end"] = max(timeline[-1]["end"], total_duration)
        return timeline
    total_weight = sum(sc.get("weight", 2.0) for sc in scenes)
    timeline = []
    cur_t = 0.0
    for sc in scenes:
        dur = (sc.get("weight", 2.0) / total_weight) * total_duration
        timeline.append({"id": sc["id"], "motion": sc["motion"], "start": cur_t, "end": cur_t + dur})
        cur_t += dur
    return timeline


def load_or_build_scenes(target_dir: Path, sentences: list, ep_num: str, title: str = "") -> list:
    """Constructs strictly 18-20 distinct visual scenes from the script, with accurate biblical prompts."""
    # Check if local file has curated SCENES_CONFIG with strictly 18-20 scenes
    cand = sorted(list(target_dir.glob("generate_reel_*.py")))
    for c in cand:
        try:
            content = c.read_text(encoding="utf-8", errors="replace")
            match = re.search(r'SCENES_CONFIG\s*=\s*\[(.*?)\]\s*(?:\n\s*#|\n\w|\Z)', content, re.DOTALL)
            if match:
                local_scope = {}
                exec(match.group(0), {}, local_scope)
                cfg = local_scope.get("SCENES_CONFIG")
                if isinstance(cfg, list) and 18 <= len(cfg) <= 20:
                    return cfg
        except Exception:
            pass

    # Target: strictly 18 to 20 scenes from narration sentences
    raw_scenes = [[s] for s in sentences if s.strip()]

    # If more than 20 sentences, group shortest adjacent sentences until <= 20
    while len(raw_scenes) > 20:
        min_idx = 0
        min_words = 9999
        for i in range(len(raw_scenes) - 1):
            w = len(" ".join(raw_scenes[i] + raw_scenes[i + 1]).split())
            if w < min_words:
                min_words = w
                min_idx = i
        raw_scenes[min_idx] = raw_scenes[min_idx] + raw_scenes[min_idx + 1]
        del raw_scenes[min_idx + 1]

    # If less than 18 sentences, split compound sentences (at ; - , etc.) or split longest sentence
    while len(raw_scenes) < 18 and len(raw_scenes) > 0:
        split_idx = -1
        max_words = 0
        for i, sc in enumerate(raw_scenes):
            w = len(" ".join(sc).split())
            if w > max_words and w >= 8:
                max_words = w
                split_idx = i
        if split_idx == -1:
            break

        full_s = " ".join(raw_scenes[split_idx])
        parts = None
        for delim in [";", " - ", "—", ", and ", ", but ", ", while ", ", "]:
            if delim in full_s:
                split_cand = full_s.split(delim, 1)
                if len(split_cand[0].split()) >= 4 and len(split_cand[1].split()) >= 4:
                    parts = [split_cand[0].strip(), split_cand[1].strip()]
                    break
        if parts:
            raw_scenes[split_idx] = [parts[0]]
            raw_scenes.insert(split_idx + 1, [parts[1]])
        else:
            words = full_s.split()
            mid = len(words) // 2
            raw_scenes[split_idx] = [" ".join(words[:mid])]
            raw_scenes.insert(split_idx + 1, [" ".join(words[mid:])])

    # scenes.json prompts follow the narration: scene i takes the prompt at the same point of the reel
    curated = load_curated_prompts(target_dir)
    if curated:
        print(f"[Scenes] Using {len(curated)} hand-written prompts from scenes.json", flush=True)

    scenes = []
    for idx, sc_group in enumerate(raw_scenes):
        sc_text = " ".join(sc_group).strip()
        if curated:
            prompt = f"{curated[min(len(curated) - 1, idx * len(curated) // len(raw_scenes))]}, {REEL_IMAGE_STYLE}"
        else:
            prompt = build_scene_prompt(sc_text, title=title)
        words_count = len(sc_text.split())
        weight = round(max(1.8, words_count * 0.13), 2)
        scenes.append({
            "id": f"reel{ep_num}_dyn_{idx + 1}",
            "weight": weight,
            "motion": MOTIONS_CYCLE[idx % len(MOTIONS_CYCLE)],
            "prompt": prompt,
            "narration": sc_text
        })
    return scenes

# =============================================================================
# COMFYUI FLUX GENERATOR
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
        print(f"[ComfyUI Error] Missing executable or main.py at: {COMFY_DIR}", flush=True)
        return False
    cmd = [COMFY_PYTHON, comfy_main, "--listen", "127.0.0.1", "--port", "8188", "--lowvram"]
    flags = SUBPROCESS_CREATIONFLAGS
    subprocess.Popen(cmd, cwd=COMFY_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=flags)
    start_time = time.time()
    while time.time() - start_time < max_wait_sec:
        time.sleep(2)
        if is_comfyui_running(url):
            print(f"[ComfyUI] Server online in {time.time()-start_time:.1f}s\n", flush=True)
            return True
    print(f"[ComfyUI Error] Timed out waiting for server.", flush=True)
    return False

def create_flux_prompt(prompt_text, width=768, height=1344, steps=4, seed=None, filename_prefix="Reel_Scene"):
    if seed is None:
        import random
        seed = random.randint(1, 1000000000)
    return {
        "1": {"inputs": {"unet_name": "flux1-schnell-Q4_K_S.gguf"}, "class_type": "UnetLoaderGGUF"},
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
        "9": {"inputs": {"filename_prefix": filename_prefix, "images": ["8", 0]}, "class_type": "SaveImage"}
    }

# A scene may wait behind other ComfyUI jobs; it is abandoned only past this (or on an error / lost job)
SCENE_MAX_WAIT_SEC = 45 * 60


def comfy_queue_position(prompt_id: str):
    """0 = running now, n = n jobs ahead of it, None = not in ComfyUI's queue."""
    with urllib.request.urlopen(f"{COMFY_URL}/queue", timeout=15) as resp:
        queue = json.loads(resp.read().decode("utf-8"))
    running = queue.get("queue_running") or []
    if any(item[1] == prompt_id for item in running):
        return 0
    pending = sorted(queue.get("queue_pending") or [], key=lambda item: item[0])
    for i, item in enumerate(pending):
        if item[1] == prompt_id:
            return len(running) + i
    return None


def _render_scene_in_comfyui(prompt_text: str, scene_id: str, target_img: Path, is_valid) -> Path:
    """Submits one scene and waits for its image. Returns the saved image, or None if ComfyUI dropped the job."""
    print(f"  [FLUX] Generating scene {scene_id} via ComfyUI: \"{prompt_text[:65]}...\"", flush=True)
    workflow = create_flux_prompt(prompt_text, width=768, height=1344, steps=4, filename_prefix=f"Reel_{scene_id}")
    data = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(f"{COMFY_URL}/prompt", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        prompt_id = json.loads(resp.read().decode("utf-8"))["prompt_id"]

    t0 = time.time()
    last_note = 0.0
    missing_since = None
    while True:
        time.sleep(2.0)
        elapsed = time.time() - t0
        with urllib.request.urlopen(f"{COMFY_URL}/history/{prompt_id}", timeout=15) as resp:
            history = json.loads(resp.read().decode("utf-8"))
        if prompt_id in history:
            entry = history[prompt_id]
            outputs = entry.get("outputs", {})
            if "9" in outputs and outputs["9"].get("images"):
                info = outputs["9"]["images"][0]
                url = f"{COMFY_URL}/view?filename={info['filename']}&subfolder={info.get('subfolder', '')}&type={info.get('type', 'output')}"
                urllib.request.urlretrieve(url, str(target_img))
                if is_valid(target_img):
                    print(f"  ✔ [FLUX Saved] {scene_id}.png in {elapsed:.1f}s ({target_img.stat().st_size // 1024} KB)", flush=True)
                    return target_img
            if (entry.get("status") or {}).get("status_str") == "error":
                raise RuntimeError(f"ComfyUI reported an error while drawing {scene_id}")
        position = comfy_queue_position(prompt_id)
        if position is None and prompt_id not in history:
            # Not queued, not finished: give ComfyUI a moment (it moves jobs between lists), then treat as dropped
            missing_since = missing_since or time.time()
            if time.time() - missing_since > 30:
                print(f"  [FLUX Notice] ComfyUI dropped {scene_id} from its queue", flush=True)
                return None
        else:
            missing_since = None
        if elapsed - last_note >= 12:
            last_note = elapsed
            where = "drawing now" if position == 0 else (f"{position} job(s) ahead in ComfyUI's queue" if position else "finishing")
            print(f"    [FLUX Waiting] {scene_id}: {int(elapsed)}s elapsed, {where}...", flush=True)
        if elapsed > SCENE_MAX_WAIT_SEC:
            raise RuntimeError(f"{scene_id} waited over {SCENE_MAX_WAIT_SEC // 60} minutes in ComfyUI")


def generate_scene_image(prompt_text: str, scene_id: str, images_dir: Path, custom_image: str = None, force: bool = False) -> Path:
    images_dir.mkdir(parents=True, exist_ok=True)
    target_img = images_dir / f"{scene_id}.png"
    alt_name = re.sub(r'reel0+(\d+)', r'reel\1', scene_id)
    alt_img = images_dir / f"{alt_name}.png"

    def is_valid_9_16(p: Path) -> bool:
        if not (p.exists() and p.stat().st_size > 50000):
            return False
        try:
            with Image.open(p) as im:
                # Must be 9:16 vertical aspect ratio (height > width)
                return im.size[1] > im.size[0]
        except Exception:
            return False

    if not force:
        if is_valid_9_16(target_img):
            return target_img
        if is_valid_9_16(alt_img):
            return alt_img

    if custom_image and os.path.exists(custom_image):
        shutil.copy2(custom_image, target_img)
        return target_img

    if not is_comfyui_running():
        ensure_comfyui_running()

    if is_comfyui_running():
        # Step A: An image ComfyUI already made for THIS scene with this exact prompt (e.g. the render stopped before
        # saving it) is reused. Never another scene's image: a shared prompt would repeat the same picture.
        try:
            req_hist = urllib.request.Request(f"{COMFY_URL}/history")
            with urllib.request.urlopen(req_hist, timeout=3.0) as resp:
                hist_data = json.loads(resp.read().decode("utf-8"))
            for pid, h_item in hist_data.items():
                p_wf = h_item.get("prompt", [])
                if len(p_wf) > 2:
                    h_txt = p_wf[2].get("4", {}).get("inputs", {}).get("text", "").strip()
                    h_prefix = p_wf[2].get("9", {}).get("inputs", {}).get("filename_prefix", "")
                    if h_prefix == f"Reel_{scene_id}" and h_txt == prompt_text.strip():
                        outputs = h_item.get("outputs", {})
                        if "9" in outputs and outputs["9"].get("images"):
                            info = outputs["9"]["images"][0]
                            url = f"{COMFY_URL}/view?filename={info['filename']}&subfolder={info.get('subfolder', '')}&type={info.get('type', 'output')}"
                            urllib.request.urlretrieve(url, str(target_img))
                            if is_valid_9_16(target_img):
                                print(f"  ✔ [FLUX History Match] {scene_id}.png retrieved from previous render ({target_img.stat().st_size // 1024} KB)", flush=True)
                                return target_img
        except Exception:
            pass

        # Step B: Submit the workflow and wait while the scene is in ComfyUI's queue. Other tools may share ComfyUI,
        # so a scene can wait behind their jobs: keep waiting as long as it is queued or running (up to
        # SCENE_MAX_WAIT_SEC). If ComfyUI goes down, relaunch it and submit the scene once more.
        for attempt in (1, 2):
            try:
                img = _render_scene_in_comfyui(prompt_text, scene_id, target_img, is_valid_9_16)
                if img:
                    return img
                break
            except (urllib.error.URLError, ConnectionError, OSError) as e:
                print(f"  [FLUX Notice] ComfyUI connection lost on {scene_id} ({e})", flush=True)
                if attempt == 1 and ensure_comfyui_running():
                    print(f"  [FLUX] ComfyUI is back; submitting {scene_id} again", flush=True)
                    continue
                break
            except RuntimeError as e:
                print(f"  [FLUX Notice] {e}", flush=True)
                break

    if is_valid_9_16(target_img):
        return target_img

    # No placeholder images: a cached placeholder would be reused by every later render
    raise RuntimeError(f"ComfyUI could not generate scene {scene_id} (is it running at http://127.0.0.1:8188, and not busy with another tool's jobs?). No placeholder was saved: run the render again; finished scenes are kept.")


# =============================================================================
# TEXT CARDS & THUMBNAIL GENERATOR WITH BACKGROUND IMAGE
# =============================================================================
def generate_text_card(card_type: str, ep_num: str, hook_text: str, thumb_text: str, scripture_ref: str, images_dir: Path, bg_image_path: Path = None) -> Path:
    """Generates high-res 768x1344 text card with scene background, gold borders, and logo."""
    W, H = 768, 1344
    card_path = images_dir / f"reel{ep_num}_card_{card_type}.png"

    # 1. Base Image: Use real generated scene image if available, else dark blue canvas
    if bg_image_path and os.path.exists(bg_image_path):
        try:
            base = Image.open(bg_image_path).convert("RGBA").resize((W, H), Image.Resampling.BICUBIC)
            # Apply dark cinematic scrim/vignette overlay
            scrim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            sdraw = ImageDraw.Draw(scrim)
            for y in range(H):
                # Heavy darkening at top (for badge/logo) and bottom (for CTA), medium at center
                dist = abs(y / H - 0.5) * 2
                alpha = int(140 + 80 * dist)
                sdraw.line([(0, y), (W, y)], fill=(6, 8, 14, alpha))
            img = Image.alpha_composite(base, scrim)
        except Exception:
            img = Image.new("RGBA", (W, H), (10, 12, 20, 255))
    else:
        img = Image.new("RGBA", (W, H), (10, 12, 20, 255))

    draw = ImageDraw.Draw(img)

    # 2. Gold borders top & bottom
    draw.rectangle([0, 0, W, 10], fill=(212, 175, 55, 255))
    draw.rectangle([0, H - 10, W, H], fill=(212, 175, 55, 255))

    # 3. Watermark logo
    if os.path.exists(LOCAL_LOGO):
        try:
            logo = Image.open(LOCAL_LOGO).convert("RGBA").resize((75, 75), Image.Resampling.LANCZOS)
            r, g, b, a = logo.split()
            a = a.point(lambda p: int(p * 0.70))
            logo.putalpha(a)
            img.paste(logo, (36, 36), logo)
        except Exception:
            pass

    # 4. Fonts
    try:
        font_badge = ImageFont.truetype("arialbd.ttf", 36)
        font_main = ImageFont.truetype("arialbd.ttf", 62)
        font_sub = ImageFont.truetype("arialbd.ttf", 38)
        font_cta = ImageFont.truetype("arialbd.ttf", 40)
        font_small = ImageFont.truetype("arialbd.ttf", 28)
    except Exception:
        font_badge = font_main = font_sub = font_cta = font_small = ImageFont.load_default()

    # 5. Episode Badge
    badge_text = f"EPISODE {ep_num}".upper()
    bw = draw.textlength(badge_text, font=font_badge)
    draw.rounded_rectangle([W // 2 - bw // 2 - 28, 126, W // 2 + bw // 2 + 28, 186], radius=16, fill=(212, 175, 55, 255))
    draw.text((W // 2, 156), badge_text, font=font_badge, fill=(0, 0, 0, 255), anchor="mm")

    # 6. Headline Typography
    display_text = thumb_text if card_type == "thumbnail" else hook_text
    words = display_text.split()
    lines, current = [], ""
    for w in words:
        if len(current) + len(w) + 1 <= 20:
            current = (current + " " + w).strip()
        else:
            if current: lines.append(current)
            current = w
    if current: lines.append(current)

    line_h = 80
    start_y = H // 2 - (len(lines) * line_h) // 2

    for i, line in enumerate(lines):
        y = start_y + i * line_h
        draw.text((W // 2 + 3, y + 3), line, font=font_main, fill=(0, 0, 0, 230), anchor="mm")
        draw.text((W // 2, y), line, font=font_main, fill=(255, 230, 20, 255), anchor="mm")

    # 7. Scripture Badge
    if scripture_ref:
        sw = draw.textlength(scripture_ref, font=font_sub)
        draw.rounded_rectangle([W // 2 - sw // 2 - 24, H * 3 // 4 - 30, W // 2 + sw // 2 + 24, H * 3 // 4 + 30], radius=14, fill=(0, 0, 0, 190))
        draw.text((W // 2, H * 3 // 4), scripture_ref, font=font_sub, fill=(255, 255, 255, 240), anchor="mm")

    # 8. Compelling CTA Button
    cta_line = "FULL EPISODE ON OUR CHANNEL"
    cw = draw.textlength(cta_line, font=font_cta)
    draw.rounded_rectangle([W // 2 - cw // 2 - 26, H - 216, W // 2 + cw // 2 + 26, H - 150], radius=18, fill=(212, 175, 55, 230))
    draw.text((W // 2, H - 183), cta_line, font=font_cta, fill=(0, 0, 0, 255), anchor="mm")

    # 9. Channel Branding
    draw.text((W // 2, H - 110), "FOLLOW & SUBSCRIBE FOR FULL EPISODES", font=font_small, fill=(220, 220, 220, 230), anchor="mm")
    draw.text((W // 2, H - 65), "BIBLE HIDDEN SECRETS REVEALED", font=font_badge, fill=(212, 175, 55, 220), anchor="mm")

    final_card = img.convert("RGB")
    final_card.save(str(card_path), "PNG")
    return card_path

# =============================================================================
# WHISPER TRANSCRIPTION & CAPTION CHUNKING
# =============================================================================
def align_transcript_with_script(script_text: str, whisper_words: list) -> list:
    def _clean(tok): return re.sub(r'[^\w]', '', tok.lower())
    script_tokens = script_text.split()
    clean_script = [_clean(t) for t in script_tokens]
    clean_whisper = [_clean(w['word']) for w in whisper_words]
    matcher = difflib.SequenceMatcher(None, clean_script, clean_whisper)
    aligned = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for si, wj in zip(range(i1, i2), range(j1, j2)):
                aligned.append({'word': script_tokens[si], 'start': whisper_words[wj]['start'], 'end': whisper_words[wj]['end']})
        elif tag == 'replace':
            num_s = i2 - i1
            w_start, w_end = whisper_words[j1]['start'], whisper_words[j2-1]['end']
            dur = (w_end - w_start) / max(num_s, 1)
            for idx, si in enumerate(range(i1, i2)):
                aligned.append({'word': script_tokens[si], 'start': round(w_start + idx * dur, 2), 'end': round(w_start + (idx + 1) * dur, 2)})
        elif tag == 'delete':
            prev_end = aligned[-1]['end'] if aligned else 0.0
            next_start = whisper_words[j1]['start'] if j1 < len(whisper_words) else prev_end + 0.3
            num_s = i2 - i1
            dur = max(0.1, (next_start - prev_end) / max(num_s, 1))
            for idx, si in enumerate(range(i1, i2)):
                aligned.append({'word': script_tokens[si], 'start': round(prev_end + idx * dur, 2), 'end': round(prev_end + (idx + 1) * dur, 2)})
    return aligned

def format_scripture_words(all_words: list) -> list:
    i = 0
    cleaned = []
    def _clean_token(w): return re.sub(r'^[^\w]+|[^\w]+$', '', w).lower()
    while i < len(all_words):
        w = all_words[i]
        raw_tok = w['word'].strip()
        tok = _clean_token(raw_tok)
        has_prefix, prefix_str, book_idx = False, '', i
        if tok in PREFIX_NUMS and i + 1 < len(all_words):
            next_tok = _clean_token(all_words[i+1]['word'])
            if next_tok in BIBLE_BOOKS_BASE:
                has_prefix, prefix_str, book_idx = True, PREFIX_NUMS[tok] + ' ', i + 1
        book_tok = _clean_token(all_words[book_idx]['word'])
        if has_prefix or book_tok in BIBLE_BOOKS_BASE:
            canonical_book = prefix_str + BIBLE_BOOKS_BASE[book_tok]
            if book_idx + 1 < len(all_words):
                next_word_raw = all_words[book_idx + 1]['word'].strip()
                m_punct = re.search(r'([^\w]+)$', next_word_raw)
                trailing_punct = m_punct.group(1) if m_punct else ''
                next_word_clean = next_word_raw[:-len(trailing_punct)] if trailing_punct else next_word_raw
                if re.match(r'^\d+[.:]\d+(?:[\-]\d+)?$', next_word_clean):
                    cv_clean = next_word_clean.replace('.', ':')
                    cleaned.append({'word': f'{canonical_book} {cv_clean}{trailing_punct}', 'start': w['start'], 'end': all_words[book_idx + 1]['end']})
                    i = book_idx + 2
                    continue
        cleaned.append(w)
        i += 1
    return cleaned

def load_chunked_captions(script_text: str, transcript_data: dict, max_words=4) -> list:
    all_raw_words = []
    for seg in transcript_data.get("segments", []):
        for w in seg.get("words", []):
            all_raw_words.append({"word": w["word"].strip(), "start": w["start"], "end": w["end"]})

    aligned_words = align_transcript_with_script(script_text, all_raw_words)
    formatted_words = format_scripture_words(aligned_words)
    max_chunk_width, word_spacing = 680, 14
    try: font_word = ImageFont.truetype("arialbd.ttf", 56)
    except Exception: font_word = ImageFont.load_default()

    draw = ImageDraw.Draw(Image.new("RGB", (768, 1344)))
    chunks, curr_chunk, curr_w = [], [], 0
    for w in formatted_words:
        w_len = draw.textlength(w["word"], font=font_word)
        prev_ended = False
        if curr_chunk:
            last_w = re.sub(r'[^\w.!?]+$', '', curr_chunk[-1]["word"].strip())
            if last_w.endswith(('.', '!', '?')) and not re.search(r'\b(?:vs|dr|mr|mrs|ms|gen|exod|lev|num|deut)\.$', last_w, re.IGNORECASE):
                prev_ended = True
        if curr_chunk and (prev_ended or len(curr_chunk) >= max_words or (curr_w + word_spacing + w_len) > max_chunk_width):
            chunks.append({"start": curr_chunk[0]["start"], "end": curr_chunk[-1]["end"],
                           "words": [{"word": x["word"].strip(), "start": x["start"], "end": x["end"]} for x in curr_chunk]})
            curr_chunk, curr_w = [w], w_len
        else:
            curr_chunk.append(w)
            curr_w += (word_spacing if len(curr_chunk) > 1 else 0) + w_len
    if curr_chunk:
        chunks.append({"start": curr_chunk[0]["start"], "end": curr_chunk[-1]["end"],
                       "words": [{"word": x["word"].strip(), "start": x["start"], "end": x["end"]} for x in curr_chunk]})
    return chunks

# =============================================================================
# KEN BURNS MOTION & FRAME COMPOSITING
# =============================================================================
def apply_motion(img: Image.Image, motion_cfg: dict, t_frac: float, out_size=(768, 1344)) -> Image.Image:
    W, H = out_size
    orig_w, orig_h = img.size
    ease_t = 0.5 * (1 - math.cos(math.pi * t_frac))
    start_z = motion_cfg.get("start_zoom", 1.0)
    end_z = motion_cfg.get("end_zoom", 1.15)
    zoom = start_z + (end_z - start_z) * ease_t
    crop_w, crop_h = int(orig_w / zoom), int(orig_h / zoom)
    pan_y = motion_cfg.get("pan_y", (0.5, 0.5))
    pan_x = motion_cfg.get("pan_x", (0.5, 0.5))
    curr_py = pan_y[0] + (pan_y[1] - pan_y[0]) * ease_t
    curr_px = pan_x[0] + (pan_x[1] - pan_x[0]) * ease_t
    shift_y = max(0, min(orig_h - crop_h, int((orig_h - crop_h) * curr_py)))
    shift_x = max(0, min(orig_w - crop_w, int((orig_w - crop_w) * curr_px)))
    cropped = img.crop((shift_x, shift_y, shift_x + crop_w, shift_y + crop_h))
    return cropped.resize(out_size, Image.Resampling.BICUBIC).convert("RGBA")

# =============================================================================
# AUDIO SYNTHESIS & SOUNDTRACK MASTERING (EPISODE 80 / 60 VIBEVOICE BENCHMARK)
# =============================================================================
def synthesize_and_align_audio(script_text: str, temp_dir: Path, ep_title: str) -> tuple:
    import whisper
    raw_voice_path = temp_dir / f"{ep_title}_raw_voice.wav"
    transcript_path = temp_dir / f"{ep_title}_transcript.json"
    master_audio_path = temp_dir / f"{ep_title}_master_soundtrack.wav"

    voice_script = prepare_voice_script(script_text)

    # 1. Synthesize Studio Voiceover with Microsoft VibeVoice Cloned Voice (Episode 80 Standard)
    chunks_dir = Path(str(raw_voice_path) + "_chunks")
    if raw_voice_path.exists() and cached_script_differs(temp_dir / f"{ep_title}_voice_script.txt", voice_script):
        print("[Voiceover] The script changed since the cached recording: re-recording the narration "
              "(old audio kept in temp/_previous).", flush=True)
        retire_stale_audio(temp_dir, [raw_voice_path, chunks_dir, transcript_path, master_audio_path])
    is_cloned_voice = raw_voice_path.exists() and chunks_dir.exists()

    if not is_cloned_voice:
        # Invalidate old non-cloned audio artifacts so Whisper and master soundtrack re-align
        for old_p in [raw_voice_path, transcript_path, master_audio_path]:
            if old_p.exists():
                try: old_p.unlink()
                except Exception: pass

        print("\n=== [Audio Step 1/3] Generating Studio Voiceover with Microsoft VibeVoice Cloned Voice ===", flush=True)
        # Ensure ComfyUI yields VRAM before starting VibeVoice on 4GB GPU
        try:
            video_gen().free_comfyui_memory()
        except Exception:
            pass

        voice_script_file = temp_dir / f"{ep_title}_voice_script.txt"
        voice_script_file.write_text(voice_script, encoding="utf-8")

        vv_py, vv_script = find_vibevoice_paths()
        success = False

        if vv_py and vv_script and os.path.exists(vv_py) and os.path.exists(vv_script):
            try:
                print(f"[VibeVoice] Initializing synthesis via {Path(vv_script).name} (steps=5)...", flush=True)
                cmd = [
                    vv_py, "-u", vv_script,
                    "--text_file", str(voice_script_file),
                    "--output", str(raw_voice_path),
                    "--steps", "5"
                ]
                cf = SUBPROCESS_CREATIONFLAGS
                with ProgressHeartbeat("Voiceover Synthesis", interval_sec=60):
                    proc = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        encoding="utf-8",
                        errors="replace",
                        creationflags=cf
                    )
                    for line in proc.stdout:
                        print(line, end="", flush=True)
                    proc.wait()
                if proc.returncode == 0 and raw_voice_path.exists():
                    success = True
                else:
                    print(f"[VibeVoice Notice] Subprocess returned code {proc.returncode}", flush=True)
            except Exception as e:
                print(f"[VibeVoice Warning] Subprocess synthesis failed: {e}", flush=True)

        if not success:
            try:
                if str(PROJECT_DIR) not in sys.path:
                    sys.path.insert(0, str(PROJECT_DIR))
                from vibevoice_engine import synthesize_cloned_speech
                with ProgressHeartbeat("In-Process Voiceover", interval_sec=60):
                    synthesize_cloned_speech(voice_script, str(raw_voice_path))
                success = raw_voice_path.exists()
            except Exception as e:
                print(f"[VibeVoice Warning] Fallback to edge-tts due to: {e}", flush=True)

        if not success or not raw_voice_path.exists():
            import edge_tts
            async def _gen():
                comm = edge_tts.Communicate(voice_script, voice="en-GB-RyanNeural", rate="-2%", pitch="-1Hz")
                await comm.save(str(raw_voice_path))
            asyncio.run(_gen())

        print(f"[Voice audio saved] -> {raw_voice_path.name}", flush=True)

    # 2. Whisper Timestamp Alignment
    if not transcript_path.exists():
        print("\n=== Transcribing Word Timestamps with Whisper ===", flush=True)
        print("[Whisper] Aligning speech timestamps (this takes 1-2 minutes, please wait)...", flush=True)
        with ProgressHeartbeat("Whisper Alignment", interval_sec=60):
            import warnings
            warnings.filterwarnings("ignore", category=UserWarning, module="whisper")
            model = whisper.load_model("base", device="cpu")
            transcript_res = model.transcribe(str(raw_voice_path), word_timestamps=True, fp16=False)
            transcript_path.write_text(json.dumps(transcript_res, indent=2), encoding="utf-8")
    else:
        transcript_res = json.loads(transcript_path.read_text(encoding="utf-8"))

    total_duration = transcript_res["segments"][-1]["end"]
    print(f"Audio Duration: {total_duration:.2f}s across {len(transcript_res['segments'])} segments.", flush=True)

    # 3. Master voice track: narration only, no background music (music beds caused copyright claims)
    if not master_audio_path.exists():
        print("\n=== Mastering Voiceover (voice only, no music) ===", flush=True)
        master_cmd = [
            FFMPEG_EXE, "-y",
            "-hide_banner", "-loglevel", "error",
            "-i", str(raw_voice_path),
            "-filter_complex", "[0:a]highpass=f=75,lowpass=f=7200,equalizer=f=220:t=q:w=1.2:g=2.5,equalizer=f=3400:t=q:w=1.8:g=-4.5,equalizer=f=5500:t=q:w=1.5:g=-5.0,deesser=i=0.6:m=0.5:f=0.5,compand=attacks=0.01:decays=0.08:points=-80/-80|-22/-10|-10/-3|0/0,volume=3.2,loudnorm=I=-11.5:TP=-0.5:LRA=5[out]",
            "-map", "[out]",
            "-ar", "44100",
            str(master_audio_path)
        ]
        cf = SUBPROCESS_CREATIONFLAGS
        with ProgressHeartbeat("Voice Mastering", interval_sec=60):
            subprocess.run(master_cmd, check=True, creationflags=cf)
        print(f"[Audio] Voice master ready: {master_audio_path}", flush=True)
    else:
        print(f"[Audio] Master soundtrack already exists: {master_audio_path}", flush=True)

    return master_audio_path, transcript_res, total_duration

# =============================================================================
# THUMBNAIL & FAST AD COMBINER ENGINES (NO FULL RE-RENDER)
# =============================================================================
def legacy_reel_metadata(txt_path: Path) -> dict:
    """Thumbnail fields from an older reel's metadata.txt ("TITLE: Headline — Subtitle | Bible Secrets #51")."""
    text = txt_path.read_text(encoding="utf-8", errors="replace")

    def field(name):
        m = re.search(rf"^{name}:[ \t]*(.+)$", text, re.MULTILINE)
        return m.group(1).strip() if m else ""

    title = re.sub(r"\s*\|\s*Bible Secrets\s*#\d+\s*$", "", field("TITLE"), flags=re.IGNORECASE)
    head, _, sub = title.partition(" — ")
    if not sub and len(title) > 26:
        # A long title fits the 2-line headline only in part: keep ~24 characters up front, the rest as subtitle
        words, n = title.split(), 1
        while n < len(words) - 1 and len(" ".join(words[:n + 1])) <= 24:
            n += 1
        head, sub = " ".join(words[:n]), " ".join(words[n:])
    desc = text.split("DESCRIPTION:", 1)[1].split("HASHTAGS:", 1)[0] if "DESCRIPTION:" in text else ""
    verse = re.search(r"\b(?:[1-3] )?[A-Z][a-z]+ \d+:\d+(?:-\d+)?", desc)
    meta = {"title": head.strip() or title, "hook": field("HOOK")}
    if sub:
        meta["thumbnail_kicker"] = sub.strip().upper()
    if verse:
        meta["thumbnail_scripture"] = verse.group(0).upper()
    return meta


def regenerate_thumbnail_only(target_dir: Path, week_num: int, reel_num: int) -> Path:
    """Regenerates the Option-C composite thumbnail and text cards in seconds without re-rendering video."""
    meta_p = target_dir / "metadata.json"
    meta = {}
    if meta_p.exists():
        try:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
        except Exception:
            pass
    elif (target_dir / "metadata.txt").exists():
        meta = legacy_reel_metadata(target_dir / "metadata.txt")

    ep_num = f"{reel_global_number(target_dir):02d}"
    title = meta.get("title") or target_dir.name.replace("_", " ").title()
    hook_text = meta.get("hook_text") or meta.get("hook") or title.upper()
    thumb_text = meta.get("thumbnail_text") or meta.get("hook") or title.upper()
    scripture_ref = meta.get("scripture") or meta.get("scriptures") or ""

    images_dir = target_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    target_thumb = target_dir / "thumbnail.jpg"

    # Resolve background image: a scene image (never a text card, which carries old wording), first scene first.
    # Older reels keep their scene images in the reel folder itself.
    bg_candidates = [
        images_dir / f"reel{ep_num}_dyn_1.png",
        images_dir / f"reel{int(ep_num)}_dyn_1.png",
        images_dir / f"reel{ep_num}_scene_01.png",
    ]
    bg_candidates += [target_dir / p.name for p in bg_candidates]
    if not any(p.exists() for p in bg_candidates):
        def scene_order(p):
            nums = re.findall(r"\d+", p.stem)
            return (int(nums[-1]) if nums else 999, p.name)
        scenes = [p for p in list(images_dir.glob("reel*.png")) + list(target_dir.glob("reel*.png")) if "card" not in p.name]
        if scenes:
            bg_candidates.append(sorted(scenes, key=scene_order)[0])

    bg_img = next((p for p in bg_candidates if p.exists()), None)

    try:
        sys.path.insert(0, str(PROJECT_DIR / "scripts"))
        from reel_thumbnail_builder import generate_composite_reel_thumbnail
        badge_text = meta.get("thumbnail_badge") or meta.get("category") or "THE SECRET BIBLE CODE"
        generate_composite_reel_thumbnail(
            base_img_path=str(bg_img) if bg_img else None,
            title=title,
            week_tag=badge_text,
            scripture=meta.get("thumbnail_scripture") or scripture_ref,
            subtitle=meta.get("thumbnail_kicker") or meta.get("subtitle") or meta.get("hook_text", ""),
            out_path=str(target_thumb),
            out_size=(1080, 1920),
            badge_text=badge_text,
            line1=meta.get("thumbnail_line1"),
            line2=meta.get("thumbnail_line2"),
            kicker=meta.get("thumbnail_kicker")
        )
        shutil.copy2(target_thumb, images_dir / f"reel{ep_num}_card_thumbnail.png")
        print(f"[SUCCESS] Modern Reel Thumbnail generated: {target_thumb.name} ({target_thumb.stat().st_size // 1024} KB)", flush=True)
    except Exception as e:
        print(f"[Thumbnail Notice] Composite builder fallback: {e}", flush=True)
        thumb_card_p = generate_text_card("thumbnail", ep_num, hook_text, thumb_text, scripture_ref, images_dir, bg_image_path=bg_img)
        shutil.copy2(thumb_card_p, target_thumb)
        print(f"[SUCCESS] Text card thumbnail generated: {target_thumb.name}", flush=True)

    generate_text_card("hook", ep_num, hook_text, thumb_text, scripture_ref, images_dir, bg_image_path=bg_img)
    return target_thumb


def render_ad_clip(ad_num: int, force: bool = False) -> Path:
    """Renders or retrieves a cached 768x1344 broadcast ad outro clip for fast concatenation."""
    if ad_num not in AD_VARIANTS:
        raise ValueError(f"Unknown ad variant {ad_num}. Choose 1, 2, or 3.")

    ad_cfg = AD_VARIANTS[ad_num]
    shared_dir = PROJECT_DIR / "shared_assets"
    shared_dir.mkdir(parents=True, exist_ok=True)
    ad_clip_path = shared_dir / f"ad_outro_{ad_num}.mp4"

    cached_ad_script = shared_dir / f"temp_ad_{ad_num}" / f"ad_{ad_num}_voice_script.txt"
    ad_wording_changed = cached_script_differs(cached_ad_script, prepare_voice_script(ad_cfg["script"].strip()))
    if ad_clip_path.exists() and ad_clip_path.stat().st_size > 100000 and not force and not ad_wording_changed:
        print(f"[Ad Engine] Using pre-rendered ad outro clip: {ad_clip_path.name}", flush=True)
        return ad_clip_path

    print(f"\n[Ad Engine] Rendering broadcast ad outro #{ad_num}: {ad_cfg['title']}...", flush=True)
    temp_ad_dir = shared_dir / f"temp_ad_{ad_num}"
    temp_ad_dir.mkdir(parents=True, exist_ok=True)

    # 1. Synthesize audio & timestamps
    ad_script = ad_cfg["script"].strip()
    master_audio, transcript_res, ad_duration = synthesize_and_align_audio(ad_script, temp_ad_dir, f"ad_{ad_num}")

    # 2. Render ad motion frames
    graphic_p = PROJECT_DIR / ad_cfg["graphic"]
    if not graphic_p.exists():
        graphic_p = shared_dir / "merch_book_ad.png"

    ad_img = Image.open(graphic_p).convert("RGB")
    logo_img = None
    if os.path.exists(LOCAL_LOGO):
        try:
            l_raw = Image.open(LOCAL_LOGO).convert("RGBA").resize((75, 75), Image.Resampling.LANCZOS)
            r, g, b, a = l_raw.split()
            a = a.point(lambda p: int(p * 0.58))
            l_raw.putalpha(a)
            logo_img = l_raw
        except Exception:
            pass

    chunks = load_chunked_captions(ad_script, transcript_res, max_words=4)
    try: font_word = ImageFont.truetype("arialbd.ttf", 56)
    except Exception: font_word = ImageFont.load_default()

    total_ad_frames = int(ad_duration * FPS)
    temp_ad_video = temp_ad_dir / f"ad_{ad_num}_frames.mp4"
    writer = imageio.get_writer(
        str(temp_ad_video), fps=FPS, codec="libx264",
        ffmpeg_params=["-pix_fmt", "yuv420p", "-crf", "18", "-preset", "veryfast"]
    )

    motion = ad_cfg.get("motion", {"type": "slow_push_in", "start_zoom": 1.0, "end_zoom": 1.05, "pan_y": (0.5, 0.5)})
    for f in range(total_ad_frames):
        t = f / FPS
        t_frac = min(1.0, max(0.0, t / max(0.01, ad_duration)))
        frame_img = apply_motion(ad_img, motion, t_frac, out_size=(768, 1344))

        # Safe captions overlay
        active_chunk = None
        for c in chunks:
            if c["start"] <= t <= c["end"] + 0.15:
                active_chunk = c
                break
        if active_chunk:
            overlay = Image.new("RGBA", (768, 1344), (0, 0, 0, 0))
            draw_ov = ImageDraw.Draw(overlay)
            pad_x, pad_y, word_sp = 24, 12, 14
            total_w = sum(draw_ov.textlength(w["word"], font=font_word) for w in active_chunk["words"]) + word_sp * (len(active_chunk["words"]) - 1)
            card_w = int(total_w + pad_x * 2)
            card_h = font_word.size + 28
            card_x = (768 - card_w) // 2
            card_y = int(1344 * 0.74)
            draw_ov.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=18, fill=(0, 0, 0, 160))

            cur_x = card_x + pad_x
            text_y = card_y + 12
            for w in active_chunk["words"]:
                wl = draw_ov.textlength(w["word"], font=font_word)
                is_active = (w["start"] <= t <= w["end"] + 0.05)
                color = (255, 230, 0, 255) if is_active else (255, 255, 255, 245)
                draw_ov.text((cur_x, text_y), w["word"], font=font_word, fill=color)
                cur_x += wl + word_sp
            frame_img = Image.alpha_composite(frame_img, overlay)

        if logo_img:
            frame_img.paste(logo_img, (36, 36), logo_img)

        writer.append_data(np.array(frame_img.convert("RGB")))

    writer.close()

    # 3. Mux final ad outro clip
    mux_cmd = [
        FFMPEG_EXE, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(temp_ad_video),
        "-i", str(master_audio),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "320k",
        "-movflags", "+faststart",
        "-shortest", str(ad_clip_path)
    ]
    cf = SUBPROCESS_CREATIONFLAGS
    subprocess.run(mux_cmd, check=True, creationflags=cf)
    print(f"[Ad Engine] Ad outro clip successfully created: {ad_clip_path.name} ({ad_duration:.1f}s)", flush=True)
    return ad_clip_path


def resolve_ad_clip(ad_source: Any) -> Path:
    """Resolves an ad reference (integer variant, filename, or stem) to a video file path in Adz-Video or shared_assets."""
    if not ad_source:
        ad_source = 1
    ref_str = str(ad_source).strip()

    # 1. Check C:\Projects\Adz-Video
    if ADZ_DIR.exists():
        direct = ADZ_DIR / ref_str
        if direct.is_file():
            return direct
        cand_mp4 = ADZ_DIR / f"{ref_str}.mp4"
        if cand_mp4.is_file():
            return cand_mp4
        if ref_str.isdigit():
            cand_num = ADZ_DIR / f"ad_outro_{ref_str}.mp4"
            if cand_num.is_file():
                return cand_num
            # Match any ad ending with _{ref_str}.mp4 (e.g. ad_outro_hidden_secrets_4.mp4)
            num_matches = list(ADZ_DIR.glob(f"*_{ref_str}.mp4"))
            if num_matches:
                return num_matches[0]
        # Text stem match (e.g. "merch", "ot_gems", "nt_gems", "hidden_secrets")
        stem_matches = list(ADZ_DIR.glob(f"*{ref_str}*.mp4"))
        if stem_matches:
            return stem_matches[0]

    # 2. Check shared_assets in PROJECT_DIR
    shared_dir = PROJECT_DIR / "shared_assets"
    if shared_dir.exists():
        shared_file = shared_dir / ref_str
        if shared_file.is_file():
            return shared_file
        shared_mp4 = shared_dir / f"{ref_str}.mp4"
        if shared_mp4.is_file():
            return shared_mp4
        if ref_str.isdigit():
            shared_num = shared_dir / f"ad_outro_{ref_str}.mp4"
            if shared_num.is_file():
                return shared_num
            num_matches = list(shared_dir.glob(f"*_{ref_str}.mp4"))
            if num_matches:
                return num_matches[0]
        stem_matches = list(shared_dir.glob(f"*{ref_str}*.mp4"))
        if stem_matches:
            return stem_matches[0]

    # 3. Fallback to render_ad_clip if it's one of the legacy AD_VARIANTS
    if ref_str.isdigit() and int(ref_str) in AD_VARIANTS:
        return render_ad_clip(int(ref_str))

    raise FileNotFoundError(f"Could not find advertisement video for '{ad_source}' in {ADZ_DIR} or {shared_dir}")


def combine_reel_with_ad(main_video_path: Path, ad_num: Any, output_path: Path) -> Path:
    """Combines a base reel video and an ad outro clip via fast concat without re-rendering."""
    if not main_video_path.exists():
        raise FileNotFoundError(f"Base reel video not found: {main_video_path}")

    ad_clip_path = resolve_ad_clip(ad_num)

    concat_list_path = main_video_path.parent / "temp" / f"concat_ad_{Path(str(ad_num)).stem}.txt"
    concat_list_path.parent.mkdir(parents=True, exist_ok=True)
    with open(concat_list_path, "w", encoding="utf-8") as f:
        p1 = str(main_video_path).replace("\\", "/").replace("'", "'\\''")
        p2 = str(ad_clip_path).replace("\\", "/").replace("'", "'\\''")
        f.write(f"file '{p1}'\n")
        f.write(f"file '{p2}'\n")

    print(f"[Combine] Concat demuxing {main_video_path.name} + {ad_clip_path.name} -> {output_path.name}...", flush=True)
    temp_target = output_path.parent / f"temp_comb_{output_path.name}"

    concat_cmd = [
        FFMPEG_EXE, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list_path),
        "-c", "copy",
        "-movflags", "+faststart",
        str(temp_target)
    ]
    cf = SUBPROCESS_CREATIONFLAGS
    res = subprocess.run(concat_cmd, creationflags=cf)

    if res.returncode != 0 or not temp_target.exists() or temp_target.stat().st_size < 10000:
        print(f"[Combine Notice] Stream copy concat failed; falling back to re-encode concat...", flush=True)
        fallback_cmd = [
            FFMPEG_EXE, "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(main_video_path),
            "-i", str(ad_clip_path),
            "-filter_complex",
            "[1:v]scale=768:1344:force_original_aspect_ratio=decrease,pad=768:1344:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[v1];[0:v][0:a][v1][1:a]concat=n=2:v=1:a=1[v][a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
            "-c:a", "aac", "-b:a", "320k",
            "-movflags", "+faststart",
            str(temp_target)
        ]
        subprocess.run(fallback_cmd, check=True, creationflags=cf)

    if output_path.exists():
        try: os.remove(str(output_path))
        except Exception: pass
    shutil.move(str(temp_target), str(output_path))
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"[SUCCESS] Fast ad combine completed: {output_path.name} ({size_mb:.1f} MB)", flush=True)

    # Persist ad attachment state in reel metadata.json
    meta_p = output_path.parent / "metadata.json"
    if meta_p.exists():
        try:
            m_data = json.loads(meta_p.read_text(encoding="utf-8"))
            ad_comment = generate_pinned_comment_for_ad(ad_num, ad_clip_path.name)
            m_data["ad_outro"] = {
                "attached": True,
                "filename": ad_clip_path.name,
                "title": f"Ad: {ad_clip_path.stem.replace('_', ' ').title()}",
                "attached_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "pinned_comment": ad_comment
            }
            m_data["pinned_comment"] = ad_comment
            meta_p.write_text(json.dumps(m_data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[Metadata] Pinned comment updated to match attached ad: {ad_clip_path.name}", flush=True)
        except Exception:
            pass

    return output_path


# =============================================================================
# SINGLE REEL PRODUCTION PIPELINE
# =============================================================================
def render_reel(
    week_num: int,
    reel_num: int,
    target_dir: Path,
    force_rebuild: bool = False,
    images_only: bool = False,
    force_images: bool = False,
    ad_num: Any = None,
    speed: float = None,
    thumbnail_only: bool = False,
    combine_ad_only: bool = False,
    remove_ad_only: bool = False,
    comment_only: bool = False,
    plan_only: bool = False,
    replan: bool = False,
    auto_prompts: bool = False,
    prompt_writer: str = None
) -> Path:
    print(f"\n{'='*74}", flush=True)
    print(f"▶ PRODUCING REEL W{week_num:02d} {reel_key(target_dir) or reel_num}: {target_dir.name}", flush=True)
    print(f"Benchmark Standard: Episode 57 / 768x1344 Native Ken Burns + Safe Captions", flush=True)
    print(f"{'='*74}", flush=True)

    final_vid_name = f"{target_dir.name}_final_reel.mp4"
    final_output = target_dir / final_vid_name

    # Quick Mode 1: Regenerate Thumbnail Only (No video render)
    if thumbnail_only and not combine_ad_only and not remove_ad_only and not comment_only:
        print(f"\n[Quick Mode] Regenerating Option-C composite thumbnail for {target_dir.name}...", flush=True)
        return regenerate_thumbnail_only(target_dir, week_num, reel_num)

    # Quick Mode 2c: Trigger / Sync Pinned Comment Only (No video render)
    if comment_only:
        print(f"\n[Quick Mode] Triggering pinned comment update for {target_dir.name}...", flush=True)
        meta_p = target_dir / "metadata.json"
        if not meta_p.exists():
            print(f"[ERROR] metadata.json not found in {target_dir.name}!", flush=True)
            return None
        try:
            m_data = json.loads(meta_p.read_text(encoding="utf-8"))
            chosen_ad = ad_num
            if not chosen_ad:
                ad_info = m_data.get("ad_outro", {})
                if ad_info.get("attached"):
                    chosen_ad = ad_info.get("filename")

            new_comment = generate_pinned_comment_for_ad(chosen_ad)
            m_data["pinned_comment"] = new_comment
            if "ad_outro" in m_data and m_data["ad_outro"].get("attached"):
                m_data["ad_outro"]["pinned_comment"] = new_comment
            meta_p.write_text(json.dumps(m_data, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[TRIGGER] Pinned comment updated in metadata.json based on attached ad: {chosen_ad or 'Clean/None'}\n", flush=True)
            print(f"--- Pinned Comment Preview ---\n{new_comment}\n------------------------------\n", flush=True)
            return meta_p
        except Exception as e:
            print(f"[ERROR] Failed to update pinned comment: {e}", flush=True)
            return None

    # Quick Mode 2a: Remove / Strip Ad Outro (Restore clean video)
    if remove_ad_only:
        print(f"\n[Quick Mode] Removing ad outro for {target_dir.name}...", flush=True)
        clean_vid = target_dir / f"{target_dir.name}_clean.mp4"
        if clean_vid.exists():
            shutil.copy2(clean_vid, final_output)
            print(f"[SUCCESS] Restored clean reel video: {final_output.name}", flush=True)
            with_ads = target_dir / f"{target_dir.name}_with_ads_final_reel.mp4"
            if with_ads.exists():
                try: with_ads.unlink()
                except Exception: pass
            meta_p = target_dir / "metadata.json"
            if meta_p.exists():
                try:
                    m_data = json.loads(meta_p.read_text(encoding="utf-8"))
                    m_data["ad_outro"] = {
                        "attached": False,
                        "filename": None,
                        "attached_at": None
                    }
                    m_data["pinned_comment"] = generate_pinned_comment_for_ad(None)
                    meta_p.write_text(json.dumps(m_data, indent=2, ensure_ascii=False), encoding="utf-8")
                    print(f"[Metadata] Reset pinned comment to clean video discussion.", flush=True)
                except Exception:
                    pass
        else:
            print(f"[INFO] Clean reel video not found; keeping current {final_output.name}.", flush=True)
        if thumbnail_only:
            regenerate_thumbnail_only(target_dir, week_num, reel_num)
        return final_output

    # Quick Mode 2b: Fast Ad Combine & Update (Instant concat demux)
    if combine_ad_only:
        print(f"\n[Quick Mode] Fast combining ad '{ad_num or 1}' for {target_dir.name}...", flush=True)
        clean_vid = target_dir / f"{target_dir.name}_clean.mp4"
        base_vid = clean_vid if clean_vid.exists() else final_output
        if not base_vid.exists():
            cands = [p for p in target_dir.glob("*_final_reel.mp4") if "_with_ads_" not in p.name]
            if cands:
                base_vid = cands[0]
        if not base_vid.exists():
            print(f"[ERROR] Cannot combine ad: Base reel video not found in {target_dir.name}!", flush=True)
            return None
        if not clean_vid.exists():
            shutil.copy2(base_vid, clean_vid)

        combined_p = combine_reel_with_ad(clean_vid, ad_num or 1, final_output)
        if thumbnail_only:
            regenerate_thumbnail_only(target_dir, week_num, reel_num)
        return combined_p


    if final_output.exists() and not force_rebuild and not images_only and not plan_only and final_output.stat().st_size > 100000:
        print(f"[Ready] Reel already rendered: {final_vid_name}", flush=True)
        return final_output

    temp_dir = target_dir / "temp"
    use_legacy = reel_uses_legacy_scenes(target_dir, replan)
    if force_rebuild and temp_dir.exists():
        if use_legacy:
            shutil.rmtree(temp_dir, ignore_errors=True)
        else:
            # Narration-timed reels keep their recording (it is re-recorded by itself when the script changes):
            # the scenes, prompts and pictures are timed to it
            stale_frames = temp_dir / "rendered_frames.mp4"
            if stale_frames.exists():
                stale_frames.unlink()
    temp_dir.mkdir(parents=True, exist_ok=True)
    images_dir = target_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    # 1. Ingest metadata.json
    meta_p = target_dir / "metadata.json"
    meta = {}
    if meta_p.exists():
        try:
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
        except Exception:
            pass

    ep_num = f"{reel_global_number(target_dir):02d}"
    title = meta.get("title") or target_dir.name.replace("_", " ").title()
    hook_text = meta.get("hook_text") or meta.get("hook") or title.upper()
    thumb_text = meta.get("thumbnail_text") or meta.get("hook") or title.upper()
    scripture_ref = meta.get("scripture") or meta.get("scriptures") or ""

    # 2. Ingest script.txt & Verify 1.75 - 2.00 Minute Standard
    script_p = target_dir / "script.txt"
    raw_script = script_p.read_text(encoding="utf-8", errors="replace") if script_p.exists() else ""
    clean_narr = clean_script_for_tts(raw_script)
    if not clean_narr:
        clean_narr = f"{title}. {hook_text}. In the scriptures, {scripture_ref}. Follow for more biblical secrets."
    # Captions show the script's real words, not the voice's pronunciation spellings
    caption_narr = clean_script_for_tts(raw_script, phonetic=False) or clean_narr
    clean_narr, caption_narr = strip_books_cta(clean_narr), strip_books_cta(caption_narr)

    word_count = len(clean_narr.split())
    # Measured narration pace on rendered reels is ~130 words/min (~2.17 words/sec); reels must stay under 2:00
    est_dur_sec = word_count / 2.17
    est_dur_min = est_dur_sec / 60.0

    print("=" * 74, flush=True)
    print(f"  [SCRIPT CHECK] Episode: {ep_num} | Title: {title}", flush=True)
    print(f"  • Script File: {script_p.name} ({'Found' if script_p.exists() else 'MISSING'})", flush=True)
    print(f"  • Word Count: {word_count} words", flush=True)
    print(f"  • Estimated Duration: {est_dur_min:.2f} min ({est_dur_sec:.1f}s)", flush=True)
    if not script_p.exists():
        print(f"  • Status: [FAILED] No script.txt found in {target_dir.name}!", flush=True)
    elif 1.50 <= est_dur_min <= 2.00:
        print(f"  • Status: [PASSED] Script fits the 1:30 - 2:00 reel length.", flush=True)
    else:
        print(f"  • Status: [NOTICE] Script runs ~{est_dur_min:.2f} min; reels should be 1:30 - 2:00 (~200-260 words).", flush=True)
    print("=" * 74, flush=True)

    timed_plan = None
    audio = None
    if use_legacy and plan_only:
        # Planning never records or draws: a reel rendered earlier keeps its pictures unless --replan
        print(f"[Scenes] {target_dir.name} keeps its earlier pictures; nothing to plan (use --replan to re-time it).", flush=True)
        return "KEPT"
    if use_legacy:
        # A reel rendered before narration-timed scenes: keep its pictures and their proportional timing
        sentences = split_into_sentences(clean_narr)

        # 3. Resolve Scenes Configuration (Strictly 18-20 Scenes)
        scenes = load_or_build_scenes(target_dir, sentences, ep_num, title=title)

        print(f"\n[Scenes] Resolved {len(scenes)} visual scenes (Standard: 18-20 scenes):", flush=True)
        for s_idx, sc in enumerate(scenes):
            print(f"   Scene {s_idx+1:02d}: [{sc['id']}] {sc['prompt'][:72]}...", flush=True)

        # 4. Generate / Resolve Scene Images (FLUX or Fallback)
        scene_image_paths = {}
        missing_count = 0
        for sc in scenes:
            sc_id = sc["id"]
            t_img = images_dir / f"{sc_id}.png"
            a_name = re.sub(r'reel0+(\d+)', r'reel\1', sc_id)
            a_img = images_dir / f"{a_name}.png"
            exists = (t_img.exists() and t_img.stat().st_size > 50000) or (a_img.exists() and a_img.stat().st_size > 50000)
            if not exists or force_images:
                missing_count += 1

        if missing_count > 0:
            print(f"\n[Images Check] {missing_count} / {len(scenes)} images missing or force-requested. Generating via ComfyUI...", flush=True)
        else:
            print(f"\n[Images Check] All {len(scenes)} scene images verified on disk.", flush=True)

        for sc in scenes:
            sc_id = sc["id"]
            img_p = generate_scene_image(sc["prompt"], sc_id, images_dir, custom_image=sc.get("custom_image"), force=force_images)
            scene_image_paths[sc_id] = img_p
    else:
        result = narration_timed_reel_scenes(target_dir, caption_narr, clean_narr, temp_dir, plan_only=plan_only,
                                             images_only=images_only, prompt_writer=prompt_writer,
                                             auto_prompts=auto_prompts, force_images=force_images)
        if isinstance(result, str):
            return result
        scenes, scene_image_paths, timed_plan, audio = result
        print(f"\n[Scenes] {len(scenes)} narration-timed scenes (at most {REEL_MAX_SCENES}):", flush=True)
        for sc in timed_plan["scenes"]:
            print(f"   {sc['id']} {sc['start']:6.1f}s-{sc['end']:6.1f}s: {sc['prompt'][:64]}...", flush=True)


    # 5. Generate Text Cards & Composite Thumbnail (Image + Caption)
    first_scene_img = scene_image_paths.get(scenes[0]["id"])
    target_thumb = target_dir / "thumbnail.jpg"
    try:
        sys.path.insert(0, str(PROJECT_DIR / "scripts"))
        from reel_thumbnail_builder import generate_composite_reel_thumbnail
        badge_text = meta.get("thumbnail_badge") or meta.get("category") or "THE SECRET BIBLE CODE"
        generate_composite_reel_thumbnail(
            base_img_path=str(first_scene_img),
            title=title,
            week_tag=badge_text,
            scripture=meta.get("thumbnail_scripture") or scripture_ref,
            subtitle=meta.get("thumbnail_kicker") or meta.get("subtitle") or meta.get("hook_text", ""),
            out_path=str(target_thumb),
            out_size=(1080, 1920),
            badge_text=badge_text,
            line1=meta.get("thumbnail_line1"),
            line2=meta.get("thumbnail_line2"),
            kicker=meta.get("thumbnail_kicker")
        )
        # Also sync to images/ folder
        shutil.copy2(target_thumb, images_dir / f"reel{ep_num}_card_thumbnail.png")
        print(f"[Thumbnail] Generated Modern Reel Thumbnail (image + viral typography) -> {target_thumb.name}", flush=True)
    except Exception as e:
        print(f"[Thumbnail Notice] Builder fallback: {e}", flush=True)
        thumb_card_p = generate_text_card("thumbnail", ep_num, hook_text, thumb_text, scripture_ref, images_dir, bg_image_path=first_scene_img)
        shutil.copy2(thumb_card_p, target_thumb)

    generate_text_card("hook", ep_num, hook_text, thumb_text, scripture_ref, images_dir, bg_image_path=first_scene_img)

    if images_only:
        print("[SUCCESS] Images-only mode complete.", flush=True)
        return target_thumb

    # 6. Audio Synthesis & Alignment (narration-timed reels recorded it before planning their scenes)
    master_audio, transcript_res, total_duration = audio or synthesize_and_align_audio(clean_narr, temp_dir, target_dir.name)

    # 7. Scene timeline: each picture from its first spoken word (narration-timed), or by word share (earlier reels)
    timeline = reel_timeline(scenes, timed_plan, total_duration)

    # 8. Load Pre-loaded Images & Logo
    loaded_imgs = {}
    for sc in scenes:
        loaded_imgs[sc["id"]] = Image.open(scene_image_paths[sc["id"]]).convert("RGB")

    logo_img = None
    if os.path.exists(LOCAL_LOGO):
        try:
            l_raw = Image.open(LOCAL_LOGO).convert("RGBA").resize((75, 75), Image.Resampling.LANCZOS)
            r, g, b, a = l_raw.split()
            a = a.point(lambda p: int(p * 0.58))
            l_raw.putalpha(a)
            logo_img = l_raw
        except Exception:
            pass

    # 9. Chunk Captions for Safe-Zone Rendering
    chunks = load_chunked_captions(caption_narr, transcript_res, max_words=4)
    try: font_word = ImageFont.truetype("arialbd.ttf", 56)
    except Exception: font_word = ImageFont.load_default()

    # 10. Frame-by-Frame Video Rendering (Ken Burns + Captions)
    total_frames = int(total_duration * FPS)
    temp_rendered = temp_dir / "rendered_frames.mp4"

    print(f"[Video] Rendering {total_frames} frames (768x1344 @ {FPS}fps)...", flush=True)
    writer = imageio.get_writer(
        str(temp_rendered), fps=FPS, codec="libx264",
        ffmpeg_params=["-pix_fmt", "yuv420p", "-crf", "18", "-preset", "veryfast"]
    )

    t_start = time.time()
    for f in range(total_frames):
        t = f / FPS
        active_sc = timeline[-1]
        for sc in timeline:
            if sc["start"] <= t <= sc["end"]:
                active_sc = sc
                break

        dur = max(0.01, active_sc["end"] - active_sc["start"])
        t_frac = min(1.0, max(0.0, (t - active_sc["start"]) / dur))
        frame_img = apply_motion(loaded_imgs[active_sc["id"]], active_sc["motion"], t_frac, out_size=(768, 1344))

        # Safe-zone captions at Y=74%
        active_chunk = None
        for c in chunks:
            if c["start"] <= t <= c["end"] + 0.15:
                active_chunk = c
                break

        if active_chunk:
            overlay = Image.new("RGBA", (768, 1344), (0, 0, 0, 0))
            draw_ov = ImageDraw.Draw(overlay)
            pad_x, pad_y, word_sp = 24, 12, 14
            total_w = sum(draw_ov.textlength(w["word"], font=font_word) for w in active_chunk["words"]) + word_sp * (len(active_chunk["words"]) - 1)
            card_w = int(total_w + pad_x * 2)
            card_h = font_word.size + 28
            card_x = (768 - card_w) // 2
            card_y = int(1344 * 0.74)
            draw_ov.rounded_rectangle([card_x, card_y, card_x + card_w, card_y + card_h], radius=18, fill=(0, 0, 0, 160))

            cur_x = card_x + pad_x
            text_y = card_y + 12
            for w in active_chunk["words"]:
                wl = draw_ov.textlength(w["word"], font=font_word)
                is_active = (w["start"] <= t <= w["end"] + 0.05)
                color = (255, 230, 0, 255) if is_active else (255, 255, 255, 245)
                draw_ov.text((cur_x, text_y), w["word"], font=font_word, fill=color)
                cur_x += wl + word_sp
            frame_img = Image.alpha_composite(frame_img, overlay)

        if logo_img:
            frame_img.paste(logo_img, (36, 36), logo_img)

        writer.append_data(np.array(frame_img.convert("RGB")))

        if f % 180 == 0 or f == total_frames - 1:
            pct = ((f + 1) / total_frames) * 100
            print(f"  [Render] Frame {f+1}/{total_frames} ({pct:.1f}%) in {time.time()-t_start:.1f}s", flush=True)

    writer.close()

    # 11. Final Mux with Master Audio into Clean Video
    print("[Mux] Assembling broadcast video...", flush=True)
    clean_output = target_dir / f"{target_dir.name}_clean.mp4"
    mux_cmd = [
        FFMPEG_EXE, "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(temp_rendered),
        "-i", str(master_audio),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "320k",
        "-movflags", "+faststart",
        "-shortest", str(clean_output)
    ]
    cf = SUBPROCESS_CREATIONFLAGS
    subprocess.run(mux_cmd, check=True, creationflags=cf)

    if temp_rendered.exists():
        try: os.remove(str(temp_rendered))
        except Exception: pass

    # If ad requested, combine with ad outro; otherwise copy clean to final
    if ad_num:
        try:
            combine_reel_with_ad(clean_output, ad_num, final_output)
        except Exception as e:
            print(f"[Ad Warning] Combining ad '{ad_num}' failed: {e}. Falling back to clean reel.", flush=True)
            shutil.copy2(clean_output, final_output)
    else:
        shutil.copy2(clean_output, final_output)
        meta_p = target_dir / "metadata.json"
        if meta_p.exists():
            try:
                m_data = json.loads(meta_p.read_text(encoding="utf-8"))
                m_data["ad_outro"] = {
                    "attached": False,
                    "filename": None,
                    "attached_at": None
                }
                m_data["pinned_comment"] = generate_pinned_comment_for_ad(None)
                meta_p.write_text(json.dumps(m_data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass

    size_mb = final_output.stat().st_size / (1024 * 1024)
    print(f"\n[SUCCESS] Reel Render Completed: {final_output.name} ({size_mb:.1f} MB, {total_duration:.1f}s)\n", flush=True)
    return final_output

# =============================================================================
# CLI ENTRY POINT
# =============================================================================
def main():
    parser = argparse.ArgumentParser(description="Master Reel Video Generator (Episode 57 Benchmark Standard)")
    parser.add_argument("--week", "-w", type=str, default=None, help="Target week (e.g. 1 or W01)")
    parser.add_argument("--reel", "-r", type=str, default=None,
                        help="Reel to render: its day key (mon_2), folder name, or place in the week's posting order (1 = first)")
    parser.add_argument("--episode", "-e", type=int, default=None, help="Global reel number (the 'Bible Secrets #NNN')")
    parser.add_argument("--all", "-a", action="store_true", help="Generate every reel of the specified week")
    parser.add_argument("--force-rebuild", action="store_true", help="Force rebuild even if video exists")
    parser.add_argument("--force-images", action="store_true", help="Force ComfyUI FLUX re-generation of all scene images")
    parser.add_argument("--images-only", action="store_true", help="Generate scene images & text cards only")
    parser.add_argument("--thumbnail-only", "--thumb-only", action="store_true", help="Regenerate Option-C composite thumbnail without re-rendering video")
    parser.add_argument("--combine-ad", "--ad-only", "--regen-ad", action="store_true", help="Fast combine existing video with ad outro without re-rendering scenes")
    parser.add_argument("--remove-ad", "--strip-ad", action="store_true", help="Remove ad outro and restore clean reel video")
    parser.add_argument("--quick-combine", action="store_true", help="Regenerate thumbnail and combine ad outro without full video re-render")
    parser.add_argument("--comment-only", "--trigger-comment", action="store_true",
                        help="Trigger and sync pinned comment in metadata.json based on attached ad without altering video")
    parser.add_argument("--ads", nargs="?", const="1", type=str, default=None, help="Include ad outro (variant 1, 2, 3 or filename in C:\\Projects\\Adz-Video)")
    parser.add_argument("--speed", type=float, default=None, help="Optional vocal speed multiplier")
    parser.add_argument("--plan-only", action="store_true",
                        help="Plan the scenes from the script and write their prompts, before any voice is recorded")
    parser.add_argument("--replan", action="store_true",
                        help="Time new pictures to the narration even if the reel already has its earlier pictures")
    parser.add_argument("--auto-prompts", action="store_true",
                        help="Fill missing scene prompts with the built-in rules instead of pausing")
    parser.add_argument("--prompt-writer", default=None,
                        help="Who writes the scene prompts: e.g. claude,gemini (default from generator_settings.json), or manual")
    args = parser.parse_args()

    week_num = None
    targets = []

    if args.episode is not None:
        found = find_reel_by_number(args.episode)
        if not found:
            print(f"[ERROR] No reel has the number {args.episode}")
            sys.exit(1)
        week_num, folder = found
        targets = [folder]
    elif args.week is not None:
        w_str = str(args.week).upper().replace("W", "")
        week_num = int(w_str)
    else:
        parser.print_help()
        sys.exit(1)

    week_tag = f"W{week_num:02d}"
    week_dir = PROJECT_DIR / week_tag
    if not week_dir.exists():
        print(f"[ERROR] Week directory not found: {week_dir}")
        sys.exit(1)

    if args.episode is None:
        if args.all or args.reel is None:
            targets = ordered_reels(week_dir / "reels")
        else:
            folder = find_reel_folder(week_dir, args.reel)
            if folder:
                targets = [folder]
            else:
                print(f"[SKIP] Reel {args.reel} folder not found in {week_dir / 'reels'}")
    reel_indices = [reel_key(f) or f.name for f in targets]
    all_reels = ordered_reels(week_dir / "reels")

    print(f"\n===========================================================================")
    print(f"MASTER REEL GENERATOR: Week {week_tag}, Reels {reel_indices}")
    print(f"===========================================================================")

    completed = []
    for target_sub in targets:
        r_idx = all_reels.index(target_sub) + 1 if target_sub in all_reels else 1
        try:
            out_p = render_reel(
                week_num=week_num,
                reel_num=r_idx,
                target_dir=target_sub,
                force_rebuild=args.force_rebuild,
                images_only=args.images_only,
                force_images=args.force_images,
                ad_num=args.ads,
                speed=args.speed,
                thumbnail_only=args.thumbnail_only or args.quick_combine,
                combine_ad_only=args.combine_ad or args.quick_combine,
                remove_ad_only=args.remove_ad,
                comment_only=args.comment_only,
                plan_only=args.plan_only,
                replan=args.replan,
                auto_prompts=args.auto_prompts,
                prompt_writer=args.prompt_writer
            )
            completed.append(out_p)
        except Exception as e:
            print(f"[ERROR] Failed to render Reel {r_idx}: {e}", flush=True)
            import traceback
            traceback.print_exc()

    print(f"\n===========================================================================")
    print(f"SUMMARY: Successfully processed {len(completed)} / {len(reel_indices)} reels for {week_tag}")
    print(f"===========================================================================\n")
    if len([p for p in completed if p]) < len(targets):
        sys.exit(1)
    paused = [p for p in completed if p == "NEEDS_PROMPTS"]
    if paused:
        print(f"⏸  {len(paused)} reel(s) wait for scene prompts.", flush=True)
        sys.exit(3)  # KCT Studio shows this as paused, not failed

if __name__ == "__main__":
    main()
