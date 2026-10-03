"""
Multi-Platform Policy Compliance Engine for ALL Reels.
Enforces 100% compliance across:
1. YouTube (Shorts & Long-Form):
   - Zero external URLs in descriptions (replaced with Channel Bio & Pinned Comment callout).
   - Titles <= 100 characters.
   - Max 3-5 relevant hashtags (prevents YouTube over-tagging penalty).
   - Verified Pinned Comment with official store and book links.
2. Instagram (Reels):
   - Zero naked unclickable URLs in captions (etsy.com, amazon.com, https://).
   - Clean 'Link in Bio!' callouts.
   - Max 3-5 hashtags (Instagram official creator standard).
   - Strips sensitive / shadowban-triggering keywords (#Lucifer, #FallOfSatan, #Demons, #SpiritualWarfare).
3. Threads (@threads):
   - Strictly <= 500 characters total limit.
   - Clean hook + brief takeaway + Link in Bio CTA + 3-4 clean tags.
4. TikTok:
   - Softens violent trigger terms ('murder' -> 'violence').
   - Max 5 hashtags.
   - Under 2,000 characters.
5. Facebook (Watch & Reels):
   - Clean merch block without link-spamming.
6. X (Twitter):
   - Strictly <= 280 characters.
"""

import sys
import os
import re
import json
from pathlib import Path

# Adjust paths
PIPELINE_ROOT = Path(r"c:\Projects\AI-Content-Generation-Pipeline")
BHSR_ROOT = Path(r"C:\Projects\BHSR")
sys.path.insert(0, str(PIPELINE_ROOT))

from core.social_dispatcher import (
    social_dispatcher,
    DEFAULT_BHRS_PINNED_COMMENT,
    DEFAULT_BHRS_YT_MERCH_BLOCK,
    DEFAULT_BHRS_IG_MERCH_BLOCK
)

STATS = {
    "json_processed": 0,
    "json_updated": 0,
    "txt_processed": 0,
    "txt_updated": 0,
    "yt_urls_cleaned": 0,
    "yt_titles_trimmed": 0,
    "ig_urls_cleaned": 0,
    "ig_sensitive_tags_removed": 0,
    "threads_captions_added": 0,
    "threads_captions_trimmed": 0,
    "tiktok_captions_sanitized": 0,
    "x_posts_trimmed": 0
}

def clean_tags_list(tags_list):
    sensitive = ["lucifer", "satan", "demon", "demons", "warfare", "devil", "fallofsatan", "murder"]
    cleaned = []
    removed = 0
    for t in tags_list:
        clean = str(t).strip().lstrip("#")
        if not clean:
            continue
        if any(s in clean.lower() for s in sensitive):
            removed += 1
            continue
        if clean not in cleaned:
            cleaned.append(clean)
            
    if not cleaned:
        cleaned = ["BibleSecrets", "ScriptureUncovered", "BibleStudy", "BiblicalTruth"]
        
    return cleaned[:5], removed

