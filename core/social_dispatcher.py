import json
import time
import os
import asyncio
import requests
import re
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List, Optional
from core.config import config_manager
from core.asset_manager import asset_manager

DEFAULT_BHRS_MERCH_BLOCK = """============================================================
🛒 OFFICIAL MERCH & BOOKS:
✨ Etsy Store (Merch & Art): https://www.etsy.com/shop/BibleHiddenGems
📖 Book 1 (Amazon): https://www.amazon.com/dp/B0H9NX1BL2
📖 Book 2 (Amazon): https://www.amazon.com/dp/B0H9S491BG
============================================================"""

class SocialDispatcher:
    def __init__(self):
        pass

    @staticmethod
    def get_docker_path(file_path: Optional[Path]) -> str:
        r"""Converts a local host Path under C:\Projects into an n8n container path under /data/projects."""
        if not file_path:
            return ""
        resolved = str(Path(file_path).resolve())
        for prefix in ["C:\\Projects\\", "c:\\Projects\\", "C:/Projects/", "c:/Projects/", "C:\\projects\\", "c:\\projects\\"]:
            if resolved.startswith(prefix):
                rel = resolved[len(prefix):].replace("\\", "/")
                return f"/data/projects/{rel}"
        if resolved.startswith("/data/projects/"):
            return resolved
        clean = re.sub(r'^[a-zA-Z]:[\\/]', '', resolved).replace("\\", "/")
        return f"/data/projects/{clean}"

    def find_custom_thumbnail(self, project_path: Path, video_rel_path: str) -> Optional[Path]:
        """Scans the video directory for preferred custom thumbnail files (e.g. thumbnail_option_1.jpg, thumbnail.png, cover.jpg)."""
        video_abs_path = project_path / video_rel_path
        video_dir = video_abs_path.parent if video_abs_path.is_file() else video_abs_path
        if not video_dir.exists():
            return None

        # 1. Preferred option 1 thumbnail (standard in BHRS-Youtube long-form episodes)
        for name in [
            "thumbnail_option_1.jpg", "thumbnail_option_1.png", "thumbnail_option_1.jpeg", "thumbnail_option_1.webp",
            "thumbnail_1.jpg", "thumbnail_1.png", "thumbnail_1.jpeg", "thumbnail_1.webp",
            "thumbnail-1.jpg", "thumbnail-1.png"
        ]:
            cand = video_dir / name
            if cand.is_file() and cand.stat().st_size > 0:
                return cand

        # 2. Generic thumbnail or cover
        for name in [
            "thumbnail.jpg", "thumbnail.png", "thumbnail.jpeg", "thumbnail.webp",
            "cover.jpg", "cover.png", "cover.jpeg", "cover.webp",
            "poster.jpg", "poster.png"
        ]:
            cand = video_dir / name
            if cand.is_file() and cand.stat().st_size > 0:
                return cand

        # 3. Video stem matching image (e.g. {video_stem}.jpg)
        stem = video_abs_path.stem
        for ext in [".jpg", ".png", ".jpeg", ".webp"]:
            cand = video_dir / f"{stem}{ext}"
            if cand.is_file() and cand.stat().st_size > 0:
                return cand

        # 4. Any other numbered thumbnail option (option 2, option 3)
        for cand in sorted(video_dir.glob("thumbnail_option_*.*")):
            if cand.is_file() and cand.suffix.lower() in [".jpg", ".png", ".jpeg", ".webp"] and cand.stat().st_size > 0:
                return cand

        # 5. Any *thumbnail*.* in directory
        for cand in sorted(video_dir.glob("*thumbnail*.*")):
            if cand.is_file() and cand.suffix.lower() in [".jpg", ".png", ".jpeg", ".webp"] and cand.stat().st_size > 0:
                return cand

        # 6. Check images/ subfolder if present
        images_dir = video_dir / "images"
        if images_dir.exists() and images_dir.is_dir():
            for name in ["thumbnail_option_1.jpg", "thumbnail.jpg", "cover.jpg", "thumbnail.png"]:
                cand = images_dir / name
                if cand.is_file() and cand.stat().st_size > 0:
                    return cand
            for cand in sorted(images_dir.glob("*thumbnail*.*")):
                if cand.is_file() and cand.suffix.lower() in [".jpg", ".png", ".jpeg", ".webp"] and cand.stat().st_size > 0:
                    return cand

        return None

    @classmethod
    def format_social_description(
        cls,
        hook: str,
        body: str,
        merch_block: str = "",
        hashtags: str = "",
        timestamps: str = "",
        platform: str = "facebook",
        is_short_or_reel: bool = True
    ) -> str:
        """
        Builds the unified standardized description for Facebook, Instagram, and YouTube.
        - Facebook & Instagram (Images 1 & 2): [Hook/Title] + [Body] + [Full Merch Block with Direct URLs] + [Hashtags]
        - YouTube Shorts (Image 3): [Hook/Title] + [Body] + [Merch Block with bio links] + [Hashtags]
        - YouTube Long-Form: [Hook/Title] + [Body] + [Timestamps] + [Full Merch Block with Direct URLs] + [Hashtags]
        """
        blocks = []

        # 1. Top Hook or Title
        top_line = (hook or "").strip()
        if top_line:
            blocks.append(top_line)

        # 2. Body / Story description
        body_clean = (body or "").strip()
        if body_clean:
            blocks.append(body_clean)

        # 3. Timestamps (if long-form video or chapters provided)
        ts_clean = (timestamps or "").strip()
        if ts_clean:
            blocks.append(ts_clean)

        # 4. Merch Block
        mb_clean = (merch_block or "").strip()
        if mb_clean:
            if "youtube" in platform.lower():
                mb_formatted = cls.sanitize_urls_for_youtube(mb_clean)
            else:
                mb_formatted = mb_clean
            blocks.append(mb_formatted)

        # 5. Hashtags
        ht_clean = (hashtags or "").strip()
        if ht_clean:
            blocks.append(ht_clean)

        res = "\n\n".join(blocks).strip()
        # Strictly guarantee NO URLs exist anywhere in YouTube descriptions
        if "youtube" in platform.lower():
            res = cls.sanitize_urls_for_youtube(res)
        return res

    def extract_metadata_for_video(self, project_path: Path, video_rel_path: str) -> Dict[str, Any]:
        """Looks for adjacent metadata.json, metadata.txt, or youtube_metadata.md to build title, rich description, tags, custom thumbnail and platform captions."""
        base_name = Path(video_rel_path).stem.replace("_", " ").title()
        title = base_name
        hook_text = ""
        description = f"Generated by AI Content Generation Pipeline.\nStory chapter: {base_name}"
        tags = ["anime", "manhwa", "recap", "ai-video", "flux", "vibevoice", "story"]
        thumbnail_text = ""
        merch_block = ""
        pinned_comment = ""
        youtube_shorts_title = ""
        youtube_description = ""
        facebook_caption = ""
        instagram_caption = ""
        tiktok_caption = ""
        timestamps_block = ""
        body_description = ""

        # 1. Search for existing metadata via asset_manager
        meta_file = asset_manager.find_or_create_metadata_file(str(project_path), video_rel_path)
        if meta_file and meta_file.exists() and meta_file.is_file():
            try:
                content = meta_file.read_text(encoding="utf-8")
            except Exception:
                try:
                    content = meta_file.read_text(encoding="cp1252", errors="replace")
                except Exception:
                    content = ""

            if content:
                # If JSON metadata (standard for BHRS long-form videos)
                if meta_file.suffix.lower() == ".json":
                    try:
                        jdata = json.loads(content)
                        if isinstance(jdata, dict):
                            title = jdata.get("title") or title
                            hook_text = (jdata.get("hook") or "").strip()
                            body_description = (jdata.get("description") or "").strip()
                            if isinstance(jdata.get("tags"), list):
                                tags = [str(t).strip().lstrip("#") for t in jdata.get("tags") if str(t).strip()]
                            elif isinstance(jdata.get("tags"), str):
                                tags = [t.strip().lstrip("#") for t in jdata.get("tags").split(",") if t.strip()]
                            thumbnail_text = jdata.get("thumbnail_text", "").strip()
                            merch_block = jdata.get("merch_block", "").strip()
                            pinned_comment = jdata.get("pinned_comment", "").strip()
                            youtube_shorts_title = jdata.get("youtube_shorts_title", "").strip()
                            youtube_description = jdata.get("youtube_description", "").strip()
                            facebook_caption = jdata.get("facebook_caption", "").strip()
                            instagram_caption = jdata.get("instagram_caption", "").strip()
                            tiktok_caption = jdata.get("tiktok_caption", "").strip()

                            # Timestamps / Chapters
                            raw_timestamps = jdata.get("timestamps", [])
                            if isinstance(raw_timestamps, list) and raw_timestamps:
                                timestamps_block = "TIMESTAMPS:\n" + "\n".join(str(ts).strip() for ts in raw_timestamps if str(ts).strip())
                            elif isinstance(raw_timestamps, str) and raw_timestamps.strip():
                                timestamps_block = "TIMESTAMPS:\n" + raw_timestamps.strip()
                    except Exception:
                        pass
                else:
                    # Markdown / TXT parsing (standard for Shorts)
                    lines = content.splitlines()
                    body_desc_lines = []
                    hashtags_lines = []
                    current_section = None
                    has_explicit_tags = False
                    i = 0
                    
                    while i < len(lines):
                        line = lines[i]
                        clean = line.strip()

                        # Check for Merch & Books block
                        if clean.startswith("===") and i + 1 < len(lines) and ("official merch" in lines[i+1].lower() or "merch & books" in lines[i+1].lower()):
                            # If we are inside an explicit platform caption, allow continuation to capture it
                            if current_section in ("facebook_caption", "instagram_caption", "youtube_description", "tiktok_caption"):
                                pass
                            else:
                                current_section = None
                                merch_lines = [line]
                                i += 1
                                while i < len(lines):
                                    merch_lines.append(lines[i])
                                    if lines[i].strip().startswith("===") and len(merch_lines) > 2:
                                        break
                                    i += 1
                                parsed_mb = "\n".join(merch_lines).strip()
                                # Keep the block with direct clickable URLs
                                if not merch_block or ("http" in parsed_mb and "http" not in merch_block):
                                    merch_block = parsed_mb
                                i += 1
                                continue

                        # Check key headers
                        m_title = re.match(r'^(?:#\s*)?title\s*:\s*(.*)', clean, re.IGNORECASE)
                        m_hook = re.match(r'^(?:#\s*)?hook\s*:\s*(.*)', clean, re.IGNORECASE)
                        m_thumb = re.match(r'^(?:#\s*)?thumbnail(?:\s+text)?\s*:\s*(.*)', clean, re.IGNORECASE)
                        m_desc = re.match(r'^(?:#\s*)?description\s*:\s*(.*)', clean, re.IGNORECASE)
                        m_pinned = re.match(r'^(?:#\s*)?pinned(?:\s+comment)?\s*:\s*(.*)', clean, re.IGNORECASE)
                        m_hash = re.match(r'^(?:#\s*)?hashtags?\s*:\s*(.*)', clean, re.IGNORECASE)
                        m_tags = re.match(r'^(?:#\s*)?tags\s*:\s*(.*)', clean, re.IGNORECASE)
                        m_yt = re.match(r'^(?:#\s*)?youtube\s+shorts\s+title\s*:\s*(.*)', clean, re.IGNORECASE)
                        m_ytd = re.match(r'^(?:#\s*)?youtube\s+description\s*:\s*(.*)', clean, re.IGNORECASE)
                        m_fb = re.match(r'^(?:#\s*)?facebook\s+caption\s*:\s*(.*)', clean, re.IGNORECASE)
                        m_ig = re.match(r'^(?:#\s*)?instagram\s+caption\s*:\s*(.*)', clean, re.IGNORECASE)
                        m_tt = re.match(r'^(?:#\s*)?tiktok\s+caption\s*:\s*(.*)', clean, re.IGNORECASE)
                        m_edit = re.match(r'^(?:#\s*)?editing\s*:', clean, re.IGNORECASE)

                        if m_title:
                            current_section = "title"
                            val = m_title.group(1).strip()
                            if val:
                                title = val
                        elif m_hook:
                            current_section = "hook"
                            val = m_hook.group(1).strip()
                            if val:
                                hook_text = val
                        elif m_thumb:
                            current_section = "thumbnail_text"
                            val = m_thumb.group(1).strip()
                            if val:
                                thumbnail_text = val
                        elif m_desc:
                            current_section = "description"
                            val = m_desc.group(1).strip()
                            if val:
                                body_desc_lines.append(val)
                        elif m_pinned:
                            current_section = "pinned_comment"
                            val = m_pinned.group(1).strip()
                            if val:
                                pinned_comment = val
                        elif m_hash:
                            current_section = "hashtags"
                            val = m_hash.group(1).strip()
                            if val:
                                hashtags_lines.append(val)
                        elif m_tags:
                            current_section = "tags"
                            val = m_tags.group(1).strip()
                            if val:
                                parsed_tags = [t.strip().lstrip("#") for t in val.split(",") if t.strip()]
                                if parsed_tags:
                                    tags = parsed_tags
                                    has_explicit_tags = True
                        elif m_yt:
                            current_section = "youtube_shorts_title"
                            val = m_yt.group(1).strip()
                            if val:
                                youtube_shorts_title = val
                        elif m_ytd:
                            current_section = "youtube_description"
                            val = m_ytd.group(1).strip()
                            if val:
                                youtube_description = val
                        elif m_fb:
                            current_section = "facebook_caption"
                            val = m_fb.group(1).strip()
                            if val:
                                facebook_caption = val
                        elif m_ig:
                            current_section = "instagram_caption"
                            val = m_ig.group(1).strip()
                            if val:
                                instagram_caption = val
                        elif m_tt:
                            current_section = "tiktok_caption"
                            val = m_tt.group(1).strip()
                            if val:
                                tiktok_caption = val
                        elif m_edit:
                            current_section = "editing"
                        else:
                            # Continuation of previous multi-line section
                            if current_section == "description":
                                if clean.startswith("==="):
                                    current_section = None
                                elif clean:
                                    body_desc_lines.append(clean)
                            elif current_section == "hook":
                                if clean:
                                    hook_text = (hook_text + " " + clean).strip()
                            elif current_section == "pinned_comment":
                                if clean.startswith("===") or clean.startswith("#") or clean.startswith("HASHTAGS"):
                                    current_section = None
                                elif clean:
                                    pinned_comment = (pinned_comment + "\n" + clean).strip()
                            elif current_section == "hashtags":
                                if clean.startswith("#") or clean:
                                    hashtags_lines.append(clean)
                            elif current_section == "youtube_description":
                                youtube_description = (youtube_description + "\n" + line.strip()) if youtube_description else line.strip()
                            elif current_section == "facebook_caption":
                                facebook_caption = (facebook_caption + "\n" + line.strip()) if facebook_caption else line.strip()
                            elif current_section == "instagram_caption":
                                instagram_caption = (instagram_caption + "\n" + line.strip()) if instagram_caption else line.strip()
                            elif current_section == "tiktok_caption":
                                tiktok_caption = (tiktok_caption + "\n" + line.strip()) if tiktok_caption else line.strip()
                            elif not current_section:
                                if clean.startswith("# ") and not title:
                                    title = clean.lstrip("#").strip()
                                elif not clean.startswith("===") and not clean.startswith("EPISODE") and clean:
                                    if not body_desc_lines:
                                        body_desc_lines.append(clean)

                        i += 1

                    # Parse tags from hashtags if found
                    all_hashtags_str = " ".join(hashtags_lines).strip()
                    if all_hashtags_str and not has_explicit_tags:
                        extracted_tags = [t.lstrip("#") for t in re.findall(r'#(\w+)', all_hashtags_str)]
                        if extracted_tags:
                            tags = extracted_tags

                    body_description = "\n\n".join(body_desc_lines).strip()

        # Check default merch block if none is explicitly specified
        if not merch_block:
            proj_str = f"{project_path.name} {video_rel_path}".lower()
            if "bhrs" in proj_str or "bible" in proj_str or "covenant" in proj_str:
                merch_block = DEFAULT_BHRS_MERCH_BLOCK

        # Format hashtags string
        hashtags_list = [f"#{t.replace(' ', '').lstrip('#')}" for t in tags if t]
        hashtags_string = " ".join(hashtags_list)

        # Check if video is short/reel vs long-form
        v_low = str(video_rel_path).lower()
        is_reel_or_short = "reel" in v_low or "short" in v_low
        if not is_reel_or_short:
            try:
                minfo = asset_manager.get_media_info(project_path / video_rel_path)
                dur = minfo.get("duration_sec", 0.0)
                res = minfo.get("resolution", "")
                if ("x" in res and int(res.split("x")[1]) > int(res.split("x")[0])) or (0 < dur <= 60):
                    is_reel_or_short = True
            except Exception:
                pass

        # Determine top hook / headline line:
        # 1. Explicit hook_text from metadata if present
        # 2. Thumbnail text ONLY if it is short, uppercase, and does not contain "=" or ":" (e.g. "JERICHO — WALLS FELL OUTWARD")
        # 3. Video title (standard headline, e.g. "The First Death in the Bible Was GOD Killing an Animal — For Clothing")
        top_hook = ""
        if hook_text:
            top_hook = hook_text
        elif thumbnail_text and ("=" not in thumbnail_text) and (":" not in thumbnail_text) and len(thumbnail_text) <= 80 and thumbnail_text == thumbnail_text.upper():
            top_hook = thumbnail_text
        elif title:
            top_hook = title
        elif thumbnail_text:
            top_hook = thumbnail_text

        # Build standardized descriptions for each platform
        # Standard full description with direct URLs (Format for Facebook & Instagram)
        standard_full_description = self.format_social_description(
            hook=top_hook,
            body=body_description,
            merch_block=merch_block,
            hashtags=hashtags_string,
            timestamps=timestamps_block,
            platform="facebook",
            is_short_or_reel=is_reel_or_short
        )

        # YouTube description (Sanitized bio links for Shorts, direct URLs for long-form)
        standard_youtube_description = self.format_social_description(
            hook=top_hook,
            body=body_description,
            merch_block=merch_block,
            hashtags=hashtags_string,
            timestamps=timestamps_block,
            platform="youtube",
            is_short_or_reel=is_reel_or_short
        )

        # Check if parsed captions already have the full multi-section layout (contains merch block divider or official merch & books header)
        # If not, use the standardized full description to prevent legacy single-paragraph snippets
        is_full_fb = bool(facebook_caption and ("====" in facebook_caption or "official merch & books" in facebook_caption.lower()))
        is_full_ig = bool(instagram_caption and ("====" in instagram_caption or "official merch & books" in instagram_caption.lower()))
        is_full_yt = bool(youtube_description and ("====" in youtube_description or "official merch & books" in youtube_description.lower()))

        final_fb_caption = facebook_caption if is_full_fb else standard_full_description
        final_ig_caption = instagram_caption if is_full_ig else standard_full_description
        final_yt_description = self.sanitize_urls_for_youtube(youtube_description) if is_full_yt else standard_youtube_description
        final_description = standard_full_description or body_description

        caption = f"{top_hook or title}\n\n{hashtags_string}".strip()

        # 2. Check for custom thumbnail in video folder
        thumb_file = self.find_custom_thumbnail(project_path, video_rel_path)
        has_custom_thumb = bool(thumb_file and thumb_file.exists())
        thumbnail_abs_path = str(thumb_file.resolve()) if has_custom_thumb else ""
        thumbnail_rel_path = str(thumb_file.relative_to(project_path)).replace("\\", "/") if has_custom_thumb else ""
        thumbnail_docker_path = self.get_docker_path(thumb_file) if has_custom_thumb else ""

        return {
            "title": title,
            "hook": top_hook,
            "description": final_description,
            "youtube_description": final_yt_description,
            "tags": tags,
            "hashtags_string": hashtags_string,
            "caption": caption,
            "thumbnail_text": thumbnail_text,
            "merch_block": merch_block,
            "pinned_comment": pinned_comment,
            "youtube_shorts_title": youtube_shorts_title,
            "facebook_caption": final_fb_caption,
            "instagram_caption": final_ig_caption,
            "tiktok_caption": tiktok_caption or final_description,
            "has_custom_thumbnail": has_custom_thumb,
            "thumbnail_filename": thumb_file.name if has_custom_thumb else "",
            "thumbnail_rel_path": thumbnail_rel_path,
            "thumbnail_abs_path": thumbnail_abs_path,
            "thumbnail_docker_path": thumbnail_docker_path
        }

    @staticmethod
    def sanitize_urls_for_youtube(text: str) -> str:
        """Replaces all raw http/https and www links with '🔗 (Link in channel bio)' for YouTube compliance (no raw external URLs)."""
        if not text:
            return ""
        t = re.sub(r'[-–—:|]?\s*https?://\S+', ' 🔗 (Link in channel bio)', text)
        t = re.sub(r'[-–—:|]?\s*www\.\S+', ' 🔗 (Link in channel bio)', t)
        return t

    def _build_auth_headers(self, auth_header: Optional[str]) -> Dict[str, str]:
        """Constructs headers dictionary with authentication if provided."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "KCT-Studio-Pipeline/2.0"
        }
        if auth_header and auth_header.strip():
            raw = auth_header.strip()
            if ":" in raw:
                k, v = raw.split(":", 1)
                headers[k.strip()] = v.strip()
            else:
                if raw.lower().startswith("bearer ") or raw.lower().startswith("basic "):
                    headers["Authorization"] = raw
                else:
                    headers["Authorization"] = f"Bearer {raw}"
        return headers

    def test_webhook(self, webhook_url: Optional[str] = None, auth_header: Optional[str] = None, project_path: Optional[str] = None) -> Dict[str, Any]:
        """Sends a verification ping to the webhook URL and measures response time."""
        cfg = config_manager.get_project_social_config(project_path)
        target_url = (webhook_url or cfg.get("webhook_url", "")).strip()
        auth = auth_header if auth_header is not None else cfg.get("webhook_auth_header", "")

        if not target_url:
            return {"success": False, "error": "No Webhook URL provided or configured."}

        headers = self._build_auth_headers(auth)
        test_payload = {
            "event": "test_ping",
            "source": "KCT Studio AI Video Pipeline",
            "dry_run": True,
            "video": {
                "filename": "test_ping.mp4",
                "abs_path": "",
                "rel_path": "test_ping.mp4"
            },
            "timestamp": time.time(),
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "message": "Webhook connectivity test from KCT Studio dashboard.",
            "target_platforms": ["youtube", "facebook", "instagram", "tiktok", "x"]
        }

        start_time = time.perf_counter()
        try:
            resp = requests.post(target_url, json=test_payload, headers=headers, timeout=8)
            latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
            is_ok = 200 <= resp.status_code < 300
            return {
                "success": is_ok,
                "status_code": resp.status_code,
                "latency_ms": latency_ms,
                "response_preview": resp.text[:300] if resp.text else "(Empty response body)",
                "target_url": target_url
            }
        except requests.exceptions.Timeout:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
            return {
                "success": False,
                "error": f"Connection timed out after 8s ({latency_ms}ms)",
                "latency_ms": latency_ms,
                "target_url": target_url
            }
        except Exception as e:
            latency_ms = round((time.perf_counter() - start_time) * 1000, 1)
            return {
                "success": False,
                "error": str(e),
                "latency_ms": latency_ms,
                "target_url": target_url
            }

    async def publish_video(self, project_path_str: str, video_rel_path: str, platforms: Optional[List[str]] = None, custom_title: Optional[str] = None, custom_desc: Optional[str] = None, custom_tags: Optional[List[str]] = None, force_republish: bool = False) -> Dict[str, Any]:
        project_path = Path(project_path_str)
        video_abs_path = project_path / video_rel_path
        if not video_abs_path.exists():
            return {"success": False, "error": f"Video file not found: {video_abs_path}"}

        cfg = config_manager.get_project_social_config(project_path_str)
        dry_run = cfg.get("dry_run", True)
        webhook_url = cfg.get("webhook_url", "").strip()
        auth_header = cfg.get("webhook_auth_header", "").strip()

        all_platforms = ["youtube", "facebook", "instagram", "tiktok", "x"]
        target_platforms = platforms if platforms else [p for p in all_platforms if cfg.get(p, {}).get("enabled", True)]

        # Check existing publication records in asset manager
        rec = asset_manager.get_asset_record(video_rel_path)
        existing_published = rec.get("published", {})
        already_published_platforms = [
            p for p, pdata in existing_published.items() 
            if pdata.get("status") == "published"
        ]

        if not force_republish:
            unposted = [p for p in target_platforms if p not in already_published_platforms]
            if unposted:
                # Target only unposted platforms
                target_platforms = unposted
                is_already_posted = False
            else:
                # All selected platforms are already published
                is_already_posted = True
        else:
            is_already_posted = False

        meta = self.extract_metadata_for_video(project_path, video_rel_path)

        vid_stem_title = video_abs_path.stem.replace("_", " ").title()
        if custom_title and custom_title.strip() and custom_title.strip() != vid_stem_title:
            title = custom_title
        else:
            title = meta.get("title") or custom_title or vid_stem_title

        if custom_desc and not custom_desc.startswith("Generated by AI Content Generation Pipeline"):
            desc = custom_desc
        else:
            desc = meta.get("description") or custom_desc or ""

        tags = custom_tags if custom_tags is not None else meta["tags"]
        hashtags_string = meta.get("hashtags_string") or " ".join([f"#{t}" for t in tags])
        caption = f"{title}\n\n{hashtags_string}".strip()

        # Video media specifications
        stat = video_abs_path.stat()
        media_info = asset_manager.get_media_info(video_abs_path)
        duration_str = media_info.get("duration") or "N/A"
        duration_sec = media_info.get("duration_sec") or 0.0
        resolution = media_info.get("resolution") or "1920x1080"
        
        # Check aspect ratio
        is_short_or_reel = False
        aspect_ratio = "16:9"
        if "x" in resolution:
            try:
                w, h = map(int, resolution.split("x"))
                if h > w:
                    aspect_ratio = "9:16"
                    is_short_or_reel = True
                elif duration_sec > 0 and duration_sec <= 60:
                    is_short_or_reel = True
            except Exception:
                pass

        has_custom_thumb = meta.get("has_custom_thumbnail", False)
        thumb_abs = meta.get("thumbnail_abs_path", "")
        thumb_rel = meta.get("thumbnail_rel_path", "")
        thumb_docker = meta.get("thumbnail_docker_path", "")

        video_spec = {
            "filename": video_abs_path.name,
            "rel_path": video_rel_path.replace("\\", "/"),
            "abs_path": str(video_abs_path.resolve()),
            "docker_path": self.get_docker_path(video_abs_path),
            "size_bytes": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "duration": duration_str,
            "duration_sec": duration_sec,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "is_short_or_reel": is_short_or_reel,
            "has_custom_thumbnail": has_custom_thumb,
            "thumbnail_filename": Path(thumb_abs).name if thumb_abs else "",
            "thumbnail_rel_path": thumb_rel,
            "thumbnail_abs_path": thumb_abs,
            "thumbnail_docker_path": thumb_docker,
            "thumbnail_path": thumb_docker,
            "local_url": f"/api/media/{urllib.parse.quote(video_rel_path.replace('\\', '/'), safe='/')}",
            "already_published_platforms": already_published_platforms,
            "is_already_posted": is_already_posted and not force_republish,
            "published_history": existing_published
        }

        if custom_desc and not custom_desc.startswith("Generated by AI Content Generation Pipeline"):
            desc = custom_desc
            fb_desc = custom_desc
            ig_desc = custom_desc
            yt_desc = self.sanitize_urls_for_youtube(custom_desc)
        else:
            desc = meta.get("description") or ""
            fb_desc = meta.get("facebook_caption") or desc
            ig_desc = meta.get("instagram_caption") or desc
            yt_desc = self.sanitize_urls_for_youtube(meta.get("youtube_description") or desc)

        content_spec = {
            "title": title,
            "description": desc,
            "youtube_description": yt_desc,
            "tags": tags,
            "hashtags_string": hashtags_string,
            "caption": caption,
            "thumbnail_text": meta.get("thumbnail_text", ""),
            "merch_block": meta.get("merch_block", ""),
            "pinned_comment": meta.get("pinned_comment", ""),
            "youtube_shorts_title": meta.get("youtube_shorts_title", ""),
            "facebook_caption": fb_desc,
            "instagram_caption": ig_desc,
            "tiktok_caption": meta.get("tiktok_caption") or desc
        }

        project_spec = {
            "name": project_path.name,
            "path": str(project_path.resolve())
        }

        platform_configs = {p: cfg.get(p, {}) for p in all_platforms}

        results = {}

        # 1. External Webhook Dispatch (Zapier, Make, n8n)
        webhook_status = None
        if webhook_url:
            payload = {
                "event": "video_approved_and_publish",
                "dry_run": dry_run,
                "project": project_spec,
                "video": video_spec,
                "content": content_spec,
                "target_platforms": target_platforms,
                "already_published_platforms": already_published_platforms,
                "is_already_posted": is_already_posted and not force_republish,
                "force_republish": force_republish,
                "platform_configs": platform_configs,
                "timestamp": time.time(),
                "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
            try:
                headers = self._build_auth_headers(auth_header)
                if not dry_run:
                    start_t = time.perf_counter()
                    video_mb = video_spec.get("size_mb", 50)
                    calc_timeout = max(3600, int(video_mb * 10))
                    resp = await asyncio.to_thread(requests.post, webhook_url, json=payload, headers=headers, timeout=calc_timeout)
                    latency = round((time.perf_counter() - start_t) * 1000, 1)
                    try:
                        resp_data = resp.json()
                    except Exception:
                        resp_data = resp.text[:300]
                    webhook_status = {
                        "status_code": resp.status_code,
                        "latency_ms": latency,
                        "response": resp_data
                    }
                    if resp.status_code >= 400:
                        webhook_status["error"] = f"Webhook returned HTTP {resp.status_code}"
                else:
                    webhook_status = {
                        "status_code": 200,
                        "simulated": True,
                        "payload": payload
                    }
            except Exception as e:
                webhook_status = {"error": str(e)}

        # Check if webhook dispatch failed
        if not dry_run and webhook_url and isinstance(webhook_status, dict):
            if webhook_status.get("error") or webhook_status.get("status_code", 200) >= 400:
                err_detail = webhook_status.get("error") or f"Webhook returned HTTP {webhook_status.get('status_code')}"
                resp_val = webhook_status.get("response")
                if isinstance(resp_val, dict) and resp_val.get("message"):
                    err_detail = f"{err_detail}: {resp_val.get('message')}"
                elif isinstance(resp_val, str) and resp_val.strip():
                    err_detail = f"{err_detail}: {resp_val.strip()[:200]}"

                fail_results = {}
                for plat in target_platforms:
                    fail_results[plat] = {
                        "status": "failed",
                        "platform": plat,
                        "error": err_detail
                    }

                return {
                    "success": False,
                    "error": err_detail,
                    "dry_run": False,
                    "title": title,
                    "video": video_abs_path.name,
                    "webhook_result": webhook_status,
                    "platforms": fail_results
                }

            # Check if webhook responded with an explicit error in JSON
            resp_json = webhook_status.get("response")
            if isinstance(resp_json, dict) and resp_json.get("success") is False:
                err_detail = resp_json.get("message") or resp_json.get("error") or "Webhook workflow reported failure"
                fail_results = {}
                for plat in target_platforms:
                    fail_results[plat] = {
                        "status": "failed",
                        "platform": plat,
                        "error": err_detail
                    }
                return {
                    "success": False,
                    "error": err_detail,
                    "dry_run": False,
                    "title": title,
                    "video": video_abs_path.name,
                    "webhook_result": webhook_status,
                    "platforms": fail_results
                }

        # If webhook indicates the video was already posted, return immediately without re-marking
        if isinstance(webhook_status, dict):
            resp_json = webhook_status.get("response")
            if isinstance(resp_json, dict) and resp_json.get("already_posted"):
                return {
                    "success": False,
                    "already_posted": True,
                    "skipped": True,
                    "title": title,
                    "video": video_abs_path.name,
                    "message": resp_json.get("message") or "Video/image is already posted to target platform. Dispatch halted to prevent duplicate.",
                    "webhook_result": webhook_status,
                    "platforms": {
                        p: {
                            "status": "skipped",
                            "message": "Already posted",
                            "url": existing_published.get(p, {}).get("details", {}).get("url")
                        }
                        for p in target_platforms
                    }
                }

        # 2. Individual Platform Handlers & Status Tracking
        for plat in target_platforms:
            plat_cfg = cfg.get(plat, {})
            if dry_run:
                # Simulated dispatch
                res = {
                    "status": "success",
                    "mode": "DRY_RUN (Simulated)",
                    "message": f"Simulated posting to {plat.upper()} with title '{title}'",
                    "video": video_abs_path.name,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            else:
                # Live dispatch handlers
                res = self._dispatch_to_platform(plat, plat_cfg, video_abs_path, title, desc, tags)

            results[plat] = res
            if not dry_run and plat == "youtube" and isinstance(webhook_status, dict):
                resp_json = webhook_status.get("response")
                if isinstance(resp_json, dict) and resp_json.get("youtube_url"):
                    results[plat]["url"] = resp_json["youtube_url"]
                    results[plat]["id"] = resp_json.get("youtube_id")
                    results[plat]["status"] = "published"
                    results[plat]["message"] = f"Published to YouTube: {resp_json['youtube_url']}"
                elif isinstance(resp_json, dict) and resp_json.get("success"):
                    results[plat]["status"] = "published"
                    results[plat]["url"] = resp_json.get("youtube_url", "")
                    results[plat]["message"] = "Published to YouTube via n8n"
                else:
                    results[plat]["status"] = "failed"
                    results[plat]["error"] = "YouTube upload did not return a confirmed video URL"
            elif not dry_run and plat == "facebook" and isinstance(webhook_status, dict):
                resp_json = webhook_status.get("response")
                if isinstance(resp_json, dict) and (resp_json.get("facebook_id") or resp_json.get("facebook_url")):
                    fb_id = resp_json.get("facebook_id")
                    results[plat]["url"] = resp_json.get("facebook_url") or f"https://www.facebook.com/watch/?v={fb_id}"
                    results[plat]["id"] = fb_id
                    results[plat]["status"] = "published"
                    results[plat]["message"] = f"Published to Facebook: {results[plat]['url']}"
                elif isinstance(resp_json, dict) and resp_json.get("success"):
                    results[plat]["status"] = "published"
                    results[plat]["message"] = "Published to Facebook via n8n"
            elif not dry_run and plat == "instagram" and isinstance(webhook_status, dict):
                resp_json = webhook_status.get("response")
                if isinstance(resp_json, dict) and (resp_json.get("instagram_id") or resp_json.get("instagram_url")):
                    results[plat]["url"] = resp_json.get("instagram_url") or ""
                    results[plat]["id"] = resp_json.get("instagram_id")
                    results[plat]["status"] = "published"
                    results[plat]["message"] = f"Published to Instagram"
                elif isinstance(resp_json, dict) and resp_json.get("success"):
                    results[plat]["status"] = "published"
                    results[plat]["message"] = "Published to Instagram via n8n"

        # Determine overall success
        overall_success = dry_run or any(r.get("status") == "published" for r in results.values())
        if not overall_success:
            err_msg = next((r.get("error") for r in results.values() if r.get("error")), "Social media dispatch failed.")
            return {
                "success": False,
                "error": err_msg,
                "dry_run": dry_run,
                "title": title,
                "video": video_abs_path.name,
                "webhook_result": webhook_status,
                "platforms": results
            }

        # Mark successfully published platforms in asset manager
        for plat in target_platforms:
            if dry_run or results[plat].get("status") == "published":
                asset_manager.mark_published(video_rel_path, plat, results[plat])

        # Send native desktop notification only on verified success
        try:
            from core.notifier import notify_desktop
            pub_plats = [p.upper() for p, r in results.items() if dry_run or r.get("status") == "published"]
            plat_names = ", ".join(pub_plats) if pub_plats else ", ".join([p.upper() for p in target_platforms])
            action_word = "Reposted" if force_republish else "Published"
            mode_prefix = "[Simulated] " if dry_run else ""
            notify_desktop(
                f"{mode_prefix}Video {action_word}: {plat_names}",
                f"'{title}' was {action_word.lower()} to {plat_names} successfully."
            )
        except Exception:
            pass

        return {
            "success": True,
            "dry_run": dry_run,
            "title": title,
            "video": video_abs_path.name,
            "webhook_result": webhook_status,
            "platforms": results
        }

    def _dispatch_to_platform(self, platform: str, config: Dict[str, Any], video_path: Path, title: str, description: str, tags: List[str]) -> Dict[str, Any]:
        """Modular execution handlers for social platforms."""
        if platform == "youtube":
            return {
                "status": "queued",
                "platform": "YouTube",
                "message": f"Dispatched '{title}' to YouTube uploader queue.",
                "privacy": config.get("privacy_status", "public")
            }
        elif platform == "facebook":
            return {
                "status": "queued",
                "platform": "Facebook",
                "message": f"Posted video '{title}' to Facebook Page."
            }
        elif platform == "instagram":
            return {
                "status": "queued",
                "platform": "Instagram",
                "message": f"Dispatched Reel '{title}' to Instagram Media Publishing API."
            }
        elif platform == "tiktok":
            return {
                "status": "queued",
                "platform": "TikTok",
                "message": f"Dispatched video '{title}' to TikTok Content Creator API."
            }
        elif platform == "x":
            return {
                "status": "queued",
                "platform": "X (Twitter)",
                "message": f"Published video tweet: '{title[:100]}'."
            }
        return {"status": "unsupported", "platform": platform}

social_dispatcher = SocialDispatcher()
