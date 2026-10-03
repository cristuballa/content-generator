"""
Format routing + dispatch, following the plan's verification step: a Reel, a long-form video of
30 minutes or less, and one over 30 minutes, in dry-run and (with mocked uploaders) live mode.
"""

import asyncio
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (blocks network before core modules load)
from core.config import config_manager
from core.social_dispatcher import SocialDispatcher, social_dispatcher

PLATFORMS = ("youtube", "facebook", "instagram", "threads", "tiktok", "x")
REEL = ("W01/reels/01_genesis/final_reel.mp4", "1080x1920", 45)
STORY = ("W01/stories/01_teaser/story_video.mp4", "1080x1920", 20)
LONG_UNDER_30M = ("W03/long_form/doc_final_16x9.mp4", "1920x1080", 25 * 60)
LONG_OVER_30M = ("W03/long_form/doc_final_16x9.mp4", "1920x1080", 34 * 60)


def run_publish(video, platforms, dry_run=False, disabled=(), scheduled_iso=None):
    """Runs publish_video against a temp project with every uploader and data file mocked out."""
    rel_path, resolution, duration_sec = video
    with tempfile.TemporaryDirectory() as tmp:
        video_file = Path(tmp) / rel_path
        video_file.parent.mkdir(parents=True)
        video_file.write_bytes(b"\0" * 16)

        cfg = {"dry_run": dry_run, **{p: {"enabled": p not in disabled} for p in PLATFORMS}}
        assets = mock.Mock()
        assets.get_asset_record.return_value = {"published": {}}
        assets.get_media_info.return_value = {
            "duration": f"{duration_sec}s", "duration_sec": duration_sec, "resolution": resolution
        }
        meta = {"title": "Test Video", "description": "A test video.", "tags": ["Bible"], "hashtags_string": "#Bible"}
        calls = []

        def fake_dispatch(**kwargs):
            calls.append({**kwargs, "thread": threading.current_thread()})
            return {"status": "published", "platform": kwargs["platform"], "url": f"https://example.test/{kwargs['platform']}"}

        with mock.patch("core.social_dispatcher.asset_manager", assets), \
                mock.patch.object(config_manager, "get_project_social_config", return_value=cfg), \
                mock.patch.object(SocialDispatcher, "extract_metadata_for_video", return_value=meta), \
                mock.patch.object(SocialDispatcher, "_dispatch_to_platform", side_effect=fake_dispatch), \
                mock.patch("core.notifier.notify_desktop"):
            result = asyncio.run(social_dispatcher.publish_video(
                tmp, rel_path, platforms=list(platforms), scheduled_datetime_iso=scheduled_iso
            ))
    return result, calls, assets


def dispatched(calls):
    return [c["platform"] for c in calls]


class ClassifyVideoFormatTests(unittest.TestCase):
    def check(self, resolution, duration, rel_path, expected):
        self.assertEqual(SocialDispatcher.classify_video_format(resolution, duration, rel_path)["format"], expected)

    def test_vertical_reel_is_short(self):
        self.check("1080x1920", 45, REEL[0], "short")

    def test_landscape_is_long_form_even_in_reels_folder(self):
        self.check("1920x1080", 60, REEL[0], "long_form")

    def test_vertical_in_stories_folder_is_story(self):
        self.check("1080x1920", 20, STORY[0], "story")
        self.check("1080x1920", 20, r"W01\stories\01_teaser\story_video.mp4", "story")

    def test_square(self):
        self.check("1080x1080", 120, "W01/clip.mp4", "short")
        self.check("1080x1080", 600, "W01/clip.mp4", "long_form")

    def test_unknown_resolution_falls_back_to_path_and_duration(self):
        self.check(None, 40, "W01/reels/a.mp4", "short")
        self.check(None, 600, "W01/long_form/a.mp4", "long_form")


