import asyncio
import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (blocks network before core modules load)
from core.calendar_manager import CalendarManager


def run_due_post(platforms, dispatch_result):
    """Runs one overdue scheduled post through execute_due_posts with a fake dispatcher."""
    with tempfile.TemporaryDirectory() as tmp:
        schedule = Path(tmp) / "schedule.json"
        schedule.write_text(json.dumps([{
            "id": "p1",
            "status": "scheduled",
            "project_path": tmp,
            "video_rel_path": "W01/reels/01/final_reel.mp4",
            "platforms": platforms,
            "scheduled_datetime_iso": "2000-01-01T00:00:00"
        }]), encoding="utf-8")
        calendar = CalendarManager(schedule_file=schedule)
        assets = mock.Mock()
        assets.get_asset_record.return_value = {"published": {}}
        dispatcher = mock.Mock()
        dispatcher.publish_video = mock.AsyncMock(return_value=dispatch_result)
        with mock.patch("core.calendar_manager.asset_manager", assets):
            executed = asyncio.run(calendar.execute_due_posts(dispatcher))
    return executed[0], assets


class ExecuteDuePostsTests(unittest.TestCase):
    def test_skipped_platforms_do_not_fail_the_post(self):
        item, assets = run_due_post(["youtube", "x"], {
            "success": True,
            "platforms": {
                "youtube": {"status": "published", "url": "https://youtu.be/a"},
                "x": {"status": "skipped", "message": "Skipped: X posting is not implemented yet."}
            }
        })
        self.assertEqual(item["status"], "posted")
        self.assertIn("x", item["skipped_platforms"])
        # Only the platform that really went out is recorded as posted
        assets.update_social_posted_batch.assert_called_once_with("W01/reels/01/final_reel.mp4", ["youtube"])

    def test_dry_run_is_not_recorded_as_posted(self):
        item, assets = run_due_post(["youtube"], {
            "success": True,
            "dry_run": True,
            "platforms": {"youtube": {"status": "simulated", "simulated": True}}
        })
        self.assertEqual(item["status"], "failed")
        self.assertIn("Dry run", item["error"])
        assets.mark_published.assert_not_called()
        assets.update_social_posted_batch.assert_not_called()

    def test_everything_skipped_is_a_failure_with_reasons(self):
        item, _ = run_due_post(["instagram"], {
            "success": True,
            "skipped": True,
            "platforms": {"instagram": {"status": "skipped", "message": "Skipped: landscape long-form video."}}
        })
        self.assertEqual(item["status"], "failed")
        self.assertIn("landscape long-form", item["error"])

    def test_partial_failure_reports_the_platform_error(self):
        item, _ = run_due_post(["youtube", "facebook"], {
            "success": True,
            "platforms": {
                "youtube": {"status": "published"},
                "facebook": {"status": "failed", "error": "Token expired"}
            }
        })
        self.assertEqual(item["status"], "failed")
        self.assertIn("facebook: Token expired", item["error"])


class StorySlotTests(unittest.TestCase):
    """Stories get 3 daily slots of their own, reels their own reel slots; long-form keeps the 1-a-day rule."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.calendar = CalendarManager(schedule_file=self.project / "schedule.json")
        cfg = {"default_posting_time": "18:00", "story_posting_times": ["08:00", "13:00", "20:00"]}
        patcher = mock.patch("core.calendar_manager.config_manager")
        self.config = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)
        self.config.get_project_social_config.return_value = cfg
        self.start = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

    def story(self, num, post_time=None, day=None):
        folder = self.project / "W01" / "stories" / f"{num:02d}_story"
        folder.mkdir(parents=True, exist_ok=True)
        if post_time or day:
            meta = {k: v for k, v in (("post_time", post_time), ("day", day)) if v}
            (folder / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
        return f"W01/stories/{num:02d}_story/story_video_final.mp4"

    def book(self, rel, slot):
        items = json.loads((self.project / "schedule.json").read_text(encoding="utf-8")) \
            if (self.project / "schedule.json").exists() else []
        items.append({"id": rel, "project_path": str(self.project), "video_rel_path": rel, "status": "scheduled",
                      "platforms": ["instagram"], "scheduled_date": slot["date"], "scheduled_time": slot["time"]})
        (self.project / "schedule.json").write_text(json.dumps(items), encoding="utf-8")

    def next_slot(self, rel):
        return self.calendar.find_next_available_slot(str(self.project), ["instagram"], start_date_str=self.start,
                                                      video_rel_path=rel)

    def test_three_stories_fill_one_day_then_move_on(self):
        slots = []
        for n in range(1, 5):
            rel = self.story(n)
            slot = self.next_slot(rel)
            self.book(rel, slot)
            slots.append((slot["date"], slot["time"]))
        self.assertEqual([t for _, t in slots[:3]], ["08:00", "13:00", "20:00"])
        self.assertEqual(len({d for d, _ in slots[:3]}), 1)
        self.assertNotEqual(slots[3][0], slots[0][0])
        self.assertEqual(slots[3][1], "08:00")

    def test_story_keeps_its_preferred_time(self):
        evening = [self.story(n, "20:00") for n in (1, 2)]
        first = self.next_slot(evening[0])
        self.book(evening[0], first)
        second = self.next_slot(evening[1])
        self.assertEqual((first["time"], second["time"]), ("20:00", "20:00"))
        self.assertNotEqual(first["date"], second["date"])
        # The morning slot of the first day is still free for a morning story
        morning = self.next_slot(self.story(3, "08:00"))
        self.assertEqual((morning["date"], morning["time"]), (first["date"], "08:00"))

    def test_story_keeps_its_weekday_next_to_its_reel(self):
        tuesday = self.next_slot(self.story(1, "08:00", "Tuesday"))
        self.assertEqual((datetime.date.fromisoformat(tuesday["date"]).weekday(), tuesday["time"]), (1, "08:00"))
        self.book("W01/stories/01_story/story_video_final.mp4", tuesday)
        # The same Tuesday morning slot is taken: the next Tuesday, never a Wednesday
        again = self.next_slot(self.story(2, "08:00", "Tue"))
        self.assertEqual((datetime.date.fromisoformat(again["date"]) - datetime.date.fromisoformat(tuesday["date"])).days, 7)

    def test_stories_and_reels_do_not_block_each_other(self):
        reel = "W01/reels/01_reel/final_reel.mp4"
        reel_slot = self.calendar.find_next_available_slot(str(self.project), ["instagram"], start_date_str=self.start,
                                                           video_rel_path=reel)
        self.book(reel, reel_slot)
        story_slot = self.next_slot(self.story(1))
        self.assertEqual(story_slot["date"], reel_slot["date"])
        self.book("W01/stories/01_story/story_video_final.mp4", story_slot)
        next_reel = self.calendar.find_next_available_slot(str(self.project), ["instagram"], start_date_str=self.start,
                                                           video_rel_path="W01/reels/02_reel/final_reel.mp4")
        # Both reels want the first reel slot of the day (07:30 by default), so the second goes to another day
        self.assertNotEqual(next_reel["date"], reel_slot["date"])
        self.assertEqual((reel_slot["time"], next_reel["time"]), ("07:30", "07:30"))


if __name__ == "__main__":
    unittest.main()
