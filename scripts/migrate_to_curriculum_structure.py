r"""
=============================================================================
BHSR Curriculum-Aligned Episodic Structure Migration Script
=============================================================================
Migrates C:\Projects\BHSR from format-siloed folders to 156-Week Episodic Bundles:
C:\Projects\BHSR\
  ├── W01\
  │   ├── long_form\     # 16:9 Master Documentary + assets
  │   ├── reels\         # 5 Vertical Reels
  │   ├── stories\       # 5 Daily Stories
  │   ├── substack\      # Substack issues & graphics
  │   └── metadata.json  # Full week curriculum manifest
  ├── W02\ ... W156\
  ├── shared_assets\
  ├── config\
  └── scripts\
=============================================================================
"""

import os
import sys
import re
import json
import shutil
from pathlib import Path

# Paths
BHSR_ROOT = Path("C:/Projects/BHSR")
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CORE_DIR = Path(__file__).resolve().parent.parent / "core"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.story_map_definitions import MASTER_WEEK_DEFINITIONS

# Mapping of existing 28 long-form folders to canonical week numbers
LONG_FORM_TO_WEEK = {
    "3-What_Happened_Before_Genesis": 1,
    "10-The_Seraph_and_the_Garden": 3,
    "4-The_Watchers_and_Nephilim": 6,
    "15-The_Azazel_Scapegoat_Ritual": 8,
    "2-Noahs_Ark": 9,
    "7-The_Curse_of_Ham_and_Canaan": 11,
    "6-The_Stargate_of_Babel_Nimrod": 12,
    "5-The_Enigma_of_Melchizedek": 15,
    "9-The_Covenant_of_Pieces": 16,
    "8-Jacobs_Midnight_Duel_Peniel": 18,
    "12-The_Giants_of_Bashan_Og": 25,
    "1-David_and_Goliath": 27,
    "14-The_Witch_of_Endor_Sheol": 29,
    "21-The_Lost_Ark_Jeremiahs_Vault": 32,
    "13-Ezekiels_Merkabah_Ophanim": 35,
    "17-The_Valley_of_Dry_Bones": 36,
    "18-Michael_vs_Prince_of_Persia": 38,
    "19-The_Transfiguration_Mount_Hermon": 41,
    "11-The_Red_Heifer_Third_Temple": 43,
    "24-The_War_in_Heaven_Dragon": 50,
    "23-The_Two_Witnesses_Enoch_Elijah": 51,
    "25-The_New_Jerusalem_Hypercube": 52,
    "16-The_Prince_of_Tyre_Anointed_Cherub": 73,
    "20-The_Four_Horsemen_Apocalypse": 112,
    "22-The_Sea_of_Glass_24_Elders": 111,
    "sample_2min_before_genesis": 1,
    "1-David_Goliath_1Hour": 27,
    "2-Noah_Ark_1Hour": 9
}