class PlatformRoutingTests(unittest.TestCase):
    ALL_ON = {p: {"enabled": True} for p in PLATFORMS}

    def eligible(self, video_format, duration, cfg=None):
        routes = SocialDispatcher.get_platform_routing(video_format, duration, cfg or self.ALL_ON)
        return {p for p, r in routes.items() if r["eligible"]}

    def test_long_form_over_30_minutes(self):
        self.assertEqual(self.eligible("long_form", LONG_OVER_30M[2]), {"youtube", "facebook"})

    def test_long_form_up_to_30_minutes_adds_tiktok(self):
        self.assertEqual(self.eligible("long_form", LONG_UNDER_30M[2]), {"youtube", "facebook", "tiktok"})

    def test_reel_goes_everywhere_except_x(self):
        self.assertEqual(self.eligible("short", 45), {"youtube", "facebook", "instagram", "threads", "tiktok"})

    def test_story_over_60s_skips_instagram(self):
        self.assertNotIn("instagram", self.eligible("story", 75))

    def test_disabled_platform_is_ineligible(self):
        cfg = {**self.ALL_ON, "tiktok": {"enabled": False}}
        routes = SocialDispatcher.get_platform_routing("short", 45, cfg)
        self.assertFalse(routes["tiktok"]["eligible"])
        self.assertIn("disabled", routes["tiktok"]["reason"])

    def test_labels(self):
        routes = SocialDispatcher.get_platform_routing("short", 45, self.ALL_ON)
        self.assertEqual(routes["youtube"]["label"], "YouTube Shorts")
        self.assertEqual(routes["facebook"]["label"], "Facebook Reels")
        routes = SocialDispatcher.get_platform_routing("long_form", 1500, self.ALL_ON)
        self.assertEqual(routes["youtube"]["label"], "YouTube Standard")
        self.assertEqual(routes["facebook"]["label"], "Facebook Long Video")


class PublishVideoTests(unittest.TestCase):
    def test_dry_run_uploads_nothing_and_keeps_history_clean(self):
        result, calls, assets = run_publish(REEL, PLATFORMS, dry_run=True)
        self.assertTrue(result["success"])
        self.assertEqual(calls, [])
        assets.mark_published.assert_not_called()
        for plat in ("youtube", "facebook", "instagram", "threads", "tiktok"):
            self.assertEqual(result["platforms"][plat]["status"], "simulated")
        self.assertIn("Dry run", result["message"])

    def test_reel_routes_to_short_formats(self):
        result, calls, assets = run_publish(REEL, PLATFORMS)
        self.assertEqual(dispatched(calls), ["youtube", "facebook", "instagram", "threads", "tiktok"])
        self.assertTrue(all(c["is_short"] and not c["is_story"] for c in calls))
        self.assertEqual(result["platforms"]["x"]["status"], "skipped")
        self.assertEqual(assets.mark_published.call_count, 5)

    def test_long_form_under_30_minutes(self):
        _, calls, _ = run_publish(LONG_UNDER_30M, PLATFORMS)
        self.assertEqual(dispatched(calls), ["youtube", "facebook", "tiktok"])
        self.assertTrue(all(not c["is_short"] for c in calls))

    def test_long_form_over_30_minutes_skips_tiktok(self):
        result, calls, assets = run_publish(LONG_OVER_30M, PLATFORMS)
        self.assertEqual(dispatched(calls), ["youtube", "facebook"])
        for plat in ("instagram", "threads", "tiktok", "x"):
            self.assertEqual(result["platforms"][plat]["status"], "skipped")
        self.assertEqual(sorted(c.args[1] for c in assets.mark_published.call_args_list), ["facebook", "youtube"])

    def test_story_uses_story_upload(self):
        _, calls, _ = run_publish(STORY, ("facebook", "instagram"))
        self.assertEqual(dispatched(calls), ["facebook", "instagram"])
        self.assertTrue(all(c["is_story"] for c in calls))

    def test_scheduled_story_is_not_cloud_staged_on_meta(self):
        result, calls, _ = run_publish(STORY, ("youtube", "facebook", "instagram"), scheduled_iso="2030-01-01T10:00:00")
        self.assertEqual(dispatched(calls), ["youtube"])
        self.assertIn("can't be cloud-scheduled", result["platforms"]["facebook"]["message"])

    def test_disabled_platform_is_skipped_even_when_requested(self):
        result, calls, _ = run_publish(REEL, ("youtube", "tiktok"), disabled=("tiktok",))
        self.assertEqual(dispatched(calls), ["youtube"])
        self.assertIn("disabled", result["platforms"]["tiktok"]["message"])

    def test_uploads_run_off_the_event_loop_thread(self):
        _, calls, _ = run_publish(REEL, ("youtube",))
        self.assertIsNot(calls[0]["thread"], threading.main_thread())


if __name__ == "__main__":
    unittest.main()