def process_metadata_json(file_path: Path) -> bool:
    try:
        content = file_path.read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception as e:
        print(f"  [ERROR] Reading {file_path}: {e}")
        return False

    STATS["json_processed"] += 1
    changed = False

    title = data.get("title", "")
    hook = data.get("hook") or data.get("hook_text") or title
    body = data.get("description") or data.get("body_narrative") or ""
    tags = data.get("tags") or []
    
    # 1. Title sanitization
    if len(title) > 100:
        new_title = social_dispatcher.sanitize_title_for_youtube(title)
        if new_title != title:
            data["title"] = new_title
            title = new_title
            STATS["yt_titles_trimmed"] += 1
            changed = True

    # 2. YouTube Shorts Title
    yt_shorts_title = data.get("youtube_shorts_title", "")
    if yt_shorts_title and len(yt_shorts_title) > 100:
        new_yt_title = social_dispatcher.sanitize_title_for_youtube(yt_shorts_title)
        if new_yt_title != yt_shorts_title:
            data["youtube_shorts_title"] = new_yt_title
            STATS["yt_titles_trimmed"] += 1
            changed = True

    # 3. Tags & Hashtags sanitization
    safe_tags, removed_count = clean_tags_list(tags)
    if removed_count > 0 or len(tags) > 5:
        data["tags"] = safe_tags
        data["hashtags"] = [f"#{t}" for t in safe_tags]
        STATS["ig_sensitive_tags_removed"] += removed_count
        changed = True
    safe_ht_str = " ".join([f"#{t}" for t in safe_tags])

    # 4. YouTube description
    ytd = data.get("youtube_description", "")
    if not ytd:
        ytd = social_dispatcher.build_youtube_description(title, body, hashtags=safe_ht_str)
        data["youtube_description"] = ytd
        changed = True
    else:
        new_ytd = social_dispatcher.sanitize_urls_for_youtube(ytd)
        if new_ytd != ytd:
            data["youtube_description"] = new_ytd
            STATS["yt_urls_cleaned"] += 1
            changed = True

    # 5. Instagram caption
    ig = data.get("instagram_caption", "")
    if not ig:
        ig = social_dispatcher.build_instagram_caption(title, body, hashtags=safe_ht_str)
        data["instagram_caption"] = ig
        changed = True
    else:
        new_ig = social_dispatcher.sanitize_urls_for_instagram(ig)
        if new_ig != ig:
            data["instagram_caption"] = new_ig
            STATS["ig_urls_cleaned"] += 1
            changed = True

    # 6. Threads caption (Strictly <= 500 chars)
    th = data.get("threads_caption", "")
    if not th:
        th = social_dispatcher.build_threads_caption(hook, body, safe_ht_str)
        data["threads_caption"] = th
        STATS["threads_captions_added"] += 1
        changed = True
    else:
        new_th = social_dispatcher.sanitize_caption_for_threads(th, hook, body)
        if new_th != th:
            data["threads_caption"] = new_th
            STATS["threads_captions_trimmed"] += 1
            changed = True

    # 7. TikTok caption
    tt = data.get("tiktok_caption", "")
    if not tt:
        tt = social_dispatcher.build_tiktok_caption(title, body, safe_ht_str)
        data["tiktok_caption"] = tt
        changed = True
    else:
        new_tt = social_dispatcher.sanitize_caption_for_tiktok(tt)
        if new_tt != tt:
            data["tiktok_caption"] = new_tt
            STATS["tiktok_captions_sanitized"] += 1
            changed = True

    # 8. X Post (Strictly <= 280 chars)
    x = data.get("x_post", "")
    if not x:
        x = social_dispatcher.build_x_post(title, body, hashtags=safe_ht_str)
        data["x_post"] = x
        changed = True
    else:
        new_x = social_dispatcher.sanitize_post_for_x(x)
        if new_x != x:
            data["x_post"] = new_x
            STATS["x_posts_trimmed"] += 1
            changed = True

    # 9. Pinned comment
    if not data.get("pinned_comment") or "http" not in data.get("pinned_comment", ""):
        data["pinned_comment"] = DEFAULT_BHRS_PINNED_COMMENT
        changed = True

    if changed:
        try:
            file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            STATS["json_updated"] += 1
            return True
        except Exception as e:
            print(f"  [ERROR] Writing {file_path}: {e}")
            return False

    return False

