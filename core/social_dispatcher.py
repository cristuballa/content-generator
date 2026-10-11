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
from core.meta_uploader import meta_uploader
from core.youtube_uploader import youtube_uploader
from core.threads_uploader import threads_uploader
from core.tiktok_uploader import tiktok_uploader
from core.hashtags import find_hashtags, normalize_tags, split_tags, strip_hashtags
from core.week_links import (comment_id_of, export_week_links, is_reel, live_documentary_url, week_of,
                             with_documentary_link)

# Posted as the first comment right after every upload (captions themselves carry no links)
DEFAULT_BHRS_PINNED_COMMENT = """🛒 OFFICIAL MERCH & SACRED BOOKS:
✨ Etsy Store (Merch & Art): https://www.etsy.com/shop/BibleHiddenGems
📖 Book of Enoch https://www.etsy.com/nz/listing/4591934547
📖 Study Guide NT https://www.etsy.com/nz/listing/4536465297
📖 Study Guide OT https://www.etsy.com/nz/listing/4526027051
📖 Bible Hidden Secrets https://www.etsy.com/nz/listing/4526030482

👉 Subscribe to Bible Hidden Secrets Revealed for new revelations every week!"""
DEFAULT_BHRS_FIRST_COMMENT = DEFAULT_BHRS_PINNED_COMMENT

# Legacy caption blocks. No longer added to captions (and stripped from old ones); kept only so the older
# one-off scripts in scripts/ still import.
DEFAULT_BHRS_MERCH_BLOCK = """=======================================================
🛒 OFFICIAL MERCH & BOOKS:
✨ Etsy Store (Merch & Art): https://www.etsy.com/shop/BibleHiddenGems
📖 Book of Enoch https://www.etsy.com/nz/listing/4591934547
📖 Study Guide NT https://www.etsy.com/nz/listing/4536465297
📖 Study Guide OT https://www.etsy.com/nz/listing/4526027051
📖 Bible Hidden Secrets https://www.etsy.com/nz/listing/4526030482
======================================================="""
DEFAULT_BHRS_FB_CALLOUT = "📖 Official Books & Sacred Art collection linked in the pinned comment below 👇"
DEFAULT_BHRS_YT_MERCH_BLOCK = DEFAULT_BHRS_MERCH_BLOCK
DEFAULT_BHRS_IG_MERCH_BLOCK = DEFAULT_BHRS_MERCH_BLOCK

# Standard YouTube viewer disclosure for altered or synthetic content (Rule 7)
DEFAULT_YT_AI_DISCLOSURE = "ℹ️ Altered or synthetic content: Sound and visuals in this video are significantly edited or digitally generated."

