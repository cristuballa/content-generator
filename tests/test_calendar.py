import asyncio
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


if __name__ == "__main__":
    unittest.main()
