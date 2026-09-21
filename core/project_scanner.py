import os
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

KNOWN_PIPELINE_SCRIPTS = {
    "generate_chapter.py": {
        "label": "Master Chapter Dispatcher",
        "description": "Full workflow orchestrator across all or single chapters",
        "category": "master",
        "recommended_args": ["--status", "--all", "--chapter 1", "--audio-only", "--images-only"]
    },
    "generate_audio.py": {
        "label": "Dual-Track Audio Generator",
        "description": "Synthesize Microsoft VibeVoice audio & run Whisper alignment",
        "category": "audio",
        "recommended_args": ["--all", "--chapter 1", "--from 1 --to 4"]
    },
    "batch_generate_vibevoice.py": {
        "label": "VibeVoice Batch Narrator",
        "description": "Direct Microsoft VibeVoice Realtime 0.5B neural TTS batcher",
        "category": "audio",
        "recommended_args": ["--all", "--chapter 1"]
    },
    "generate_images.py": {
        "label": "FLUX Image Generator",
        "description": "Renders 16:9 widescreen 1344x768 manhwa scene visuals via ComfyUI",
        "category": "visual",
        "recommended_args": ["--all", "--chapter 1", "--from 1 --to 4"]
    },
    "generate_video.py": {
        "label": "Video Compositor & Motion",
        "description": "Renders dynamic Ken Burns camera motion & Videoke karaoke subtitles",
        "category": "video",
        "recommended_args": ["--all", "--chapter 1", "--from 1 --to 4"]
    },
    "combine_all_videos.py": {
        "label": "Combine Chapters Master Video",
        "description": "Lossless concat demuxer muxing all chapter reels into final video",
        "category": "mastering",
        "recommended_args": ["--check-only", "", "--from 1 --to 4", "--render-missing", "--reencode"]
    },
    "combine_chapters.py": {
        "label": "Combine Chapters",
        "description": "Merge rendered chapters into master video",
        "category": "mastering",
        "recommended_args": ["--check-only", "", "--from 1 --to 4"]
    },
    "build_all_chapters_video.py": {
        "label": "Build All Chapters Video",
        "description": "Compiles all available chapters into complete story video",
        "category": "mastering",
        "recommended_args": ["--check-only", "", "--from 1 --to 4"]
    },
    "generate_all_character_turnarounds.py": {
        "label": "Character Turnarounds Generator",
        "description": "4-angle turnaround model sheets for visual continuity",
        "category": "preprod",
        "recommended_args": [""]
    },
    "generate_trading_god_turnarounds.py": {
        "label": "Trading God Turnarounds",
        "description": "Character model sheets for Trading God series",
        "category": "preprod",
        "recommended_args": [""]
    },
    "rebuild_all_sections_and_full_movie.py": {
        "label": "Rebuild Sections & Master Movie",
        "description": "Rebuilds all narrative sections into master video",
        "category": "mastering",
        "recommended_args": [""]
    },
    "create_all_episode_scripts.py": {
        "label": "Episode Script Creator",
        "description": "Script decomposition and narrative formatting",
        "category": "preprod",
        "recommended_args": [""]
    },
    "extract_yt_script.py": {
        "label": "YouTube Script Extractor",
        "description": "Pulls original narration transcripts and segments paragraphs",
        "category": "preprod",
        "recommended_args": [""]
    },
    "generate_reel.py": {
        "label": "Vertical Reel Generator",
        "description": "Renders 9:16 vertical video reel with FLUX visuals, AI narration & karaoke captions",
        "category": "video",
        "recommended_args": ["--all", "--chapter 1", "--from 1 --to 4"]
    },
    "generate_image.py": {
        "label": "FLUX Scene Image Generator",
        "description": "Renders scene visuals via ComfyUI FLUX workflow",
        "category": "visual",
        "recommended_args": ["--all", "--chapter 1"]
    },
    "generate_episodes.py": {
        "label": "Batch Episode Generator",
        "description": "Batch documentary episode generation pipeline",
        "category": "master",
        "recommended_args": ["--all", "--from 1 --to 4"]
    }
}

