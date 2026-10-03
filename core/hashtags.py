"""
Shared hashtag rules for every platform caption (YouTube, Facebook, Instagram, Threads, TikTok, X).
"""

import re
from typing import Any, List, Optional, Tuple

# A real hashtag: '#' not glued to a preceding word, URL path or HTML entity ('C#', 'page#top', '&#39;')
# and containing at least one letter, so 'Part #2' or 'Bible Secrets #78' stay plain text.
_TAG = r"(?<![\w#&/])#(?=\w*[^\W\d_])\w+"
HASHTAG_RE = re.compile(_TAG)
_TRAILING_TAGS_RE = re.compile(r"(?:[ \t]*" + _TAG + r")+[ \t]*$")

# Tags that trigger safety/shadowban filters on short-form discovery feeds (matched as substrings,
# e.g. #SpiritualWarfare). Facebook and YouTube keep the post's own tags as written.
SENSITIVE_TAG_TERMS = ("lucifer", "satan", "demon", "warfare", "devil", "murder", "slaughter")
SENSITIVE_FILTER_PLATFORMS = ("instagram", "tiktok", "threads")

# Used only when a post had tags but every one of them was filtered as sensitive
DEFAULT_BRAND_TAGS = ("#BibleSecrets", "#ScriptureUncovered", "#BibleStudy", "#BiblicalTruth")

# Max hashtags per platform. YouTube ignores every hashtag on a video that has too many, Instagram allows 5,
# Threads only turns one tag per post into a topic, X works best with 1-2. Facebook and TikTok keep the full list.
PLATFORM_HASHTAG_LIMITS = {"youtube": 15, "facebook": 30, "instagram": 5, "tiktok": 30, "threads": 1, "x": 2}


def find_hashtags(text: str) -> List[str]:
    """Returns the real hashtags in text, in order of appearance."""
    return HASHTAG_RE.findall(text or "")


def split_tags(tags: Any) -> List[str]:
    """Turns a tag list or a tag string ('#A #B', 'A, B') into a list."""
    if isinstance(tags, str):
        return [t for t in re.split(r"[\s,]+", tags) if t]
    if isinstance(tags, (list, tuple, set)):
        return [str(t) for t in tags if t]
    return []


def strip_hashtags(text: str) -> Tuple[str, List[str]]:
    """
    Removes hashtags from text and returns (text, tags_found).
    Lines made only of hashtags and tag runs at the end of a line are dropped; a hashtag inside a
    sentence keeps its word ('Join our #BibleStudy tonight' -> 'Join our BibleStudy tonight').
    """
    found = find_hashtags(text)
    lines = []
    for line in (text or "").splitlines():
        without_trailing = _TRAILING_TAGS_RE.sub("", line)
        if line.strip() and not without_trailing.strip():
            continue
        lines.append(HASHTAG_RE.sub(lambda m: m.group(0)[1:], without_trailing).rstrip())
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return cleaned, found


def tag_word(raw: str) -> str:
    """
    One tag as a single hashtag word: 'Divine Council' -> 'DivineCouncil', '#Pre-CosmicFall' -> 'PreCosmicFall',
    'Genesis 1:1' -> 'Genesis1' (platforms end a hashtag at ':' anyway).
    """
    words = re.split(r"[\s\-]+", str(raw).split(":")[0].lstrip("#"))
    return re.sub(r"\W", "", "".join(w[:1].upper() + w[1:] for w in words))


def normalize_tags(tags: Any, platform: str, max_tags: Optional[int] = None) -> str:
    """
    Cleans tags for a platform: adds '#', joins multi-word tags, drops number-only tags (and sensitive ones on
    short-form feeds), de-duplicates case-insensitively and caps at the platform limit (first tags win).
    """
    limit = max_tags if max_tags is not None else PLATFORM_HASHTAG_LIMITS.get(platform, 5)
    filter_sensitive = platform in SENSITIVE_FILTER_PLATFORMS
    clean: List[str] = []
    seen = set()
    had_tags = False
    for raw in split_tags(tags):
        word = tag_word(raw)
        if not re.search(r"[^\W\d_]", word):
            continue
        had_tags = True
        key = word.lower()
        if key in seen or (filter_sensitive and any(term in key for term in SENSITIVE_TAG_TERMS)):
            continue
        seen.add(key)
        clean.append(f"#{word}")
    if not clean and had_tags:
        clean = list(DEFAULT_BRAND_TAGS)
    return " ".join(clean[:limit])


def append_hashtag(text: str, tag: str) -> str:
    """Adds a tag to the trailing hashtag line of text (or starts one)."""
    text = (text or "").rstrip()
    last_line = text.splitlines()[-1] if text else ""
    if last_line.strip() and not _TRAILING_TAGS_RE.sub("", last_line).strip():
        return f"{text} {tag}"
    return f"{text}\n\n{tag}".strip()
