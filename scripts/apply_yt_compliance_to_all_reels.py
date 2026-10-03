"""
Batch migration script: Apply YouTube URL-Free Description & Pinned Comment to ALL Reels.
Ensures:
1. No raw URLs in youtube_description (replaced with Channel Bio & Pinned Comment callouts).
2. Pinned comment is populated with verified store & book links.
3. Both metadata.json and metadata.txt files across all reel folders are updated.
"""

import sys
import re
import json
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from core.social_dispatcher import (
    social_dispatcher,
    DEFAULT_BHRS_YT_MERCH_BLOCK,
    DEFAULT_BHRS_PINNED_COMMENT
)

BHSR_DIR = Path("C:/Projects/BHSR")

def process_metadata_json(file_path: Path) -> bool:
    try:
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception as e:
        print(f"  [ERROR] Reading {file_path.name}: {e}")
        return False

    changed = False

    # 1. Update youtube_description
    current_ytd = data.get("youtube_description", "")
    if current_ytd:
        cleaned_ytd = social_dispatcher.sanitize_urls_for_youtube(current_ytd)
        if cleaned_ytd != current_ytd:
            data["youtube_description"] = cleaned_ytd
            changed = True
    else:
        # Build new YouTube description from title/description/tags
        title = data.get("title", "")
        desc = data.get("description") or data.get("caption") or data.get("hook") or ""
        tags = data.get("tags") or data.get("hashtags") or []
        ht_str = " ".join([f"#{str(t).lstrip('#')}" for t in tags if str(t).strip()])
        new_ytd = social_dispatcher.build_youtube_description(
            hook=title,
            body=desc,
            hashtags=ht_str
        )
        data["youtube_description"] = new_ytd
        changed = True

    # 2. Update pinned_comment
    current_pin = data.get("pinned_comment", "")
    if not current_pin or "http" not in current_pin:
        data["pinned_comment"] = DEFAULT_BHRS_PINNED_COMMENT
        changed = True

    if changed:
        try:
            file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            return True
        except Exception as e:
            print(f"  [ERROR] Writing {file_path.name}: {e}")
            return False

    return False

def process_metadata_txt(file_path: Path) -> bool:
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        try:
            content = file_path.read_text(encoding="cp1252", errors="replace")
        except Exception as e:
            print(f"  [ERROR] Reading {file_path.name}: {e}")
            return False

    changed = False
    new_content = content

    # 1. If YOUTUBE DESCRIPTION: exists with old URLs, sanitize it
    if "YOUTUBE DESCRIPTION:" in new_content:
        parts = new_content.split("YOUTUBE DESCRIPTION:")
        prefix = parts[0]
        ytd_part = parts[1]
        
        # Clean up to the next section or end of file
        next_sec_match = re.search(r'\n([A-Z\s]{4,}):', ytd_part)
        if next_sec_match:
            yt_text = ytd_part[:next_sec_match.start()]
            suffix = ytd_part[next_sec_match.start():]
        else:
            yt_text = ytd_part
            suffix = ""
            
        cleaned_yt = social_dispatcher.sanitize_urls_for_youtube(yt_text)
        if cleaned_yt != yt_text:
            new_content = f"{prefix}YOUTUBE DESCRIPTION:{cleaned_yt}{suffix}"
            changed = True

    # 2. If PINNED COMMENT: missing, add it
    if "PINNED COMMENT:" not in new_content:
        pin_block = f"\n\nPINNED COMMENT:\n{DEFAULT_BHRS_PINNED_COMMENT}\n"
        new_content = new_content.strip() + pin_block
        changed = True

    if changed and new_content != content:
        try:
            file_path.write_text(new_content, encoding="utf-8")
            return True
        except Exception as e:
            print(f"  [ERROR] Writing {file_path.name}: {e}")
            return False

    return False

def main():
    print(f"=== Starting Batch Migration for Reels in {BHSR_DIR} ===")
    
    json_files = list(BHSR_DIR.glob("**/reels/**/metadata.json"))
    txt_files = list(BHSR_DIR.glob("**/reels/**/metadata.txt"))
    
    print(f"Found {len(json_files)} metadata.json files.")
    print(f"Found {len(txt_files)} metadata.txt files.")

    updated_json = 0
    for jf in json_files:
        if process_metadata_json(jf):
            updated_json += 1
            rel = jf.relative_to(BHSR_DIR)
            print(f"  [UPDATED JSON] {rel}")

    updated_txt = 0
    for tf in txt_files:
        if process_metadata_txt(tf):
            updated_txt += 1
            rel = tf.relative_to(BHSR_DIR)
            print(f"  [UPDATED TXT] {rel}")

    print("\n=== Migration Complete ===")
    print(f"Total metadata.json updated: {updated_json} / {len(json_files)}")
    print(f"Total metadata.txt updated:  {updated_txt} / {len(txt_files)}")

if __name__ == "__main__":
    main()