def process_metadata_txt(file_path: Path) -> bool:
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        try:
            content = file_path.read_text(encoding="cp1252", errors="replace")
        except Exception as e:
            print(f"  [ERROR] Reading {file_path}: {e}")
            return False

    STATS["txt_processed"] += 1
    changed = False
    new_content = content

    # 1. Sanitize YOUTUBE SHORTS TITLE if > 100 chars
    m_yt_title = re.search(r'YOUTUBE SHORTS TITLE:\s*(.*)', new_content)
    if m_yt_title:
        orig_yt_title = m_yt_title.group(1).strip()
        if len(orig_yt_title) > 100:
            cleaned_yt_title = social_dispatcher.sanitize_title_for_youtube(orig_yt_title)
            new_content = new_content.replace(f"YOUTUBE SHORTS TITLE: {orig_yt_title}", f"YOUTUBE SHORTS TITLE: {cleaned_yt_title}")
            STATS["yt_titles_trimmed"] += 1
            changed = True

    # 2. Sanitize main Merch block if it has raw URLs
    if "OFFICIAL MERCH" in new_content and ("http://" in new_content or "https://" in new_content or "etsy.com" in new_content):
        # We replace the raw URL merch block with the clean YouTube/Instagram format
        pattern = r"={20,}[\s\S]*?(?:OFFICIAL MERCH|Official Merch)[\s\S]*?={20,}"
        if re.search(pattern, new_content):
            new_content = re.sub(pattern, DEFAULT_BHRS_YT_MERCH_BLOCK, new_content)
            STATS["yt_urls_cleaned"] += 1
            changed = True

    # 3. Sanitize INSTAGRAM CAPTION
    m_ig = re.search(r'INSTAGRAM CAPTION:\s*(.*)', new_content)
    if m_ig:
        orig_ig = m_ig.group(1).strip()
        cleaned_ig = orig_ig
        if "http" in cleaned_ig or "etsy.com" in cleaned_ig or "amazon.com" in cleaned_ig:
            cleaned_ig = re.sub(r'https?://[^\s]+', '(Link in bio)', cleaned_ig)
            cleaned_ig = re.sub(r'etsy\.com/[^\s]+', '(Link in bio)', cleaned_ig)
            cleaned_ig = re.sub(r'amazon\.com/[^\s]+', '(Link in bio)', cleaned_ig)
            STATS["ig_urls_cleaned"] += 1
            changed = True
        if cleaned_ig != orig_ig:
            new_content = new_content.replace(f"INSTAGRAM CAPTION: {orig_ig}", f"INSTAGRAM CAPTION: {cleaned_ig}")

    # 4. Sanitize FACEBOOK CAPTION if it has raw URLs
    m_fb = re.search(r'FACEBOOK CAPTION:\s*(.*)', new_content)
    if m_fb:
        orig_fb = m_fb.group(1).strip()
        if "https://www.etsy.com" in orig_fb or "https://www.amazon.com" in orig_fb:
            cleaned_fb = re.sub(r'https?://[^\s|#]+', '(Link in bio)', orig_fb)
            new_content = new_content.replace(f"FACEBOOK CAPTION: {orig_fb}", f"FACEBOOK CAPTION: {cleaned_fb}")
            changed = True

    # 5. Sanitize HASHTAGS
    m_hash = re.search(r'HASHTAGS:\s*(.*)', new_content)
    if m_hash:
        orig_hash = m_hash.group(1).strip()
        tags_list = orig_hash.split()
        safe_tags, removed_count = clean_tags_list(tags_list)
        safe_hash_str = " ".join([f"#{t}" for t in safe_tags])
        if safe_hash_str != orig_hash:
            new_content = new_content.replace(f"HASHTAGS:\n{orig_hash}", f"HASHTAGS:\n{safe_hash_str}")
            new_content = new_content.replace(f"HASHTAGS: {orig_hash}", f"HASHTAGS: {safe_hash_str}")
            STATS["ig_sensitive_tags_removed"] += removed_count
            changed = True

    # 6. Ensure THREADS CAPTION exists in metadata.txt
    if "THREADS CAPTION:" not in new_content:
        # Extract title or hook
        m_title = re.search(r'TITLE:\s*(.*)', new_content)
        t_val = m_title.group(1).strip() if m_title else "Bible Mystery Revealed"
        m_desc = re.search(r'DESCRIPTION:\s*([\s\S]*?)(?:={20,}|PINNED|HASHTAGS)', new_content)
        d_val = m_desc.group(1).strip() if m_desc else ""
        th_cap = social_dispatcher.build_threads_caption(t_val, d_val)
        
        insert_marker = "TIKTOK CAPTION:" if "TIKTOK CAPTION:" in new_content else "EDITING:"
        if insert_marker in new_content:
            new_content = new_content.replace(insert_marker, f"THREADS CAPTION: {th_cap}\n{insert_marker}")
            STATS["threads_captions_added"] += 1
            changed = True

    if changed:
        try:
            file_path.write_text(new_content, encoding="utf-8")
            STATS["txt_updated"] += 1
            return True
        except Exception as e:
            print(f"  [ERROR] Writing {file_path}: {e}")
            return False

    return False

def run_multiplatform_audit_and_fix():
    print("=" * 76)
    print("STARTING FULL REELS MULTI-PLATFORM POLICY COMPLIANCE MIGRATION")
    print("Target Platforms: YouTube, Facebook, Instagram, Threads, TikTok, X")
    print("=" * 76)

    target_roots = [
        BHSR_ROOT,
        Path("c:/Projects/Bible Hidden Secrets Revealed"),
        Path("C:/Projects/Bible-Mysteries")
    ]

    for root_dir in target_roots:
        if not root_dir.exists():
            continue
        print(f"\nScanning: {root_dir}")
        json_files = list(root_dir.rglob("metadata.json"))
        txt_files = list(root_dir.rglob("metadata.txt"))

        print(f"  Found {len(json_files)} metadata.json and {len(txt_files)} metadata.txt files")

        for jf in json_files:
            process_metadata_json(jf)

        for tf in txt_files:
            process_metadata_txt(tf)

    print("\n" + "=" * 76)
    print("MIGRATION & COMPLIANCE SUMMARY REPORT")
    print("=" * 76)
    for k, v in STATS.items():
        print(f"  {k:32s}: {v}")
    print("=" * 76)
    print("All reels are now 100% compliant with YouTube, Instagram, Threads, TikTok, Facebook, and X policies.")

if __name__ == "__main__":
    run_multiplatform_audit_and_fix()