def create_week_scaffolds():
    """Generates W01 through W156 folders with metadata.json manifests."""
    print("[1/5] Scaffolding 156 weekly release directories...")
    
    # Pre-index definitions by week
    defn_by_week = {d["week"]: d for d in MASTER_WEEK_DEFINITIONS}
    
    reel_days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
    hook_types = ["Mystery Hook", "Ancient Hebrew / Text", "Prophecy / Scroll", "Christological Typology", "Bestselling Book CTA"]
    story_stickers = [
        ("link_youtube", "New Documentary Streaming! Tap to watch full episode."),
        ("poll", "Did you know this biblical revelation? [Yes] / [Mind Blown]"),
        ("link_substack", "Free Companion Study Guide & Scripture Chart Live on Substack!"),
        ("quiz", "Bible Quiz of the Week"),
        ("countdown", "Next Episode Drops Sunday 10 AM!")
    ]
    comm_types = [
        ("image_quote", "Scripture Quote & Visual Archetype"),
        ("4_choice_poll", "Interactive Theological Community Poll"),
        ("scroll_breakdown", "Ancient Scroll & Archaeological Discovery"),
        ("substack_link", "Mid-Week Deep Dive & Discussion Link"),
        ("discussion_prompt", "Weekend Reflection & Viewer Q&A Spotlight")
    ]
    
    for w in range(1, 157):
        w_folder = BHSR_ROOT / f"W{w:02d}"
        (w_folder / "long_form").mkdir(parents=True, exist_ok=True)
        (w_folder / "reels").mkdir(parents=True, exist_ok=True)
        (w_folder / "stories").mkdir(parents=True, exist_ok=True)
        (w_folder / "substack").mkdir(parents=True, exist_ok=True)
        
        defn = defn_by_week.get(w, {
            "week": w,
            "title": f"Week {w} Revelation",
            "theme": "Biblical Mysteries Decoded",
            "testament": "Old Testament" if w <= 78 else "New Testament",
            "duration": "30 min",
            "scriptures": [],
            "christological_key": "Points to Christ as the fulfillment.",
            "status": "planned"
        })
        
        # 5 Numbered Reels
        reels = []
        for i in range(5):
            global_r = (w - 1) * 5 + (i + 1)
            reels.append({
                "id": f"R-W{w:02d}.{i+1}",
                "num": i + 1,
                "global_num": global_r,
                "day": reel_days[i],
                "badge": f"Bible Secrets #{global_r:03d} [W{w:02d}.{i+1}]",
                "title": defn.get("reel_titles", [f"Reel {i+1}"])[i] if i < len(defn.get("reel_titles", [])) else f"{defn['title']} (Part {i+1})",
                "hook_type": hook_types[i],
                "hook": defn.get("reel_hooks", ["Watch to discover the decoded mystery."])[i] if i < len(defn.get("reel_hooks", [])) else "Watch to discover the decoded mystery."
            })
            
        # 5 Stories
        stories = []
        for i in range(5):
            global_s = (w - 1) * 5 + (i + 1)
            stories.append({
                "id": f"S-W{w:02d}.{i+1}",
                "num": i + 1,
                "global_num": global_s,
                "day": reel_days[i],
                "badge": f"Story #{global_s:03d} [W{w:02d}.{i+1}]",
                "sticker_type": story_stickers[i][0],
                "caption": story_stickers[i][1] if i != 3 else f"Bible Quiz of the Week on {defn['title']}"
            })
            
        # 5 Community Posts
        comm_posts = []
        for i in range(5):
            global_c = (w - 1) * 5 + (i + 1)
            comm_posts.append({
                "id": f"CT-W{w:02d}.{i+1}",
                "num": i + 1,
                "global_num": global_c,
                "day": reel_days[i],
                "badge": f"Community Post #{global_c:03d}",
                "post_type": comm_types[i][0],
                "type_label": comm_types[i][1],
                "prompt": defn.get("community_prompts", ["What was your favorite revelation?"])[i] if i < len(defn.get("community_prompts", [])) else f"Discuss {defn['title']}",
                "options": ["Prophecy Fulfilled", "Christological Type", "Ancient Scroll Context", "Never Taught in Church"] if i == 1 else []
            })
            
        metadata = {
            "week": w,
            "year": 1 if w <= 52 else (2 if w <= 104 else 3),
            "quarter": f"Q{((w - 1) // 13) + 1}",
            "theme": defn.get("theme", "Biblical Mysteries Decoded"),
            "testament": defn.get("testament", "Old Testament"),
            "documentary": {
                "id": f"DOC-W{w:02d}",
                "title": defn["title"],
                "duration": defn.get("duration", "30 min"),
                "scriptures": defn.get("scriptures", []),
                "christological_key": defn.get("christological_key", "Points to Christ as the fulfillment."),
                "status": defn.get("status", "planned")
            },
            "substack": {
                "pillar_id": f"SUB-W{w:02d}.A",
                "pillar_title": defn.get("substack_title", f"{defn['title']}: Full Study Guide"),
                "digest_id": f"SUB-W{w:02d}.B",
                "digest_title": f"Mid-Week Q&A & Sacred Art: {defn['title']}",
                "lead_magnet": "Free Printable Study Guide & Scripture Concordance Chart"
            },
            "reels": reels,
            "stories": stories,
            "community_posts": comm_posts
        }
        
        meta_file = w_folder / "metadata.json"
        meta_file.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    print("   [+] All 156 week folders and manifests created.")

def migrate_long_form():
    """Migrates existing 28 long-form folders into their corresponding Wxx/long_form directories."""
    print("[2/5] Migrating long-form documentary episodes...")
    src_long = BHSR_ROOT / "long_form"
    if not src_long.exists():
        print("   [*] No legacy long_form folder found, skipping.")
        return

    for item in list(src_long.iterdir()):
        if not item.is_dir() or item.name == "__pycache__":
            continue
            
        name = item.name
        w_num = LONG_FORM_TO_WEEK.get(name)
        if not w_num:
            # Check prefix number
            m = re.match(r"^(\d+)", name)
            if m:
                w_num = int(m.group(1))
            else:
                print(f"   [!] Could not map long-form folder: {name}")
                continue
                
        target_dir = BHSR_ROOT / f"W{w_num:02d}" / "long_form"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # If special sub-flavor (1Hour or sample), move as subfolder inside Wxx/long_form
        if "1Hour" in name or "sample" in name:
            sub_target = target_dir / name
            if not sub_target.exists():
                shutil.move(str(item), str(sub_target))
                print(f"   [+] Moved special {name} -> W{w_num:02d}/long_form/{name}")
        else:
            # Move all contents directly into Wxx/long_form
            for child in list(item.iterdir()):
                dest_child = target_dir / child.name
                if dest_child.exists():
                    if dest_child.is_dir():
                        shutil.rmtree(dest_child)
                    else:
                        dest_child.unlink()
                shutil.move(str(child), str(dest_child))
            # Remove empty source folder
            try:
                item.rmdir()
            except Exception:
                pass
            print(f"   [+] Migrated {name} contents -> W{w_num:02d}/long_form")