def is_pipeline_script(filename: str) -> bool:
    """Checks if script is an executable generation, combination, or build script."""
    fn = filename.lower()
    return any(k in fn for k in ["generate", "combine", "build", "rebuild", "run"])

def parse_numbered_folder(folder_name: str) -> Optional[Dict[str, Any]]:
    """Strictly matches folders prefixed with a number (e.g. 01_..., 1-..., chapter_1, episode_1).
    Ignores non-numbered utility folders like __pycache__, demucs_stems, scratch, stories, shared_assets."""
    # 1. Matches 01_dead_nation_resurrected, 1-David_and_Goliath, 10_..., etc.
    m1 = re.match(r"^(\d+)(?:[_\s.-]+(.*)|$)", folder_name)
    if m1:
        num = int(m1.group(1))
        suffix = (m1.group(2) or "").strip()
        clean = suffix.replace("_", " ").replace("-", " ").strip()
        if not clean:
            clean = f"Episode {num}"
        else:
            clean = " ".join(word.capitalize() for word in clean.split())
        return {"episode_num": num, "clean_title": clean, "raw_prefix": m1.group(1), "is_chapter": False}

    # 2. Matches chapter_1, chapter-2, Chapter 03, etc.
    m2 = re.match(r"^chapter[_\s.-]?(\d+)(?:[_\s.-]+(.*)|$)", folder_name, re.IGNORECASE)
    if m2:
        num = int(m2.group(1))
        suffix = (m2.group(2) or "").strip()
        clean = suffix.replace("_", " ").replace("-", " ").strip()
        title = f"Chapter {num}" + (f" - {' '.join(w.capitalize() for w in clean.split())}" if clean else "")
        return {"episode_num": num, "clean_title": title, "raw_prefix": f"ch{num}", "is_chapter": True}

    # 3. Matches episode_1, episode-2, Episode 03, etc.
    m3 = re.match(r"^episode[_\s.-]?(\d+)(?:[_\s.-]+(.*)|$)", folder_name, re.IGNORECASE)
    if m3:
        num = int(m3.group(1))
        suffix = (m3.group(2) or "").strip()
        clean = suffix.replace("_", " ").replace("-", " ").strip()
        title = f"Episode {num}" + (f" - {' '.join(w.capitalize() for w in clean.split())}" if clean else "")
        return {"episode_num": num, "clean_title": title, "raw_prefix": f"ep{num}", "is_chapter": False}

    return None

