r"""
=============================================================================
KCT Studio - Master Biblical Story Map & Curriculum Manager
=============================================================================
Manages the 3-Year (156 Weeks) Master Content Franchise:
- 156 Flagship Documentaries (16:9, 15-35 min)
- 780 Numbered Reels (9:16, 5/week)
- 780 Numbered Stories (5/week)
- 780 Community Tab Posts/Polls (5/week)
- 312 Substack Dispatches (Sunday Pillar + Thursday Mid-Week Digest)
- Automatically checks C:\Projects\BHRS-Youtube for covered video files.
=============================================================================
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional

logger = logging.getLogger("story_map_manager")

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
STORY_MAP_FILE = DATA_DIR / "story_map_data.json"
BHSR_ROOT = Path("C:/Projects/BHSR")
if not BHSR_ROOT.exists():
    BHSR_ROOT = Path("C:/Projects/BHRS")

from core.asset_manager import asset_manager

class StoryMapManager:
    def __init__(self, data_file: Optional[Path] = None):
        self.data_file = data_file or STORY_MAP_FILE
        self._ensure_data_file()

    def _ensure_data_file(self):
        """Ensures data/story_map_data.json exists, generating the 156-week master curriculum if absent."""
        if not self.data_file.exists():
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            initial_data = self._generate_full_curriculum()
            self._save_data(initial_data)
        else:
            # Sync covered status with physical files on disk
            self.refresh_covered_status()

    def _save_data(self, data: Dict[str, Any]):
        self.data_file.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_data(self) -> Dict[str, Any]:
        if not self.data_file.exists():
            return self._generate_full_curriculum()
        try:
            return json.loads(self.data_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to read story map data: {e}")
            return self._generate_full_curriculum()

    def refresh_covered_status(self):
        """Scans C:/Projects/BHSR for rendered .mp4 files across W01..W156 episodic folders and links long-form, reels, and stories."""
        data = self._load_data()
        weeks = data.get("weeks", [])
        
        updated = False
        for w in weeks:
            w_num = w.get("week")
            doc = w.get("documentary", {})
            reels = w.get("reels", [])
            stories = w.get("stories", [])
            w_dir = BHSR_ROOT / f"W{w_num:02d}"

            # ----------------- 1. Long-Form Documentary -----------------
            long_form_videos = []
            matched_doc_rel = None
            if w_dir.exists():
                lf_dir = w_dir / "long_form"
                if not lf_dir.exists():
                    lf_dir = w_dir / "longform"
                if lf_dir.exists():
                    # 1.1 Check for video subfolders (like reels)
                    lf_subdirs = sorted([
                        d for d in lf_dir.iterdir() 
                        if d.is_dir() and d.name.lower() not in ["images", "temp", "__pycache__", "sample_2min_before_genesis"]
                    ])

                    for s_idx, s_dir in enumerate(lf_subdirs):
                        s_title = doc.get("title", f"Documentary {s_idx+1}")
                        s_hook = doc.get("hook", "")
                        s_meta = s_dir / "metadata.json"
                        if not s_meta.exists():
                            s_meta = s_dir / "episode_metadata.json"
                        if s_meta.exists():
                            try:
                                sm = json.loads(s_meta.read_text(encoding="utf-8"))
                                s_title = sm.get("title") or sm.get("episode_title") or s_title
                                s_hook = sm.get("hook") or s_hook
                            except Exception:
                                pass

                        s_thumb = None
                        for tn in ["thumbnail.jpg", "thumbnail.png", "thumbnail_option_1.jpg", "thumbnail_option_2.jpg"]:
                            tp = s_dir / tn
                            if tp.exists():
                                s_thumb = f"/api/thumbnail/{str(tp.relative_to(BHSR_ROOT)).replace('\\', '/')}"
                                break

                        s_script = None
                        sw_count = 0
                        for sc in ["script_30min.txt", "script.txt", "script.md"]:
                            sp = s_dir / sc
                            if sp.exists():
                                s_script = sc
                                try:
                                    sw_count = len(sp.read_text(encoding="utf-8", errors="replace").split())
                                except Exception:
                                    pass
                                break

                        s_mp4s = [p for p in s_dir.glob("*.mp4") if "temp" not in p.parts]
                        v_rel = None
                        if s_mp4s:
                            s_mp4s.sort(key=lambda x: (0 if "16x9" in x.name.lower() else (1 if "final" in x.name.lower() else 2)))
                            v_rel = str(s_mp4s[0].relative_to(BHSR_ROOT)).replace("\\", "/")
                            if not s_thumb:
                                s_thumb = f"/api/thumbnail/{v_rel}"

                        pub = asset_manager.get_asset_record(v_rel).get("published", {}) if v_rel else {}
                        v_status = "covered" if v_rel else ("in_production" if s_script else "planned")

                        long_form_videos.append({
                            "index": s_idx,
                            "id": f"doc_{s_idx+1}",
                            "subfolder": s_dir.name,
                            "title": s_title,
                            "hook": s_hook,
                            "label": f"Video {s_idx+1}: {s_dir.name.replace('_', ' ').title()}",
                            "short_label": f"V{s_idx+1}: {s_dir.name[:18].replace('_', ' ').title()}",
                            "has_video": bool(v_rel),
                            "video_url": f"/api/media/{v_rel}" if v_rel else None,
                            "thumbnail_url": s_thumb,
                            "rel_path": v_rel,
                            "duration": doc.get("duration", "28 min"),
                            "script_file": s_script,
                            "script_word_count": sw_count,
                            "status": v_status,
                            "published": pub
                        })

                    # 1.2 If no subfolders found, scan root lf_dir
                    if not long_form_videos:
                        mp4s = [p for p in lf_dir.glob("*.mp4") if "temp" not in p.parts and "sample" not in p.name.lower()]
                        if not mp4s:
                            mp4s = [p for p in lf_dir.glob("*.mp4") if "temp" not in p.parts]

                        r_thumb = None
                        for tn in ["thumbnail.jpg", "thumbnail.png", "thumbnail_option_1.jpg"]:
                            tp = lf_dir / tn
                            if tp.exists():
                                r_thumb = f"/api/thumbnail/{str(tp.relative_to(BHSR_ROOT)).replace('\\', '/')}"
                                break

                        r_script = None
                        rw_count = 0
                        for sc in ["script_30min.txt", "script.txt", "script.md"]:
                            sp = lf_dir / sc
                            if sp.exists():
                                r_script = sc
                                try:
                                    rw_count = len(sp.read_text(encoding="utf-8", errors="replace").split())
                                except Exception:
                                    pass
                                break

                        for idx, vid in enumerate(mp4s):
                            v_rel = str(vid.relative_to(BHSR_ROOT)).replace("\\", "/")
                            pub = asset_manager.get_asset_record(v_rel).get("published", {})
                            long_form_videos.append({
                                "index": idx,
                                "id": f"doc_{idx+1}",
                                "subfolder": None,
                                "title": doc.get("title", f"Long-Form Documentary"),
                                "hook": doc.get("hook", ""),
                                "label": f"Video Cut {idx+1}: {vid.stem.replace('_', ' ').title()}",
                                "short_label": f"V{idx+1}: Cut {idx+1}",
                                "has_video": True,
                                "video_url": f"/api/media/{v_rel}",
                                "thumbnail_url": r_thumb or f"/api/thumbnail/{v_rel}",
                                "rel_path": v_rel,
                                "duration": doc.get("duration", "28 min"),
                                "script_file": r_script,
                                "script_word_count": rw_count,
                                "status": "covered",
                                "published": pub
                            })

                        if not long_form_videos and r_script:
                            long_form_videos.append({
                                "index": 0,
                                "id": "doc_1",
                                "subfolder": None,
                                "title": doc.get("title", f"Long-Form Documentary"),
                                "hook": doc.get("hook", ""),
                                "label": "Master Documentary",
                                "short_label": "V1: Master",
                                "has_video": False,
                                "video_url": None,
                                "thumbnail_url": r_thumb,
                                "rel_path": None,
                                "duration": doc.get("duration", "28 min"),
                                "script_file": r_script,
                                "script_word_count": rw_count,
                                "status": "in_production",
                                "published": {}
                            })
            if w.get("long_form_videos") != long_form_videos:
                w["long_form_videos"] = long_form_videos
                updated = True

            # Primary documentary sync for backwards compatibility
            if long_form_videos:
                primary = long_form_videos[0]
                if primary["has_video"]:
                    matched_doc_rel = primary["rel_path"]
                    if (doc.get("status") != "covered" or 
                        doc.get("rel_path") != matched_doc_rel or 
                        doc.get("video_url") != primary["video_url"]):
                        doc["status"] = "covered"
                        doc["rel_path"] = matched_doc_rel
                        doc["video_url"] = primary["video_url"]
                        doc["thumbnail_url"] = primary["thumbnail_url"]
                        doc["published"] = primary["published"]
                        updated = True
                elif primary.get("script_file"):
                    if doc.get("status") != "in_production" or doc.get("video_url"):
                        doc["status"] = "in_production"
                        doc["rel_path"] = None
                        doc["video_url"] = None
                        doc["thumbnail_url"] = primary.get("thumbnail_url")
                        updated = True
            else:
                existing_rel = doc.get("rel_path")
                if existing_rel and (BHSR_ROOT / existing_rel).is_file() and existing_rel.lower().endswith(".mp4"):
                    pub = asset_manager.get_asset_record(existing_rel).get("published", {})
                    if doc.get("status") != "covered" or not doc.get("video_url") or doc.get("published") != pub:
                        doc["status"] = "covered"
                        doc["video_url"] = f"/api/media/{existing_rel}"
                        doc["thumbnail_url"] = f"/api/thumbnail/{existing_rel}"
                        doc["published"] = pub
                        updated = True
                else:
                    if doc.get("video_url") or (existing_rel and not existing_rel.lower().endswith(".mp4")):
                        doc["video_url"] = None
                        doc["thumbnail_url"] = None
                        doc["rel_path"] = ""
                        has_scripts = w_dir.exists() and (
                            any(p.suffix in [".txt", ".md", ".json"] and "script" in p.name.lower() for p in (w_dir / "long_form").glob("*"))
                            if (w_dir / "long_form").exists() else False
                        )
                        doc["status"] = "in_production" if has_scripts else "planned"
                        updated = True

            # ----------------- 2. 5 Vertical Reels (Mon-Fri) -----------------
            r_dir = (w_dir / "reels") if (w_dir / "reels").exists() else ((w_dir / "reel") if (w_dir / "reel").exists() else None)
            subdirs = sorted([d for d in r_dir.iterdir() if d.is_dir() and "temp" not in d.name.lower()]) if (r_dir and r_dir.exists()) else []

            for i in range(min(5, len(reels))):
                reel_obj = reels[i]
                target_sub = None
                day_prefix = f"0{i+1}"
                global_reel_num = (w_num - 1) * 5 + (i + 1)
                for d in subdirs:
                    if (d.name.startswith(day_prefix) or 
                        d.name.startswith(f"{i+1}_") or 
                        d.name.startswith(f"{global_reel_num}_") or
                        f"reel_{i+1}" in d.name.lower() or 
                        f"reel{i+1}" in d.name.lower()):
                        target_sub = d
                        break
                if not target_sub and i < len(subdirs):
                    target_sub = subdirs[i]

                chosen_reel = None
                if target_sub:
                    r_mp4s = [p for p in target_sub.glob("*.mp4") if "temp" not in p.parts]
                    if r_mp4s:
                        r_mp4s.sort(key=lambda x: (
                            0 if "final_reel" in x.name.lower()
                            else (1 if "perfect_master" in x.name.lower()
                            else (2 if "master" in x.name.lower()
                            else (3 if "final" in x.name.lower() else 4)))
                        ))
                        chosen_reel = r_mp4s[0]

                if chosen_reel:
                    r_rel = str(chosen_reel.relative_to(BHSR_ROOT)).replace("\\", "/")
                    pub = asset_manager.get_asset_record(r_rel).get("published", {})
                    if (reel_obj.get("rel_path") != r_rel or 
                        reel_obj.get("published") != pub or 
                        not reel_obj.get("has_video") or
                        not reel_obj.get("video_url")):
                        reel_obj["rel_path"] = r_rel
                        reel_obj["video_url"] = f"/api/media/{r_rel}"
                        reel_obj["thumbnail_url"] = f"/api/thumbnail/{r_rel}"
                        reel_obj["has_video"] = True
                        reel_obj["published"] = pub
                        updated = True
                else:
                    existing_r = reel_obj.get("rel_path")
                    if existing_r and (BHSR_ROOT / existing_r).is_file() and existing_r.lower().endswith(".mp4"):
                        pub = asset_manager.get_asset_record(existing_r).get("published", {})
                        if not reel_obj.get("has_video") or not reel_obj.get("video_url"):
                            reel_obj["has_video"] = True
                            reel_obj["video_url"] = f"/api/media/{existing_r}"
                            reel_obj["thumbnail_url"] = f"/api/thumbnail/{existing_r}"
                            reel_obj["published"] = pub
                            updated = True
                    else:
                        if reel_obj.get("has_video") or reel_obj.get("video_url"):
                            reel_obj["has_video"] = False
                            reel_obj["video_url"] = None
                            reel_obj["thumbnail_url"] = None
                            reel_obj["rel_path"] = None
                            updated = True

            # ----------------- 3. 5 Daily Stories (Mon-Fri) -----------------
            s_dir = (w_dir / "stories") if (w_dir / "stories").exists() else ((w_dir / "story") if (w_dir / "story").exists() else None)
            s_subdirs = sorted([d for d in s_dir.iterdir() if d.is_dir() and "temp" not in d.name.lower()]) if (s_dir and s_dir.exists()) else []

            for i in range(min(5, len(stories))):
                story_obj = stories[i]
                target_s_sub = None
                day_prefix = f"0{i+1}"
                for d in s_subdirs:
                    if d.name.startswith(day_prefix) or d.name.startswith(f"{i+1}-") or f"story_{i+1}" in d.name.lower():
                        target_s_sub = d
                        break
                if not target_s_sub and i < len(s_subdirs):
                    target_s_sub = s_subdirs[i]

                chosen_story = None
                if target_s_sub:
                    s_mp4s = [p for p in target_s_sub.glob("*.mp4") if "temp" not in p.parts]
                    if s_mp4s:
                        s_mp4s.sort(key=lambda x: (0 if "story_video" in x.name.lower() else (1 if "final" in x.name.lower() else 2)))
                        chosen_story = s_mp4s[0]

                if chosen_story:
                    s_rel = str(chosen_story.relative_to(BHSR_ROOT)).replace("\\", "/")
                    pub = asset_manager.get_asset_record(s_rel).get("published", {})
                    if (story_obj.get("rel_path") != s_rel or 
                        story_obj.get("published") != pub or 
                        not story_obj.get("has_video") or
                        not story_obj.get("video_url")):
                        story_obj["rel_path"] = s_rel
                        story_obj["video_url"] = f"/api/media/{s_rel}"
                        story_obj["thumbnail_url"] = f"/api/thumbnail/{s_rel}"
                        story_obj["has_video"] = True
                        story_obj["published"] = pub
                        updated = True
                else:
                    existing_s = story_obj.get("rel_path")
                    if existing_s and (BHSR_ROOT / existing_s).is_file() and existing_s.lower().endswith(".mp4"):
                        pub = asset_manager.get_asset_record(existing_s).get("published", {})
                        if not story_obj.get("has_video") or not story_obj.get("video_url"):
                            story_obj["has_video"] = True
                            story_obj["video_url"] = f"/api/media/{existing_s}"
                            story_obj["thumbnail_url"] = f"/api/thumbnail/{existing_s}"
                            story_obj["published"] = pub
                            updated = True
                    else:
                        if story_obj.get("has_video") or story_obj.get("video_url"):
                            story_obj["has_video"] = False
                            story_obj["video_url"] = None
                            story_obj["thumbnail_url"] = None
                            story_obj["rel_path"] = None
                            updated = True

        if updated:
            self._save_data(data)

    def get_curriculum(
        self,
        year: Optional[int] = None,
        quarter: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Returns the filtered master story map curriculum and summary metrics."""
        self.refresh_covered_status()
        data = self._load_data()
        weeks = data.get("weeks", [])

        # Filter by Year
        if year is not None and year in (1, 2, 3):
            weeks = [w for w in weeks if w.get("year") == year]

        # Filter by Quarter (Q1 to Q12)
        if quarter:
            q_clean = quarter.strip().upper()
            weeks = [w for w in weeks if w.get("quarter", "").upper() == q_clean]

        # Filter by Status (covered, in_production, planned)
        if status:
            s_clean = status.strip().lower()
            weeks = [w for w in weeks if w.get("documentary", {}).get("status", "").lower() == s_clean]

        # Search Query across Title, Scriptures, Theme, Christological Key
        if search:
            query = search.strip().lower()
            filtered = []
            for w in weeks:
                doc = w.get("documentary", {})
                title = doc.get("title", "").lower()
                scriptures = " ".join(doc.get("scriptures", [])).lower()
                key = doc.get("christological_key", "").lower()
                theme = w.get("theme", "").lower()
                if query in title or query in scriptures or query in key or query in theme:
                    filtered.append(w)
            weeks = filtered

        # Summary stats across full catalog
        all_weeks = data.get("weeks", [])
        covered_count = sum(1 for w in all_weeks if w.get("documentary", {}).get("status") == "covered")
        y1_weeks = [w for w in all_weeks if w.get("year") == 1]
        y1_covered = sum(1 for w in y1_weeks if w.get("documentary", {}).get("status") == "covered")

        stats = {
            "total_weeks": len(all_weeks),
            "total_years": 3,
            "total_documentaries": len(all_weeks),
            "total_reels": len(all_weeks) * 5,
            "total_stories": len(all_weeks) * 5,
            "total_community_posts": len(all_weeks) * 5,
            "total_substack_issues": len(all_weeks) * 2,
            "total_covered": covered_count,
            "total_in_production": sum(1 for w in all_weeks if w.get("documentary", {}).get("status") == "in_production"),
            "total_planned": sum(1 for w in all_weeks if w.get("documentary", {}).get("status") == "planned"),
            "year1_covered": y1_covered,
            "year1_total": len(y1_weeks),
            "year1_percentage": round((y1_covered / len(y1_weeks) * 100), 1) if y1_weeks else 0.0,
            "overall_percentage": round((covered_count / len(all_weeks) * 100), 1) if all_weeks else 0.0
        }

        return {
            "stats": stats,
            "count": len(weeks),
            "weeks": weeks
        }

    def get_week_detail(self, week_num: int) -> Optional[Dict[str, Any]]:
        """Returns the full data object for a single week by number."""
        data = self._load_data()
        for w in data.get("weeks", []):
            if w.get("week") == week_num:
                return w
        return None

    def _generate_full_curriculum(self) -> Dict[str, Any]:
        """Generates the master 3-Year / 156-Week curriculum dataset with sub-tables for each week."""
        # Predefined Year 1 (Weeks 1-52), Year 2 (Weeks 53-104), and Year 3 (Weeks 105-156) definitions
        from core.story_map_definitions import MASTER_WEEK_DEFINITIONS
        
        weeks = []
        for defn in MASTER_WEEK_DEFINITIONS:
            w_num = defn["week"]
            year = 1 if w_num <= 52 else (2 if w_num <= 104 else 3)
            q_num = ((w_num - 1) // 13) + 1
            quarter = f"Q{q_num}"

            # 5 Numbered Reels
            reels = []
            reel_days = ["Mon", "Tue", "Wed", "Thu", "Fri"]
            hook_types = ["Mystery Hook", "Ancient Hebrew / Text", "Prophecy / Scroll", "Christological Typology", "Bestselling Book CTA"]
            for i in range(5):
                global_reel_num = (w_num - 1) * 5 + (i + 1)
                reels.append({
                    "id": f"R-W{w_num:02d}.{i+1}",
                    "num": i + 1,
                    "global_num": global_reel_num,
                    "day": reel_days[i],
                    "badge": f"Bible Secrets #{global_reel_num:03d} [W{w_num:02d}.{i+1}]",
                    "title": defn.get("reel_titles", [f"Reel {i+1}"])[i] if i < len(defn.get("reel_titles", [])) else f"{defn['title']} (Part {i+1})",
                    "hook_type": hook_types[i],
                    "hook": defn.get("reel_hooks", ["Discover the mystery."])[i] if i < len(defn.get("reel_hooks", [])) else "Watch to discover the decoded mystery."
                })

            # 5 Numbered Stories
            story_stickers = [
                ("link_youtube", "New Documentary Streaming! Tap to watch full episode."),
                ("poll", "Did you know this biblical revelation? [Yes] / [Mind Blown]"),
                ("link_substack", "Free Companion Study Guide & Scripture Chart Live on Substack!"),
                ("quiz", f"Bible Quiz of the Week on {defn['title']}"),
                ("countdown", "Next Episode Drops Sunday 10 AM!")
            ]
            stories = []
            for i in range(5):
                global_story_num = (w_num - 1) * 5 + (i + 1)
                stories.append({
                    "id": f"S-W{w_num:02d}.{i+1}",
                    "num": i + 1,
                    "global_num": global_story_num,
                    "day": reel_days[i],
                    "badge": f"Story #{global_story_num:03d} [W{w_num:02d}.{i+1}]",
                    "sticker_type": story_stickers[i][0],
                    "caption": story_stickers[i][1]
                })

            # 5 Numbered Community Tab Posts
            comm_types = [
                ("image_quote", "Scripture Quote & Visual Archetype"),
                ("4_choice_poll", "Interactive Theological Community Poll"),
                ("scroll_breakdown", "Ancient Scroll & Archaeological Discovery"),
                ("substack_link", "Mid-Week Deep Dive & Discussion Link"),
                ("discussion_prompt", "Weekend Reflection & Viewer Q&A Spotlight")
            ]
            comm_posts = []
            for i in range(5):
                global_comm_num = (w_num - 1) * 5 + (i + 1)
                comm_posts.append({
                    "id": f"CT-W{w_num:02d}.{i+1}",
                    "num": i + 1,
                    "global_num": global_comm_num,
                    "day": reel_days[i],
                    "badge": f"Community Post #{global_comm_num:03d}",
                    "post_type": comm_types[i][0],
                    "type_label": comm_types[i][1],
                    "prompt": defn.get("community_prompts", ["What was your favorite revelation?"])[i] if i < len(defn.get("community_prompts", [])) else f"Discuss {defn['title']}",
                    "options": ["Prophecy Fulfilled", "Christological Type", "Ancient Scroll Context", "Never Taught in Church"] if i == 1 else []
                })

            weeks.append({
                "week": w_num,
                "year": year,
                "quarter": quarter,
                "theme": defn.get("theme", "Biblical Mysteries Decoded"),
                "testament": defn.get("testament", "Old Testament"),
                "documentary": {
                    "id": f"DOC-W{w_num:02d}",
                    "title": defn["title"],
                    "duration": defn.get("duration", "30 min"),
                    "scriptures": defn.get("scriptures", []),
                    "christological_key": defn.get("christological_key", "Points to Christ as the fulfillment."),
                    "status": defn.get("status", "planned"),
                    "episode_folder": defn.get("episode_folder", ""),
                    "rel_path": defn.get("rel_path", ""),
                    "video_url": f"/api/media/{defn.get('rel_path')}" if defn.get("rel_path") else None,
                    "thumbnail_url": f"/api/thumbnail/{defn.get('rel_path')}" if defn.get("rel_path") else None
                },
                "substack": {
                    "pillar_id": f"SUB-W{w_num:02d}.A",
                    "pillar_title": defn.get("substack_title", f"{defn['title']}: Full Study Guide"),
                    "digest_id": f"SUB-W{w_num:02d}.B",
                    "digest_title": f"Mid-Week Q&A & Sacred Art: {defn['title']}",
                    "lead_magnet": "Free Printable Study Guide & Scripture Concordance Chart"
                },
                "reels": reels,
                "stories": stories,
                "community_posts": comm_posts
            })

        return {
            "franchise": "Bible Hidden Secrets Revealed",
            "curriculum_version": "2.0",
            "weeks": weeks
        }

story_map_manager = StoryMapManager()
