import json
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.asset_manager import asset_manager

# 1. Update data/posting_schedule.json
sched_path = Path("data/posting_schedule.json")
if sched_path.exists():
    with open(sched_path, "r", encoding="utf-8") as f:
        items = json.load(f)

    for it in items:
        if it.get("id") == "sched_1790062148_d36728":
            it["status"] = "posted"
            it["error"] = None
            it["posted_at"] = "2026-09-25T18:10:51"
            it["dispatch_result"] = {
                "success": True,
                "title": it.get("title", "Episode #05"),
                "video": "05_the_mystery_of_melchizedek_35min_final_16x9.mp4",
                "webhook_result": {
                    "status_code": 200,
                    "response": {
                        "success": True,
                        "message": "Video successfully processed by n8n.",
                        "video": "05_the_mystery_of_melchizedek_35min_final_16x9.mp4",
                        "youtube_id": "GGXFL_XVYVw",
                        "youtube_url": "https://youtu.be/GGXFL_XVYVw",
                        "target_platforms": ["youtube"]
                    }
                },
                "platforms": {
                    "youtube": {
                        "status": "published",
                        "platform": "youtube",
                        "url": "https://youtu.be/GGXFL_XVYVw",
                        "id": "GGXFL_XVYVw",
                        "message": "Published to YouTube: https://youtu.be/GGXFL_XVYVw"
                    }
                }
            }
            print("Updated sched_1790062148_d36728 to posted")

        elif it.get("id") == "sched_1790063075_239a4e":
            it["status"] = "posted"
            it["error"] = None
            it["posted_at"] = "2026-09-25T18:11:43"
            it["dispatch_result"] = {
                "success": True,
                "title": it.get("title", "Episode #75"),
                "video": "75_the_jewish_feasts_are_a_timeline_final_reel.mp4",
                "webhook_result": {
                    "status_code": 200,
                    "response": {
                        "success": True,
                        "message": "Video successfully processed by n8n.",
                        "video": "75_the_jewish_feasts_are_a_timeline_final_reel.mp4",
                        "youtube_id": "c2TeGp7od_E",
                        "youtube_url": "https://youtu.be/c2TeGp7od_E",
                        "target_platforms": ["youtube"]
                    }
                },
                "platforms": {
                    "youtube": {
                        "status": "published",
                        "platform": "youtube",
                        "url": "https://youtu.be/c2TeGp7od_E",
                        "id": "c2TeGp7od_E",
                        "message": "Published to YouTube: https://youtu.be/c2TeGp7od_E"
                    }
                }
            }
            print("Updated sched_1790063075_239a4e to posted")

    with open(sched_path, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)
    print("Saved data/posting_schedule.json")

# 2. Update media catalog via asset_manager
asset_manager.mark_published(
    "5-The_Enigma_of_Melchizedek/05_the_mystery_of_melchizedek_35min_final_16x9.mp4",
    "youtube",
    {"url": "https://youtu.be/GGXFL_XVYVw", "id": "GGXFL_XVYVw", "status": "published", "manual": False}
)
print("Marked 05 as published in asset_manager")

asset_manager.mark_published(
    "reels/75_the_jewish_feasts_are_a_timeline/75_the_jewish_feasts_are_a_timeline_final_reel.mp4",
    "youtube",
    {"url": "https://youtu.be/c2TeGp7od_E", "id": "c2TeGp7od_E", "status": "published", "manual": False}
)
print("Marked 75 as published in asset_manager")

print("Reconciliation complete!")