class ProjectScanner:
    @staticmethod
    def scan_project(project_path_str: str) -> Dict[str, Any]:
        project_path = Path(project_path_str)
        if not project_path.exists() or not project_path.is_dir():
            return {
                "valid": False,
                "error": f"Directory does not exist: {project_path_str}",
                "path": project_path_str
            }

        # 1. Detect Available Pipeline Scripts
        scripts = []
        for file in project_path.glob("*.py"):
            name = file.name
            if not is_pipeline_script(name):
                continue
            meta = KNOWN_PIPELINE_SCRIPTS.get(name, {
                "label": name.replace(".py", "").replace("_", " ").title(),
                "description": "Custom project script",
                "category": "custom",
                "recommended_args": []
            })
            scripts.append({
                "filename": name,
                "path": str(file),
                "label": meta["label"],
                "description": meta["description"],
                "category": meta["category"],
                "recommended_args": meta["recommended_args"]
            })
        
        # Sort scripts by category priority
        cat_order = {"master": 0, "mastering": 1, "video": 2, "audio": 3, "visual": 4, "preprod": 5, "custom": 6}
        scripts.sort(key=lambda s: (cat_order.get(s["category"], 99), s["filename"]))

        # 2. Detect Chapters / Episodes (Strictly Number-Prefixed Folders Only)
        # Check if root folder itself has chapters, sections or parts
        root_chapters = []
        for d in project_path.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                m_sub = re.match(r"^(chapter|section|part)[_\s.-]?(\d+)(?:[_\s.-]+(.*)|$)", d.name, re.IGNORECASE)
                if m_sub:
                    kind = m_sub.group(1).capitalize()
                    num = int(m_sub.group(2))
                    suffix = (m_sub.group(3) or "").strip()
                    clean = f"{kind}_{num}"
                    if suffix:
                        clean += f" ({suffix.replace('_', ' ').replace('-', ' ').title()})"
                    root_chapters.append({
                        "name": d.name,
                        "chapter_num": num,
                        "kind": kind.lower(),
                        "clean_title": clean,
                        "arg": f"--{kind.lower()} {num}"
                    })
        root_chapters.sort(key=lambda x: x["chapter_num"])
        has_root_chapters = len(root_chapters) > 0

        chapter_dirs = []
        # Check direct subdirectories first
        for d in project_path.iterdir():
            if d.is_dir() and not d.name.startswith("."):
                parsed = parse_numbered_folder(d.name)
                if parsed:
                    rel_p = str(d.relative_to(project_path)).replace("\\", "/")
                    chapter_dirs.append((d, parsed, rel_p))

        # If root has no numbered folders, inspect common subdirectories like reels, episodes, chapters, stories
        if not chapter_dirs:
            for sub_name in ["reels", "episodes", "chapters", "stories"]:
                sub_dir = project_path / sub_name
                if sub_dir.exists() and sub_dir.is_dir():
                    for d in sub_dir.iterdir():
                        if d.is_dir() and not d.name.startswith("."):
                            parsed = parse_numbered_folder(d.name)
                            if parsed:
                                rel_p = str(d.relative_to(project_path)).replace("\\", "/")
                                chapter_dirs.append((d, parsed, rel_p))
                    if chapter_dirs:
                        break

        # Sort chapters naturally by episode number
        chapter_dirs.sort(key=lambda x: x[1]["episode_num"])

        chapters = []
        for ch_dir, parsed, rel_folder in chapter_dirs:
            # Check script / transcript / metadata
            has_script = (
                len(list(ch_dir.glob("*script*.*"))) > 0 or
                len(list(ch_dir.glob("*transcript*.*"))) > 0 or
                (ch_dir / "metadata.json").exists() or
                (ch_dir / "metadata.txt").exists()
            )

            # Check Images
            img_count = 0
            for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
                img_count += len(list(ch_dir.glob(ext)))
            img_dir = ch_dir / "images"
            if img_dir.exists():
                for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]:
                    img_count += len(list(img_dir.glob(ext)))

            # Check Videos (Direct mp4s, reels, slideshows, output)
            video_candidates = []
            video_candidates.extend(list(ch_dir.glob("*.mp4")))
            for sub in ["slideshow", "reels", "output"]:
                s_dir = ch_dir / sub
                if s_dir.exists() and s_dir.is_dir():
                    video_candidates.extend(list(s_dir.glob("*.mp4")))

            seen_vids = set()
            video_files = []
            for vf in video_candidates:
                if vf.resolve() not in seen_vids:
                    seen_vids.add(vf.resolve())
                    video_files.append(vf)

            has_video = len(video_files) > 0
            primary_video = str(video_files[0].relative_to(project_path)).replace("\\", "/") if video_files else None
            primary_video_size = video_files[0].stat().st_size if video_files else 0

            # Check Audio (Direct wav/mp3 or temp)
            audio_files = []
            for ext in ["*.wav", "*.mp3", "*.aac"]:
                audio_files.extend(list(ch_dir.glob(ext)))
            temp_dir = ch_dir / "temp"
            if temp_dir.exists():
                for ext in ["*.wav", "*.mp3"]:
                    audio_files.extend(list(temp_dir.glob(ext)))

            has_audio = len(audio_files) > 0

            # Check sub-chapters / sections / parts inside this episode folder
            sub_chapters = []
            for sub_d in ch_dir.iterdir():
                if sub_d.is_dir() and not sub_d.name.startswith("."):
                    m_sub = re.match(r"^(chapter|section|part)[_\s.-]?(\d+)(?:[_\s.-]+(.*)|$)", sub_d.name, re.IGNORECASE)
                    if m_sub:
                        kind = m_sub.group(1).capitalize()
                        num = int(m_sub.group(2))
                        suffix = (m_sub.group(3) or "").strip()
                        clean = f"{kind}_{num}"
                        if suffix:
                            clean += f" ({suffix.replace('_', ' ').replace('-', ' ').title()})"
                        sub_chapters.append({
                            "name": sub_d.name,
                            "chapter_num": num,
                            "kind": kind.lower(),
                            "clean_title": clean,
                            "arg": f"--{kind.lower()} {num}"
                        })
            sub_chapters.sort(key=lambda x: x["chapter_num"])

            # Check scripts inside this episode folder
            ep_scripts = []
            for f in ch_dir.glob("*.py"):
                if is_pipeline_script(f.name):
                    meta = KNOWN_PIPELINE_SCRIPTS.get(f.name, {
                        "label": f.name.replace(".py", "").replace("_", " ").title(),
                        "description": f"Episode pipeline script for {ch_dir.name}",
                        "category": "custom",
                        "recommended_args": []
                    })
                    ep_scripts.append({
                        "filename": f.name,
                        "rel_path": str(f.relative_to(project_path)).replace("\\", "/"),
                        "path": str(f),
                        "label": meta["label"],
                        "description": meta["description"],
                        "category": meta["category"],
                        "recommended_args": meta["recommended_args"]
                    })
            ep_scripts.sort(key=lambda s: (cat_order.get(s["category"], 99), s["filename"]))

            chapters.append({
                "name": ch_dir.name,
                "rel_path": rel_folder,
                "path": str(ch_dir),
                "episode_num": parsed["episode_num"],
                "clean_title": parsed["clean_title"],
                "has_script": has_script,
                "image_count": img_count,
                "has_audio": has_audio,
                "audio_count": len(audio_files),
                "has_video": has_video,
                "video_count": len(video_files),
                "video_rel_path": primary_video,
                "video_size_mb": round(primary_video_size / (1024 * 1024), 2),
                "sub_chapters": sub_chapters,
                "has_sub_chapters": len(sub_chapters) > 0,
                "scripts": ep_scripts
            })

        # 3. Master Video Check
        master_videos = []
        for f in project_path.glob("*.mp4"):
            master_videos.append({
                "filename": f.name,
                "rel_path": f.name,
                "path": str(f),
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
                "modified": f.stat().st_mtime
            })

        # 4. Narrative Data Files
        narrative_files = {}
        for fname in ["scenes_parsed.json", "scenes_prompts.json", "script_clean.txt", "script_with_timestamps.txt", "character_profiles.md", "README.md", "GEMINI.md"]:
            fp = project_path / fname
            if fp.exists():
                narrative_files[fname] = {
                    "exists": True,
                    "size_kb": round(fp.stat().st_size / 1024, 1),
                    "path": str(fp)
                }

        # Scenes count if scenes_parsed.json exists
        total_scenes = None
        parsed_json = project_path / "scenes_parsed.json"
        if parsed_json.exists():
            try:
                with open(parsed_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        total_scenes = len(data)
                    elif isinstance(data, dict):
                        total_scenes = len(data.get("scenes", [])) or len(data.keys())
            except Exception:
                pass

        return {
            "valid": True,
            "name": project_path.name,
            "path": str(project_path),
            "scripts": scripts,
            "chapters": chapters,
            "total_chapters": len(chapters),
            "rendered_chapters": sum(1 for c in chapters if c["has_video"]),
            "total_scenes": total_scenes,
            "master_videos": master_videos,
            "narrative_files": narrative_files,
            "has_turnarounds": (project_path / "Character_Turnarounds").exists(),
            "has_vibevoice_folder": (project_path / "Audio_Narrator_VibeVoice").exists(),
            "has_root_chapters": has_root_chapters,
            "root_chapters": root_chapters
        }