def migrate_reels():
    """Migrates existing 285 reel folders into their corresponding Wxx/reels bundles."""
    print("[3/5] Migrating 285 numbered reels into weekly bundles...")
    src_reels = BHSR_ROOT / "reels"
    if not src_reels.exists():
        print("   [*] No legacy reels folder found, skipping.")
        return

    migrated = 0
    for item in list(src_reels.iterdir()):
        if not item.is_dir():
            continue
            
        name = item.name
        # Match leading number (e.g. 01_..., 48_..., 014, etc.)
        m = re.match(r"^0*(\d+)", name)
        if m:
            reel_num = int(m.group(1))
            if reel_num > 0:
                w_num = ((reel_num - 1) // 5) + 1
                target_reels_dir = BHSR_ROOT / f"W{w_num:02d}" / "reels" / name
                if not target_reels_dir.exists():
                    shutil.move(str(item), str(target_reels_dir))
                    migrated += 1

    print(f"   [+] Migrated {migrated} reels across W01..W60.")

def migrate_stories():
    """Migrates existing 360 story folders into their corresponding Wxx/stories bundles."""
    print("[4/5] Migrating 360 daily stories into weekly bundles...")
    src_stories = BHSR_ROOT / "stories"
    if not src_stories.exists():
        print("   [*] No legacy stories folder found, skipping.")
        return

    migrated = 0
    for item in list(src_stories.iterdir()):
        if not item.is_dir():
            continue
            
        name = item.name
        m = re.match(r"^0*(\d+)", name)
        if m:
            story_num = int(m.group(1))
            if story_num > 0:
                w_num = ((story_num - 1) // 5) + 1
                target_stories_dir = BHSR_ROOT / f"W{w_num:02d}" / "stories" / name
                if not target_stories_dir.exists():
                    shutil.move(str(item), str(target_stories_dir))
                    migrated += 1

    print(f"   [+] Migrated {migrated} daily stories across W01..W72.")

def setup_directory_junctions():
    """Configures NTFS Directory Junctions for 100% backward compatibility."""
    print("[5/5] Configuring NTFS Directory Junctions...")
    import subprocess
    
    # 1. C:\Projects\BHRS -> C:\Projects\BHSR (ensures BHRS spelling works)
    bhrs_junction = Path("C:/Projects/BHRS")
    if not bhrs_junction.exists():
        try:
            subprocess.run(f'cmd /c mklink /J "{bhrs_junction}" "{BHSR_ROOT}"', shell=True, check=True)
            print("   [+] Created Junction: C:\\Projects\\BHRS -> C:\\Projects\\BHSR")
        except Exception as e:
            print(f"   [!] Failed to create BHRS junction: {e}")

    # 2. Refresh C:\Projects\BHRS-Youtube junction -> C:\Projects\BHSR
    bhrs_yt = Path("C:/Projects/BHRS-Youtube")
    if bhrs_yt.exists():
        try:
            # Test if it's already a junction
            subprocess.run(f'cmd /c rmdir "{bhrs_yt}"', shell=True)
            subprocess.run(f'cmd /c mklink /J "{bhrs_yt}" "{BHSR_ROOT}"', shell=True, check=True)
            print("   [+] Updated Junction: C:\\Projects\\BHRS-Youtube -> C:\\Projects\\BHSR")
        except Exception as e:
            print(f"   [!] Note on BHRS-Youtube junction: {e}")

if __name__ == "__main__":
    print("=" * 70)
    print("  Starting BHSR Master Curriculum-Aligned Folder Restructuring")
    print("=" * 70)
    create_week_scaffolds()
    migrate_long_form()
    migrate_reels()
    migrate_stories()
    setup_directory_junctions()
    print("=" * 70)
    print("  Curriculum-Aligned Episodic Restructure Completed Successfully!")
    print("=" * 70)