# Promo text that must not appear in captions: store/book lines, link-in-bio pointers, raw URLs
PROMO_LINE_RE = re.compile(
    r"^[ \t]*(?:🛒|✨\s*Etsy|📖\s*(?:Book|Study|Bible|Official Books|Check our books)|📚\s*Books?|•\s*Book|👉\s*(?:Tap|Find all|Subscribe)|🔗\s*Link in bio)[^\n]*(?:\n|$)",
    re.IGNORECASE | re.MULTILINE
)
INLINE_PROMO_RE = re.compile(r"[ \t]*(?:Follow for more!\s*)?🔗\s*Link in bio[^\n]*|[ \t]*📖\s*Books? & Merch in bio!?", re.IGNORECASE)
CHAPTER_HEADER_RE = re.compile(r"^[ \t]*(?:TIMESTAMPS|CHAPTERS)\b[^\n]*:[ \t]*$\n?", re.IGNORECASE | re.MULTILINE)
CHAPTER_LINE_RE = re.compile(r"^[ \t]*\d{1,2}:\d{2}(?::\d{2})?[ \t]*[-–—][^\n]*$\n?", re.MULTILINE)
URL_RE = re.compile(
    r"(?:https?://|www\.)\S+"
    r"|\b(?:bit\.ly|tinyurl\.com|linktr\.ee|t\.co|cutt\.ly|goo\.gl|ow\.ly|is\.gd|buff\.ly|wa\.me)/\S+"
    r"|\b(?:etsy|amazon)\.com/\S+",
    re.IGNORECASE
)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((?:https?://|www\.)[^)]*\)", re.IGNORECASE)

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

        # 1. The chosen thumbnail: create_thumbnail.py copies its pick to thumbnail.jpg and redesigns overwrite it,
        #    so it wins over the original thumbnail_option_* drafts
        for name in ["thumbnail.jpg", "thumbnail.png", "thumbnail.jpeg", "thumbnail.webp"]:
            cand = video_dir / name
            if cand.is_file() and cand.stat().st_size > 0:
                return cand

        # 2. Option 1 thumbnail (standard in BHRS-Youtube long-form episodes)
        for name in [
            "thumbnail_option_1.jpg", "thumbnail_option_1.png", "thumbnail_option_1.jpeg", "thumbnail_option_1.webp",
            "thumbnail_1.jpg", "thumbnail_1.png", "thumbnail_1.jpeg", "thumbnail_1.webp",
            "thumbnail-1.jpg", "thumbnail-1.png"
        ]:
            cand = video_dir / name
            if cand.is_file() and cand.stat().st_size > 0:
                return cand

        # 3. Cover or poster image
        for name in [
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

    # ------------------------------------------------------------------------------------------------
    # House caption format (every platform), matching the Facebook post the channel standardised on:
    #
    #   HOOK IN CAPITALS
    #
    #   Scripture references
    #
    #   Description paragraph(s)
    #
    #   #Hashtags
    #
    # Captions carry no merch blocks, "link in bio" lines or URLs: the store & book links are posted as the
    # first comment right after publishing (DEFAULT_BHRS_PINNED_COMMENT).
    # ------------------------------------------------------------------------------------------------

    @staticmethod
    def strip_promo_text(text: str) -> str:
        """Removes legacy merch blocks, store/book/link-in-bio lines and raw URLs from caption text."""
        if not text:
            return ""
        clean = re.sub(r"={10,}[\s\S]*?={10,}", "", text)
        clean = re.sub(r"={10,}", "", clean)
        clean = PROMO_LINE_RE.sub("", clean)
        clean = INLINE_PROMO_RE.sub("", clean)
        clean = MARKDOWN_LINK_RE.sub(r"\1", clean)
        clean = URL_RE.sub("", clean)
        clean = re.sub(r"\((?:Link in (?:Channel )?Bio[^)]*)\)", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"[ \t]+\n", "\n", clean)
        clean = re.sub(r"[ \t]{2,}", " ", clean)
        return re.sub(r"\n{3,}", "\n\n", clean).strip()

    @classmethod
    def caption_parts(cls, meta: Dict[str, Any], fallback_title: str = "") -> Dict[str, Any]:
        """Pulls hook, scriptures, description, hashtags and timestamps out of any of the project's metadata schemas."""
        meta = meta or {}

        def text(*keys: str) -> str:
            for key in keys:
                val = meta.get(key)
                if isinstance(val, list):
                    val = ", ".join(str(v).strip() for v in val if str(v).strip())
                if isinstance(val, str) and val.strip():
                    return val.strip()
            return ""

        title = text("title", "episode_title") or fallback_title
        hook = re.sub(r"\s*\|\s*Bible Secrets\s*#\d+\s*$", "", text("hook", "hook_text") or title, flags=re.IGNORECASE)

        body, inline_tags = strip_hashtags(cls.strip_promo_text(text("description") or text("caption")))
        first, _, rest = body.partition("\n")
        if first.strip().lower() in (title.lower(), hook.lower()):
            body = rest.strip()  # caption that repeats the title as its first line

        # Chapter lists written into the description belong only in the YouTube description
        chapter_lines = CHAPTER_LINE_RE.findall(body)
        body = CHAPTER_LINE_RE.sub("", CHAPTER_HEADER_RE.sub("", body))
        body = re.sub(r"\n{3,}", "\n\n", body).strip()

        raw_tags = meta.get("hashtags") or meta.get("tags") or []
        tags = (list(raw_tags) if isinstance(raw_tags, (list, tuple)) else split_tags(raw_tags)) + inline_tags

        raw_ts = meta.get("timestamps") or [line.strip() for line in chapter_lines]
        if isinstance(raw_ts, str):
            timestamps = raw_ts.strip()
        else:
            lines = [
                f"{ts.get('time', '')} - {ts.get('title', '')}".strip(" -") if isinstance(ts, dict) else str(ts).strip()
                for ts in raw_ts
            ]
            timestamps = "\n".join(line for line in lines if line)

        return {
            "title": title,
            "hook": hook.strip().upper(),
            "scriptures": text("scriptures", "scripture", "reference"),
            "body": body,
            "tags": tags,
            "timestamps": f"TIMESTAMPS:\n{timestamps}" if timestamps else ""
        }

    @classmethod
    def build_platform_captions(cls, meta: Dict[str, Any], fallback_title: str = "", include_timestamps: bool = True) -> Dict[str, Any]:
        """Every platform caption for one video, built from its metadata in the house format."""
        p = cls.caption_parts(meta, fallback_title)
        hook, scriptures, body, tags = p["hook"], p["scriptures"], p["body"], p["tags"]
        return {
            "hook": hook,
            "scriptures": scriptures,
            "body": body,
            "hashtags_string": normalize_tags(tags, "facebook"),
            "facebook_caption": cls.build_facebook_caption(hook, body, hashtags=tags, scriptures=scriptures),
            "youtube_description": cls.build_youtube_description(
                hook, body, timestamps=p["timestamps"] if include_timestamps else "", hashtags=tags, scriptures=scriptures
            ),
            "instagram_caption": cls.build_instagram_caption(hook, body, hashtags=tags, scriptures=scriptures),
            "tiktok_caption": cls.build_tiktok_caption(hook, body, hashtags=tags, scriptures=scriptures),
            "threads_caption": cls.build_threads_caption(hook, body, hashtags=tags, scriptures=scriptures),
            "x_post": cls.build_x_post(hook, body, hashtags=tags),
            "pinned_comment": DEFAULT_BHRS_PINNED_COMMENT
        }

    @classmethod
    def _compose_caption(
        cls,
        platform: str,
        hook: str,
        body: str,
        hashtags: Any = "",
        scriptures: str = "",
        extra: str = "",
        max_chars: Optional[int] = None
    ) -> str:
        """HOOK / scriptures / body / extra / hashtags, trimming the body (never the hook or tags) to fit max_chars."""
        tags = normalize_tags(hashtags, platform) if hashtags else ""
        body = cls.strip_promo_text(body)

        def assemble(b: str) -> str:
            parts = [(hook or "").strip(), (scriptures or "").strip(), b, (extra or "").strip(), tags]
            return "\n\n".join(x for x in parts if x).strip()

        caption = assemble(body)
        if max_chars and len(caption) > max_chars and body:
            keep = max(0, len(body) - (len(caption) - max_chars) - 3)
            caption = assemble(body[:keep].rsplit(" ", 1)[0].rstrip(" ,;:—-") + "..." if keep else "")
        if max_chars and len(caption) > max_chars:
            caption = caption[:max_chars - 3].rstrip() + "..."
        return caption

    @classmethod
    def _finalize_caption(cls, text: str, platform: str, explicit_tags: Any = None, max_chars: Optional[int] = None) -> str:
        """Cleans an existing caption: drops promo text/URLs and puts one normalized tag line at the end."""
        clean, found = strip_hashtags(cls.strip_promo_text(text))
        tags = normalize_tags(split_tags(explicit_tags) + found, platform)
        caption = f"{clean}\n\n{tags}".strip() if tags else clean
        if max_chars and len(caption) > max_chars:
            room = max(0, max_chars - len(tags) - 5)
            clean = clean[:room].rsplit(" ", 1)[0].rstrip(" ,;:—-") + "..."
            caption = f"{clean}\n\n{tags}".strip() if tags else clean
        return caption

    @classmethod
    def build_facebook_caption(
        cls,
        hook: str,
        body: str,
        merch_block: str = "",
        hashtags: Any = "",
        scriptures: str = ""
    ) -> str:
        """Facebook post in the house format (merch_block is ignored: links go in the first comment)."""
        return cls._compose_caption("facebook", hook, body, hashtags, scriptures)

    @classmethod
    def sanitize_title_for_youtube(cls, title: str) -> str:
        """
        Enforces YouTube 100-character limit on titles and platform policy rules.
        Removes invalid characters (<, >, \r, \n) that cause YouTube API 400 errors.
        Trims smoothly at word boundaries or separator if exceeding 100 chars.
        """
        if not title:
            return ""
        # Remove forbidden YouTube characters (< and > are blocked by YouTube API to prevent XSS)
        clean = title.replace("<", "").replace(">", "").replace("\r", " ").replace("\n", " ")
        clean = re.sub(r'\s+', ' ', clean).strip()

        if len(clean) <= 100:
            return clean

        # If suffix like ' | Bible Secrets #78' pushed it over, try trimming suffix
        if " | " in clean:
            prefix, suffix = clean.rsplit(" | ", 1)
            if len(prefix) <= 100:
                return prefix.strip()

        # Otherwise truncate at last word before 97 chars
        truncated = clean[:97].rsplit(" ", 1)[0].rstrip(" -–—,:") + "..."
        return truncated if len(truncated) <= 100 else clean[:100]

    @classmethod
    def sanitize_hashtags_for_platform(
        cls,
        hashtags: Any,
        platform: str = "instagram",
        max_tags: Optional[int] = None
    ) -> str:
        """
        Filters out sensitive/shadowban-trigger tags (e.g. #Lucifer, #FallOfSatan, #Demons, #SpiritualWarfare)
        and caps the count at the platform limit (see core.hashtags.PLATFORM_HASHTAG_LIMITS).
        """
        return normalize_tags(hashtags, platform, max_tags)

    @classmethod
    def sanitize_urls_for_youtube(
        cls,
        text: str,
        hashtags: Any = None,
        include_ai_disclosure: bool = False
    ) -> str:
        """
        YouTube description compliance sanitization:
        - Strips raw URLs, URL shorteners, and merch blocks (external links go in pinned comment).
        - Strips illegal YouTube characters ('<' and '>') that cause API 400 errors or XSS warnings.
        - Enforces 5,000 character YouTube description ceiling.
        - Caps hashtags at YouTube platform limits.
        - Optionally includes the official altered/synthetic content disclosure note.
        """
        if not text:
            return ""
        sanitized = cls._finalize_caption(text.replace("<", "").replace(">", ""), "youtube", hashtags, max_chars=5000)
        if include_ai_disclosure and DEFAULT_YT_AI_DISCLOSURE not in sanitized:
            clean, tags = strip_hashtags(sanitized)
            tags_str = normalize_tags(tags, "youtube") if tags else ""
            disclosure_block = f"{clean}\n\n{DEFAULT_YT_AI_DISCLOSURE}".strip()
            return f"{disclosure_block}\n\n{tags_str}".strip() if tags_str else disclosure_block
        return sanitized

    @classmethod
    def apply_youtube_compliance(cls, description: str, include_ai_disclosure: bool = True) -> str:
        """
        Convenience method applying full YouTube compliance to video descriptions:
        strips all unauthorized external URLs, strips invalid characters, and appends
        the standard altered/synthetic content disclosure.
        """
        return cls.sanitize_urls_for_youtube(description, include_ai_disclosure=include_ai_disclosure)

    @classmethod
    def sanitize_urls_for_instagram(cls, text: str, hashtags: Any = None) -> str:
        """Instagram caption: no URLs or merch blocks, safe hashtags capped at the Instagram limit, 2,200 chars."""
        if not text:
            return ""
        return cls._finalize_caption(text, "instagram", hashtags, max_chars=2200)

    @classmethod
    def sanitize_caption_for_facebook(
        cls,
        text: str,
        hook: str = "",
        body: str = "",
        hashtags: Any = ""
    ) -> str:
        """Facebook caption: no URLs or merch blocks (links go in the first comment), explicit hashtags first."""
        if not text and not hook and not body:
            return ""
        return cls._finalize_caption(text or cls.build_facebook_caption(hook, body), "facebook", hashtags)

    @classmethod
    def sanitize_caption_for_threads(
        cls,
        caption: str,
        hook: str = "",
        body: str = "",
        hashtags: Any = ""
    ) -> str:
        """Threads: 500 characters max and one safe hashtag (Threads turns only one tag per post into a topic)."""
        if not caption and not hook and not body:
            return ""
        cleaned = cls._finalize_caption(caption or "", "threads", hashtags)
        if caption and len(cleaned) <= 500:
            return cleaned

        # Too long: rebuild from the hook + body so the hook and tag survive the cut
        text, found = strip_hashtags(cls.strip_promo_text(caption or ""))
        first, _, rest = text.partition("\n")
        return cls.build_threads_caption(hook or first, body or rest, hashtags=split_tags(hashtags) + found)

    @classmethod
    def sanitize_caption_for_tiktok(
        cls,
        caption: str,
        hook: str = "",
        body: str = "",
        hashtags: Any = ""
    ) -> str:
        """TikTok: softens trigger words, no URLs or merch blocks, safe hashtags, 2,200 characters max."""
        if not caption and not hook and not body:
            return ""
        return cls._finalize_caption(cls._soften_for_tiktok(caption or ""), "tiktok", hashtags, max_chars=2200)

    @staticmethod
    def _soften_for_tiktok(text: str) -> str:
        text = re.sub(r'\bmurder\b', 'violence', text, flags=re.IGNORECASE)
        text = re.sub(r'\bslaughter\b', 'destruction', text, flags=re.IGNORECASE)
        return re.sub(r'\bsuicide\b', 'tragedy', text, flags=re.IGNORECASE)

    @classmethod
    def sanitize_post_for_x(
        cls,
        post: str,
        hook: str = "",
        body: str = "",
        url: str = "",
        hashtags: Any = ""
    ) -> str:
        """
        Enforces X (Twitter) standard account 280-character limit.
        If given a full script, intelligently composes hook + punchy takeaway + 2 safe hashtags.
        """
        if not post and not hook and not body:
            return ""

        # Explicit tags first, then the ones found in the post
        safe_tags = normalize_tags(split_tags(hashtags) + find_hashtags(post or ""), "x")

        # If already <= 280 characters and contains no huge merch block
        if post and "====" not in post and "http://" not in post and "https://" not in post:
            text, _ = strip_hashtags(post.strip())
            candidate = f"{text}\n\n{safe_tags}".strip() if safe_tags else text
            if len(candidate) <= 280:
                return candidate

        # Parse hook and body if not provided
        if not hook and post:
            lines = [l.strip() for l in post.split("\n") if l.strip()]
            if lines:
                hook = lines[0]

        if not body and post:
            clean_text = post
            if hook and clean_text.startswith(hook):
                clean_text = clean_text[len(hook):].strip()
            clean_text = re.sub(r"={20,}[\s\S]*?={20,}", "", clean_text).strip()
            clean_text, _ = strip_hashtags(clean_text)
            body = clean_text

        return cls.build_x_post(hook, body, url=url, hashtags=safe_tags)

    @classmethod
    def build_youtube_description(
        cls,
        hook: str,
        body: str,
        timestamps: str = "",
        merch_block: str = "",
        hashtags: Any = "",
        scriptures: str = "",
        include_ai_disclosure: bool = False
    ) -> str:
        """YouTube description (Shorts & long-form) in the house format, with chapters for long-form. No URLs."""
        caption = cls._compose_caption("youtube", hook, body, hashtags, scriptures, extra=timestamps, max_chars=5000)
        clean = caption.replace("<", "").replace(">", "")
        if include_ai_disclosure and DEFAULT_YT_AI_DISCLOSURE not in clean:
            body_part, tags = strip_hashtags(clean)
            tags_str = normalize_tags(tags, "youtube") if tags else ""
            disclosure_block = f"{body_part}\n\n{DEFAULT_YT_AI_DISCLOSURE}".strip()
            return f"{disclosure_block}\n\n{tags_str}".strip() if tags_str else disclosure_block
        return clean

    @classmethod
    def build_instagram_caption(
        cls,
        hook: str,
        body: str,
        merch_block: str = "",
        hashtags: Any = "",
        scriptures: str = ""
    ) -> str:
        """Instagram caption in the house format (2,200 characters max, safe hashtags)."""
        return cls._compose_caption("instagram", hook, body, hashtags, scriptures, max_chars=2200)

    @classmethod
    def build_tiktok_caption(
        cls,
        hook: str,
        body: str,
        hashtags: Any = "",
        scriptures: str = ""
    ) -> str:
        """TikTok caption in the house format (2,200 characters max, trigger words softened)."""
        return cls._compose_caption("tiktok", hook, cls._soften_for_tiktok(body or ""), hashtags, scriptures, max_chars=2200)

    @classmethod
    def build_threads_caption(
        cls,
        hook: str,
        body: str,
        hashtags: Any = "",
        scriptures: str = ""
    ) -> str:
        """Threads post in the house format, trimmed to 500 characters."""
        flat_body = re.sub(r"\s*\n\s*", " ", body or "").strip()
        return cls._compose_caption("threads", hook, flat_body, hashtags, scriptures, max_chars=500)

    @classmethod
    def build_x_post(
        cls,
        hook: str,
        body: str,
        url: str = "",
        hashtags: Any = ""
    ) -> str:
        """
        Builds X (Twitter) post strictly <= 280 characters for standard accounts.
        Hook + core insight + optional link + top hashtags.
        """
        ht_str = normalize_tags(hashtags, "x")
        clean_url = (url or "").strip()

        reserved = (len(clean_url) + 2 if clean_url else 0) + (len(ht_str) + 2 if ht_str else 0) + 4
        budget = max(40, 280 - reserved)

        clean_hook = (hook or "").strip()
        clean_body = (body or "").strip()

        # Build candidate text fitting within budget
        if clean_hook and clean_body:
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean_body) if s.strip()]
            candidate = clean_hook
            for s in sentences:
                test_cand = f"{candidate}\n\n{s}"
                if len(test_cand) <= budget:
                    candidate = test_cand
                else:
                    if candidate == clean_hook:
                        avail = budget - len(clean_hook) - 4
                        if avail > 20:
                            short_s = s[:avail].rsplit(" ", 1)[0].rstrip(" -–—,:;") + "..."
                            candidate = f"{clean_hook}\n\n{short_s}"
                    break
        elif clean_hook:
            candidate = clean_hook if len(clean_hook) <= budget else clean_hook[:budget - 3].rsplit(" ", 1)[0] + "..."
        else:
            candidate = clean_body if len(clean_body) <= budget else clean_body[:budget - 3].rsplit(" ", 1)[0] + "..."

        parts = [candidate]
        if clean_url:
            parts.append(clean_url)
        if ht_str:
            parts.append(ht_str)
        res = "\n\n".join(parts).strip()
        while len(res) > 280 and len(candidate) > 20:
            candidate = candidate[:-5].rsplit(" ", 1)[0].rstrip(" -–—,:;") + "..."
            parts = [candidate]
            if clean_url:
                parts.append(clean_url)
            if ht_str:
                parts.append(ht_str)
            res = "\n\n".join(parts).strip()
        return res

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
        """Builds the house-format caption for one platform."""
        p_low = platform.lower()
        if p_low == "youtube":
            return cls.build_youtube_description(hook, body, timestamps, hashtags=hashtags)
        elif p_low == "instagram":
            return cls.build_instagram_caption(hook, body, hashtags=hashtags)
        elif p_low == "tiktok":
            return cls.build_tiktok_caption(hook, body, hashtags)
        elif p_low == "threads":
            return cls.build_threads_caption(hook, body, hashtags)
        elif p_low in ("x", "twitter"):
            return cls.build_x_post(hook, body, hashtags=hashtags)
        return cls.build_facebook_caption(hook, body, hashtags=hashtags)

    @staticmethod
    def parse_metadata_txt(content: str) -> Dict[str, Any]:
        """
        Parses the older metadata.txt layout ('HOOK:', 'DESCRIPTION:', 'HASHTAGS:', 'FACEBOOK CAPTION:', ...)
        into the same keys metadata.json uses. Merch blocks and EDITING notes are skipped.
        """
        headers = {
            "title": r"title", "hook": r"hook", "scriptures": r"scriptures?|references?",
            "thumbnail_text": r"thumbnail(?:\s+text)?", "description": r"description",
            "pinned_comment": r"pinned(?:\s+comment)?", "hashtags": r"hashtags?", "tags": r"tags",
            "youtube_shorts_title": r"youtube\s+shorts\s+title", "youtube_description": r"youtube\s+description",
            "facebook_caption": r"facebook\s+caption", "instagram_caption": r"instagram\s+caption",
            "threads_caption": r"threads\s+caption", "tiktok_caption": r"tiktok\s+caption", "x_post": r"x\s+post",
            "editing": r"editing", "timestamps": r"timestamps"
        }
        header_res = [(key, re.compile(rf"^(?:#\s*)?(?:{pattern})\s*:\s*(.*)$", re.IGNORECASE)) for key, pattern in headers.items()]
        sections: Dict[str, List[str]] = {}
        current = None
        lines = (content or "").splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            clean = line.strip()
            # Merch & books block between '=====' rulers
            if clean.startswith("===") and i + 1 < len(lines) and "merch" in lines[i + 1].lower():
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("==="):
                    i += 1
                i += 1
                current = None
                continue
            match = next(((key, m) for key, rx in header_res for m in [rx.match(clean)] if m), None)
            if match:
                current = match[0]
                sections.setdefault(current, [])
                if match[1].group(1).strip():
                    sections[current].append(match[1].group(1).strip())
            elif current and current != "editing":
                sections[current].append(line.rstrip())
            elif not current and clean and not clean.startswith(("===", "EPISODE")) and "description" not in sections:
                sections["description"] = [clean]
            i += 1

        def joined(key: str) -> str:
            return re.sub(r"\n{3,}", "\n\n", "\n".join(sections.get(key, []))).strip().strip('"').strip()

        meta: Dict[str, Any] = {key: joined(key) for key in sections if key not in ("editing", "hashtags", "tags")}
        tag_text = " ".join(sections.get("hashtags", []) + sections.get("tags", []))
        meta["hashtags"] = find_hashtags(tag_text) or [t.strip().lstrip("#") for t in tag_text.split(",") if t.strip()]
        meta["title"] = meta.get("title") or meta.get("youtube_shorts_title", "")
        meta["description"] = SocialDispatcher.strip_promo_text(meta.get("description", ""))
        if not meta.get("description"):
            # Older reels keep the narrative only inside the platform captions
            meta["description"] = SocialDispatcher.strip_promo_text(
                meta.get("facebook_caption") or meta.get("instagram_caption") or meta.get("tiktok_caption") or ""
            )
        return meta

    def extract_metadata_for_video(self, project_path: Any, video_rel_path: str) -> Dict[str, Any]:
        """Reads the video's metadata.json (or older metadata.txt) and builds every platform caption in the house format."""
        project_path = Path(project_path)
        base_name = Path(video_rel_path).stem.replace("_", " ").title()
        meta: Dict[str, Any] = {}
        from_json = False

        meta_file = asset_manager.find_or_create_metadata_file(str(project_path), video_rel_path)
        if meta_file and meta_file.exists() and meta_file.is_file():
            try:
                content = meta_file.read_text(encoding="utf-8")
            except Exception:
                content = meta_file.read_text(encoding="cp1252", errors="replace")
            if meta_file.suffix.lower() == ".json":
                try:
                    jdata = json.loads(content)
                    if isinstance(jdata, dict):
                        meta, from_json = jdata, True
                except Exception:
                    pass
            else:
                meta = self.parse_metadata_txt(content)

        title = str(meta.get("title") or meta.get("episode_title") or base_name).strip()
        captions = self.build_platform_captions(meta, fallback_title=title, include_timestamps=True)

        # YouTube tags field: the metadata's tags, else the hashtag words
        raw_tags = meta.get("tags")
        if isinstance(raw_tags, str):
            raw_tags = [t for t in raw_tags.split(",")]
        tags = [str(t).strip().lstrip("#") for t in (raw_tags or []) if str(t).strip()]
        if not tags:
            tags = [t.lstrip("#") for t in captions["hashtags_string"].split()]

        # The links comment posted after publishing: metadata.json may override it; legacy '=====' blocks and
        # metadata.txt comments are replaced by the house comment
        stored_comment = str(meta.get("pinned_comment") or "").strip() if from_json else ""
        pinned_comment = stored_comment if stored_comment and "=====" not in stored_comment else DEFAULT_BHRS_PINNED_COMMENT

        thumb_file = self.find_custom_thumbnail(project_path, video_rel_path)
        has_custom_thumb = bool(thumb_file and thumb_file.exists())
        hashtags_string = captions["hashtags_string"]

        return {
            "title": title,
            "hook": captions["hook"],
            "scriptures": captions["scriptures"],
            "description": captions["facebook_caption"],
            "youtube_description": captions["youtube_description"],
            "tags": tags,
            "hashtags_string": hashtags_string,
            "caption": f"{captions['hook'] or title}\n\n{hashtags_string}".strip(),
            "thumbnail_text": str(meta.get("thumbnail_text") or "").strip(),
            "merch_block": "",
            "pinned_comment": pinned_comment,
            "youtube_shorts_title": self.sanitize_title_for_youtube(str(meta.get("youtube_shorts_title") or title)),
            "facebook_caption": captions["facebook_caption"],
            "instagram_caption": captions["instagram_caption"],
            "threads_caption": captions["threads_caption"],
            "tiktok_caption": captions["tiktok_caption"],
            "x_post": captions["x_post"],
            "has_custom_thumbnail": has_custom_thumb,
            "thumbnail_filename": thumb_file.name if has_custom_thumb else "",
            "thumbnail_rel_path": str(thumb_file.relative_to(project_path)).replace("\\", "/") if has_custom_thumb else "",
            "thumbnail_abs_path": str(thumb_file.resolve()) if has_custom_thumb else "",
            "thumbnail_docker_path": self.get_docker_path(thumb_file) if has_custom_thumb else ""
        }

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

    SUPPORTED_PLATFORMS = ("youtube", "facebook", "instagram", "threads", "tiktok", "x")

    @staticmethod
    def classify_video_format(resolution: Optional[str], duration_sec: float, rel_path: str) -> Dict[str, str]:
        """
        Classifies a video as "story", "short" or "long_form".
        The probed aspect ratio decides first: vertical -> short, landscape -> long_form,
        square -> short if <= 180s. Path hints are only used when the resolution is unknown.
        Videos under a 'stories' folder are stories unless they are landscape.
        """
        parts = [x.lower() for x in str(rel_path).replace("\\", "/").split("/")]
        in_stories = "stories" in parts[:-1]
        name = parts[-1] if parts else ""
        reel_hint = "reels" in parts[:-1] or "shorts" in parts[:-1] or "reel" in name or "short" in name

        w = h = 0
        try:
            w, h = map(int, str(resolution or "").lower().split("x"))
        except Exception:
            pass

        if w > 0 and h > 0:
            if h > w:
                aspect_ratio, vertical_ok = "9:16", True
            elif h == w:
                aspect_ratio, vertical_ok = "1:1", 0 < duration_sec <= 180
            else:
                aspect_ratio, vertical_ok = "16:9", False
        else:
            aspect_ratio = "unknown"
            vertical_ok = in_stories or reel_hint or (0 < duration_sec <= 180)

        if not vertical_ok:
            video_format = "long_form"
        elif in_stories:
            video_format = "story"
        else:
            video_format = "short"
        return {"format": video_format, "aspect_ratio": aspect_ratio}

    @classmethod
    def get_platform_routing(cls, video_format: str, duration_sec: float, cfg: Dict[str, Any], duration_str: str = "") -> Dict[str, Dict[str, Any]]:
        """Per-platform label + eligibility for a video format. Disabled platforms in project settings are ineligible."""
        dur = duration_str or f"{int(duration_sec // 60)}m {int(duration_sec % 60)}s"
        short = video_format in ("short", "story")
        story = video_format == "story"
        routes = {
            "youtube": {"label": "YouTube Shorts" if short else "YouTube Standard", "eligible": True, "reason": ""},
            "facebook": {"label": "Facebook Story" if story else ("Facebook Reels" if short else "Facebook Long Video"), "eligible": True, "reason": ""},
            "instagram": {"label": "Instagram Story" if story else "Instagram Reels", "eligible": True, "reason": ""},
            "threads": {"label": "Threads Video", "eligible": True, "reason": ""},
            "tiktok": {"label": "TikTok" if short else "TikTok Long Video", "eligible": True, "reason": ""},
            "x": {"label": "X (not supported yet)", "eligible": False, "reason": "X posting is not implemented yet (no X API uploader)."},
        }
        if not short:
            routes["instagram"].update(eligible=False, reason="Instagram only accepts vertical Reels/Stories; this is a landscape long-form video.")
            routes["threads"].update(eligible=False, reason="Threads is limited to short vertical videos.")
        if story and duration_sec > 60:
            routes["instagram"].update(eligible=False, reason=f"Instagram Stories are limited to 60s (video is {dur}).")
        elif short and duration_sec > 900:
            routes["instagram"].update(eligible=False, reason=f"Instagram Reels are limited to 15 minutes (video is {dur}).")
        if short and duration_sec > 300:
            routes["threads"].update(eligible=False, reason=f"Threads videos are limited to 5 minutes (video is {dur}).")
        if duration_sec > 1800:
            routes["tiktok"].update(label="TikTok (>30m limit)", eligible=False, reason=f"TikTok is limited to 30 minutes (video is {dur}).")
        for p, route in routes.items():
            if route["eligible"] and not cfg.get(p, {}).get("enabled", True):
                route.update(eligible=False, reason=f"{route['label']} is disabled in this project's social settings.")
        return routes

    def compose_post_texts(
        self,
        project_path: Path,
        video_rel_path: str,
        custom_title: Optional[str] = None,
        custom_desc: Optional[str] = None,
        custom_tags: Optional[List[str]] = None,
        platform_captions: Optional[Dict[str, str]] = None,
        custom_pinned_comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Title, per-platform captions and the links comment exactly as a post sends them. Used by publish_video and by
        the Business Suite checklist, so a caption pasted into Business Suite matches what KCT Studio would post.
        """
        project_path = Path(project_path)
        meta = self.extract_metadata_for_video(project_path, video_rel_path)

        vid_stem_title = (project_path / video_rel_path).stem.replace("_", " ").title()
        if custom_title and custom_title.strip() and custom_title.strip() != vid_stem_title:
            title = custom_title
        else:
            title = meta.get("title") or custom_title or vid_stem_title
        raw_title = title

        tags = custom_tags if custom_tags is not None else meta["tags"]
        hashtags_string = meta.get("hashtags_string") or " ".join([f"#{t}" for t in tags])

        if custom_desc and not custom_desc.startswith("Generated by AI Content Generation Pipeline"):
            desc = custom_desc
            fb_desc = custom_desc
            ig_desc = custom_desc
            th_desc = custom_desc if len(custom_desc) <= 500 else self.build_threads_caption(title, custom_desc, hashtags_string)
            yt_desc = custom_desc
            tt_desc = custom_desc if len(custom_desc) <= 2000 else self.build_tiktok_caption(title, custom_desc, hashtags_string)
            x_desc = self.build_x_post(title, custom_desc, hashtags=hashtags_string)
        else:
            desc = meta.get("description") or ""
            fb_desc = meta.get("facebook_caption") or desc
            ig_desc = meta.get("instagram_caption") or desc
            th_desc = meta.get("threads_caption") or self.build_threads_caption(title, desc, hashtags=hashtags_string)
            yt_desc = meta.get("youtube_description") or desc
            tt_desc = meta.get("tiktok_caption") or desc
            x_desc = meta.get("x_post") or self.build_x_post(title, desc, hashtags=hashtags_string)

        # Allow granular per-platform caption overrides if explicitly provided
        if platform_captions and isinstance(platform_captions, dict):
            if platform_captions.get("facebook"):
                fb_desc = platform_captions["facebook"]
            if platform_captions.get("youtube"):
                yt_desc = platform_captions["youtube"]
            if platform_captions.get("instagram"):
                ig_desc = platform_captions["instagram"]
            if platform_captions.get("threads"):
                th_desc = platform_captions["threads"]
            if platform_captions.get("tiktok"):
                tt_desc = platform_captions["tiktok"]
            if platform_captions.get("x"):
                x_desc = platform_captions["x"]

        # Universal Policy & Compliance Sanitizer Guard:
        # Ensures no platform receives policy-violating text (URLs, merch blocks, length, sensitive tags).
        # Hashtags edited in the publish modal come first, then the caption's own.
        explicit_tags = custom_tags or []
        yt_desc = self.sanitize_urls_for_youtube(yt_desc, hashtags=explicit_tags)
        title = self.sanitize_title_for_youtube(title)
        fb_desc = self.sanitize_caption_for_facebook(fb_desc, hook=title, body=desc, hashtags=explicit_tags)
        ig_desc = self.sanitize_urls_for_instagram(ig_desc, hashtags=explicit_tags)
        th_desc = self.sanitize_caption_for_threads(th_desc, title, desc, hashtags=explicit_tags)
        tt_desc = self.sanitize_caption_for_tiktok(tt_desc, hashtags=explicit_tags)
        x_desc = self.sanitize_post_for_x(x_desc)

        effective_pinned_comment = custom_pinned_comment or meta.get("pinned_comment") or DEFAULT_BHRS_PINNED_COMMENT
        # Reels point to the week's full documentary: its YouTube link leads the comment once it is live
        documentary_url = live_documentary_url(project_path, video_rel_path) if is_reel(video_rel_path) else None
        effective_pinned_comment = with_documentary_link(effective_pinned_comment, documentary_url)

        return {
            "meta": meta,
            "raw_title": raw_title,
            "title": title,
            "desc": desc,
            "tags": tags,
            "captions": {"youtube": yt_desc, "facebook": fb_desc, "instagram": ig_desc,
                         "threads": th_desc, "tiktok": tt_desc, "x": x_desc},
            "pinned_comment": effective_pinned_comment,
            "documentary_url": documentary_url,
        }

    async def publish_video(
        self,
        project_path_str: str,
        video_rel_path: str,
        platforms: Optional[List[str]] = None,
        custom_title: Optional[str] = None,
        custom_desc: Optional[str] = None,
        custom_tags: Optional[List[str]] = None,
        force_republish: bool = False,
        scheduled_datetime_iso: Optional[str] = None,
        publish_mode: str = "immediate",
        platform_captions: Optional[Dict[str, str]] = None,
        custom_pinned_comment: Optional[str] = None
    ) -> Dict[str, Any]:
        project_path = Path(project_path_str)
        video_abs_path = project_path / video_rel_path
        if not video_abs_path.exists():
            return {"success": False, "error": f"Video file not found: {video_abs_path}"}

        cfg = config_manager.get_project_social_config(project_path_str)
        dry_run = cfg.get("dry_run", True)

        # Parse scheduled_datetime_iso into UTC ISO 8601 string and UNIX timestamp
        import datetime
        scheduled_timestamp = None
        publish_at_iso = None
        if scheduled_datetime_iso:
            try:
                clean_dt_str = scheduled_datetime_iso.strip()
                if clean_dt_str.endswith("Z"):
                    clean_dt_str = clean_dt_str[:-1] + "+00:00"
                dt_obj = datetime.datetime.fromisoformat(clean_dt_str)
                if dt_obj.tzinfo is None:
                    dt_obj = dt_obj.astimezone()
                dt_utc = dt_obj.astimezone(datetime.timezone.utc)
                publish_at_iso = dt_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
                scheduled_timestamp = int(dt_utc.timestamp())
            except Exception as e:
                import logging
                logging.warning(f"[SocialDispatcher] Failed to parse scheduled_datetime_iso '{scheduled_datetime_iso}': {e}")

        all_platforms = list(self.SUPPORTED_PLATFORMS)
        target_platforms = platforms if platforms else [p for p in all_platforms if cfg.get(p, {}).get("enabled", True)]

        # Check existing publication records in asset manager
        rec = asset_manager.get_asset_record(video_rel_path)
        existing_published = rec.get("published", {})
        already_published_platforms = [
            p for p, pdata in existing_published.items() 
            if pdata.get("status") in ("published", "scheduled")
        ]

        already_published_results = {}
        if not force_republish:
            for p in target_platforms:
                if p in already_published_platforms:
                    pdata = existing_published.get(p, {})
                    pdetails = pdata.get("details", {})
                    purl = pdetails.get("url") or pdata.get("url") or ""
                    pid = pdetails.get("id") or pdata.get("id") or ""
                    already_published_results[p] = {
                        "status": "published",
                        "platform": p.capitalize(),
                        "already_published": True,
                        "url": purl,
                        "id": pid,
                        "message": f"Already published on {p.capitalize()} (skipped duplicate upload)."
                    }
            unposted = [p for p in target_platforms if p not in already_published_platforms]
            if unposted:
                # Target only unposted platforms
                target_platforms = unposted
                is_already_posted = False
            else:
                # All selected platforms are already published!
                is_already_posted = True
                return {
                    "success": True,
                    "already_posted": True,
                    "skipped": True,
                    "title": custom_title or video_abs_path.stem.replace("_", " ").title(),
                    "video": video_abs_path.name,
                    "message": f"All target platforms ({', '.join(platforms or target_platforms)}) have already been published. Dispatch skipped to prevent duplicates.",
                    "platforms": already_published_results
                }
        else:
            is_already_posted = False

        texts = self.compose_post_texts(project_path, video_rel_path, custom_title=custom_title, custom_desc=custom_desc,
                                        custom_tags=custom_tags, platform_captions=platform_captions,
                                        custom_pinned_comment=custom_pinned_comment)
        meta = texts["meta"]
        title = texts["raw_title"]
        tags = texts["tags"]

        # Video media specifications
        stat = video_abs_path.stat()
        media_info = asset_manager.get_media_info(video_abs_path)
        duration_str = media_info.get("duration") or "N/A"
        duration_sec = media_info.get("duration_sec") or 0.0
        fmt = self.classify_video_format(media_info.get("resolution"), duration_sec, video_rel_path)
        video_format = fmt["format"]
        aspect_ratio = fmt["aspect_ratio"]
        is_short_or_reel = video_format in ("short", "story")
        is_story = video_format == "story"

        # Single routing rule shared with the publish modal (/api/social/format)
        routing = self.get_platform_routing(video_format, duration_sec, cfg, duration_str)
        format_skipped_platforms = {}
        for p in list(target_platforms):
            route = routing.get(p) or {"eligible": False, "label": p, "reason": f"Unsupported platform '{p}'."}
            skip_reason = None if route["eligible"] else route["reason"]
            if not skip_reason and is_story and scheduled_timestamp and p in ("facebook", "instagram"):
                skip_reason = "Stories can't be cloud-scheduled; they are published when the post is due."
            if skip_reason:
                import logging
                logging.info(f"[SocialDispatcher] Skipping {p} for {video_rel_path}: {skip_reason}")
                target_platforms = [t for t in target_platforms if t != p]
                format_skipped_platforms[p] = {
                    "status": "skipped",
                    "platform": route["label"],
                    "message": f"Skipped: {skip_reason}"
                }

        if not target_platforms and format_skipped_platforms:
            return {
                "success": True,
                "already_posted": False,
                "skipped": True,
                "title": title,
                "video": video_abs_path.name,
                "message": f"Video ({duration_str} {aspect_ratio}) was skipped on selected platforms due to format/duration limits.",
                "platforms": format_skipped_platforms
            }

        thumb_abs = meta.get("thumbnail_abs_path", "")

        title = texts["title"]
        desc = texts["desc"]
        captions = texts["captions"]
        yt_desc, fb_desc, ig_desc = captions["youtube"], captions["facebook"], captions["instagram"]
        th_desc, tt_desc, x_desc = captions["threads"], captions["tiktok"], captions["x"]
        effective_pinned_comment = texts["pinned_comment"]
        documentary_url = texts["documentary_url"]

        results = {}

        # Individual Platform Handlers (Direct Native Upload)
        for plat in target_platforms:
            plat_cfg = cfg.get(plat, {})
            if dry_run:
                # Simulated dispatch: never reported as "published" so nothing records it as a real post
                res = {
                    "status": "simulated",
                    "simulated": True,
                    "mode": "DRY_RUN (Simulated)",
                    "message": f"Simulated posting to {plat.upper()} with title '{title}'",
                    "video": video_abs_path.name,
                    "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            else:
                # Live direct native dispatch handlers (blocking HTTP/uploads run off the event loop)
                res = await asyncio.to_thread(
                    self._dispatch_to_platform,
                    platform=plat,
                    config=plat_cfg,
                    video_path=video_abs_path,
                    title=title,
                    description=(
                        yt_desc if plat == "youtube"
                        else (fb_desc if plat == "facebook"
                        else (ig_desc if plat == "instagram"
                        else (th_desc if plat == "threads"
                        else (x_desc if plat == "x"
                        else (tt_desc if plat == "tiktok" else desc)))))
                    ),
                    tags=tags,
                    scheduled_timestamp=scheduled_timestamp,
                    publish_at_iso=publish_at_iso,
                    is_short=is_short_or_reel,
                    is_story=is_story,
                    thumbnail_path=Path(thumb_abs) if thumb_abs else None,
                    pinned_comment=effective_pinned_comment
                )

            results[plat] = res

        # Check if newly attempted platforms succeeded
        newly_published = [p for p in target_platforms if results.get(p, {}).get("status") == "published"]

        # Merge already-published and format-skipped platforms into results for full visibility in the UI modal
        results.update(already_published_results)
        results.update(format_skipped_platforms)

        if not dry_run and not newly_published and target_platforms:
            err_msg = next((results[p].get("error") for p in target_platforms if results.get(p, {}).get("error")), "Social media dispatch failed.")
            return {
                "success": False,
                "error": err_msg,
                "dry_run": dry_run,
                "title": title,
                "video": video_abs_path.name,
                "platforms": results
            }

        # Record real uploads only: a dry run must never touch publish history
        if not dry_run:
            for plat in newly_published:
                details = results[plat]
                if isinstance(details, dict) and plat in ("youtube", "facebook", "instagram"):
                    details["comment_text"] = effective_pinned_comment
                    if documentary_url:
                        details["documentary_link"] = documentary_url
                asset_manager.mark_published(video_rel_path, plat, details)
            if newly_published:
                export_week_links(project_path, week_of(video_rel_path))

        # Send native desktop notification only on verified (or explicitly simulated) dispatch
        done_plats = target_platforms if dry_run else newly_published
        if done_plats:
            try:
                from core.notifier import notify_desktop
                plat_names = ", ".join(p.upper() for p in done_plats)
                if publish_at_iso or scheduled_timestamp:
                    action_word = "Scheduled in Cloud"
                else:
                    action_word = "Reposted" if force_republish else "Published"
                mode_prefix = "[Simulated] " if dry_run else ""
                notify_desktop(
                    f"{mode_prefix}Video {action_word}: {plat_names}",
                    f"Dry run for '{title}': nothing was uploaded to {plat_names}." if dry_run
                    else f"'{title}' was {action_word.lower()} to {plat_names} successfully."
                )
            except Exception:
                pass

        response = {
            "success": True,
            "dry_run": dry_run,
            "title": title,
            "video": video_abs_path.name,
            "platforms": results
        }
        if not is_story and not thumb_abs:
            response["thumbnail_warning"] = (
                "No thumbnail image was found next to this video, so each platform chose its own frame. "
                "Add thumbnail.jpg to the video's folder (reels: the thumbnail button in the Generator) and repost if needed."
            )
            for plat in newly_published:
                if isinstance(results.get(plat), dict):
                    results[plat]["message"] = f"{results[plat].get('message', '')} (no thumbnail image found)".strip()
        if dry_run:
            response["message"] = "Dry run: nothing was uploaded and publish history was not changed."
        return response

    MAX_COMMENT_ATTEMPTS = 8

    async def post_due_comments(self) -> int:
        """
        Posts the queued links comment on scheduled YouTube/Facebook posts once they have gone live.
        Called by the scheduler loop; failed attempts back off (1, 2, 3... minutes) up to MAX_COMMENT_ATTEMPTS.
        Record bookkeeping stays on the event loop thread; only the API call runs in a worker thread.
        """
        now = time.time()
        due = [
            (rel_path, platform, details) for rel_path, platform, details in asset_manager.iter_published()
            if details.get("pending_comment") and details.get("id")
            and float(details.get("comment_due_at") or 0) <= now
            and int(details.get("comment_attempts") or 0) < self.MAX_COMMENT_ATTEMPTS
        ]
        posted = 0
        project_path = Path(config_manager.get_active_project() or ".")
        for rel_path, platform, details in due:
            text = details["pending_comment"]
            doc_url = live_documentary_url(project_path, rel_path) if is_reel(rel_path) else None
            text = with_documentary_link(text, doc_url)
            res = await asyncio.to_thread(self._post_comment, platform, str(details["id"]), text)
            # Re-read the record: the catalog may have been reloaded while the API call ran
            entry = asset_manager.get_asset_record(rel_path).get("published", {}).get(platform) or {}
            if isinstance(entry.get("details"), dict):
                details = entry["details"]
            attempts = int(details.get("comment_attempts") or 0) + 1
            details["comment_attempts"] = attempts
            if res.get("success"):
                posted += 1
                details["comment_posted"] = True
                details["comment_id"] = res.get("id")
                details["comment_text"] = text
                if doc_url:
                    details["documentary_link"] = doc_url
                details.pop("pending_comment", None)
                details.pop("comment_error", None)
            else:
                details["comment_error"] = res.get("error")
                details["comment_due_at"] = now + 60 * attempts
        if due:
            asset_manager.save()
        return posted

    MAX_DOC_LINK_ATTEMPTS = 5

    async def update_documentary_links(self) -> int:
        """
        Once a week's documentary is live on YouTube, adds its link to the links comment of that week's reels that were
        posted before it (YouTube and Facebook comments are edited; Instagram comments can't be, so they are left).
        Called by the scheduler loop; does nothing (and calls no API) when every reel already has its link.
        """
        project_path = Path(config_manager.get_active_project() or ".")
        now = time.time()
        todo = []
        for rel_path, platform, details in asset_manager.iter_published():
            if platform not in ("youtube", "facebook") or not is_reel(rel_path) or details.get("documentary_link"):
                continue
            if details.get("pending_comment") or not details.get("id"):
                continue  # still queued: post_due_comments adds the link when it posts
            if "comment_text" not in details:
                continue  # posted before reels carried documentary links: older posts are left as they are
            if int(details.get("doc_link_attempts") or 0) >= self.MAX_DOC_LINK_ATTEMPTS:
                continue
            if float(details.get("doc_link_retry_at") or 0) > now:
                continue
            doc_url = live_documentary_url(project_path, rel_path)
            if doc_url:
                todo.append((rel_path, platform, details, doc_url))
        weeks = set()
        for rel_path, platform, details, doc_url in todo:
            text = with_documentary_link(details.get("comment_text") or DEFAULT_BHRS_PINNED_COMMENT, doc_url)
            comment_id = comment_id_of(details)
            if comment_id:
                res = await asyncio.to_thread(self._update_comment, platform, str(comment_id), text)
            else:
                res = await asyncio.to_thread(self._post_comment, platform, str(details["id"]), text)
            entry = asset_manager.get_asset_record(rel_path).get("published", {}).get(platform) or {}
            if isinstance(entry.get("details"), dict):
                details = entry["details"]
            if res.get("success"):
                details["documentary_link"] = doc_url
                details["comment_text"] = text
                details["comment_posted"] = True
                if not comment_id and res.get("id"):
                    details["comment_id"] = res["id"]
                details.pop("doc_link_error", None)
                weeks.add(week_of(rel_path))
            else:
                attempts = int(details.get("doc_link_attempts") or 0) + 1
                details["doc_link_attempts"] = attempts
                details["doc_link_error"] = res.get("error")
                details["doc_link_retry_at"] = now + 300 * attempts
        if todo:
            asset_manager.save()
        for week in weeks:
            export_week_links(project_path, week)
        return len(weeks)

    def _update_comment(self, platform: str, comment_id: str, text: str) -> Dict[str, Any]:
        if platform == "youtube":
            return youtube_uploader.update_comment(comment_id, text)
        if platform == "facebook":
            return meta_uploader.update_comment(comment_id, text)
        return {"success": False, "error": f"Comments can't be edited on {platform}"}

    def _post_comment(self, platform: str, object_id: str, text: str) -> Dict[str, Any]:
        if platform == "youtube":
            return youtube_uploader.post_comment(object_id, text)
        if platform in ("facebook", "instagram"):
            return meta_uploader.post_comment(object_id, text)
        if platform == "threads":
            return threads_uploader.post_reply(object_id, text)
        return {"success": False, "error": f"Comments are not supported on {platform}"}

    def _dispatch_to_platform(
        self,
        platform: str,
        config: Dict[str, Any],
        video_path: Path,
        title: str,
        description: str,
        tags: List[str],
        scheduled_timestamp: Optional[int] = None,
        publish_at_iso: Optional[str] = None,
        is_short: bool = False,
        thumbnail_path: Optional[Path] = None,
        pinned_comment: Optional[str] = None,
        is_story: bool = False
    ) -> Dict[str, Any]:
        """Direct native execution handlers for social platforms with format-aware routing."""
        import logging

        if platform == "youtube":
            if youtube_uploader.is_authenticated():
                yt_mode = "YouTube Shorts" if is_short else "YouTube Standard"
                logging.info(f"[SocialDispatcher] Executing Direct Native Upload to {yt_mode}: {video_path.name}")
                clean_yt_desc = self.sanitize_urls_for_youtube(description)
                res = youtube_uploader.upload_video(
                    video_path=video_path,
                    title=title,
                    description=clean_yt_desc,
                    tags=tags,
                    privacy_status=config.get("privacy_status", "public"),
                    scheduled_publish_iso=publish_at_iso,
                    is_short=is_short,
                    thumbnail_path=thumbnail_path,
                    pinned_comment=pinned_comment
                )
                if res.get("status") == "published":
                    res["mode"] = yt_mode
                return res
            else:
                logging.info(f"[SocialDispatcher] YouTube OAuth not yet authenticated.")
                return {
                    "status": "failed",
                    "platform": "YouTube",
                    "error": "YouTube is not authenticated. Please authenticate via Studio Settings or run OAuth setup."
                }

        elif platform == "facebook":
            if meta_uploader.page_token:
                clean_fb_desc = self.sanitize_caption_for_facebook(description, hook=title)
                fb_comment = pinned_comment or DEFAULT_BHRS_PINNED_COMMENT
                if is_story:
                    logging.info(f"[SocialDispatcher] Executing Direct Native Upload to Facebook Story: {video_path.name}")
                    return meta_uploader.upload_facebook_story(video_path=video_path)
                if is_short:
                    logging.info(f"[SocialDispatcher] Executing Direct Native Upload to Facebook Reels: {video_path.name}")
                    return meta_uploader.upload_facebook_reel(
                        video_path=video_path,
                        title=title,
                        description=clean_fb_desc,
                        tags=tags,
                        scheduled_timestamp=scheduled_timestamp,
                        pinned_comment=fb_comment,
                        thumbnail_path=thumbnail_path
                    )
                else:
                    logging.info(f"[SocialDispatcher] Executing Direct Native Upload to Facebook Long Video (Watch): {video_path.name}")
                    return meta_uploader.upload_facebook_video(
                        video_path=video_path,
                        title=title,
                        description=clean_fb_desc,
                        tags=tags,
                        scheduled_timestamp=scheduled_timestamp,
                        pinned_comment=fb_comment,
                        thumbnail_path=thumbnail_path
                    )
            else:
                return {
                    "status": "failed",
                    "platform": "Facebook",
                    "error": "Facebook Page access token is not configured."
                }

        elif platform == "instagram":
            if meta_uploader.page_token and meta_uploader.ig_user_id:
                if is_story:
                    logging.info(f"[SocialDispatcher] Executing Direct Native Upload to Instagram Story: {video_path.name}")
                    return meta_uploader.upload_instagram_reel(video_path=video_path, caption="", media_type="STORIES")
                logging.info(f"[SocialDispatcher] Executing Direct Native Upload to Instagram Reels: {video_path.name}")
                return meta_uploader.upload_instagram_reel(
                    video_path=video_path,
                    caption=description or title,
                    tags=tags,
                    pinned_comment=pinned_comment or DEFAULT_BHRS_PINNED_COMMENT,
                    thumbnail_path=thumbnail_path
                )
            else:
                return {
                    "status": "failed",
                    "platform": "Instagram",
                    "error": "Instagram Business account is not connected to Facebook Page."
                }

        elif platform == "threads":
            if threads_uploader.is_authenticated():
                logging.info(f"[SocialDispatcher] Executing Direct Native Upload to Threads: {video_path.name}")
                return threads_uploader.upload_threads_video(
                    video_path=video_path,
                    caption=description or title,
                    tags=tags,
                    pinned_comment=pinned_comment
                )
            else:
                return {
                    "status": "failed",
                    "platform": "Threads",
                    "error": "Threads is not authenticated. Please connect your Threads account (Log In with Instagram) in Studio Settings."
                }

        elif platform == "tiktok":
            if tiktok_uploader.is_authenticated():
                tt_mode = "TikTok Reels" if is_short else "TikTok Long Video"
                logging.info(f"[SocialDispatcher] Executing Direct Native Upload to {tt_mode}: {video_path.name}")
                clean_tt_caption = self.sanitize_caption_for_tiktok(description)
                res = tiktok_uploader.upload_video(
                    video_path=video_path,
                    caption=clean_tt_caption or title,
                    tags=tags
                )
                if res.get("status") == "published":
                    res["mode"] = tt_mode
                return res
            else:
                return {
                    "status": "failed",
                    "platform": "TikTok",
                    "error": "TikTok is not authenticated. Please provide your sessionid or cookies in Studio Settings."
                }

        elif platform == "x":
            return {
                "status": "skipped",
                "platform": "X (Twitter)",
                "message": "Skipped: X posting is not implemented yet (no X API uploader)."
            }

        return {"status": "unsupported", "platform": platform}

social_dispatcher = SocialDispatcher()
