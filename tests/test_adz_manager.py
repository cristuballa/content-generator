"""Tests for C:\\Projects\\Adz-Video advertisement management and API endpoints."""
import os
import shutil
import unittest
from pathlib import Path

from core import adz_manager


class TestAdzManager(unittest.TestCase):
    def test_adz_directory_exists(self):
        d = adz_manager.get_adz_dir()
        self.assertTrue(d.exists())
        self.assertTrue(str(d).lower().startswith("c:\\projects\\adz-video"))

    def test_list_ad_videos(self):
        vids = adz_manager.list_ad_videos()
        self.assertIsInstance(vids, list)
        self.assertGreaterEqual(len(vids), 3)
        filenames = [v["filename"] for v in vids]
        self.assertIn("ad_outro_1.mp4", filenames)
        self.assertIn("ad_outro_2.mp4", filenames)
        self.assertIn("ad_outro_3.mp4", filenames)

        v1 = next(v for v in vids if v["filename"] == "ad_outro_1.mp4")
        self.assertIn("duration", v1)
        self.assertIn("size_mb", v1)
        self.assertIn("video_url", v1)
        self.assertIn("thumbnail_url", v1)
        self.assertTrue(v1["is_recommended"])

    def test_resolve_ad_video(self):
        p1 = adz_manager.resolve_ad_video(1)
        self.assertIsNotNone(p1)
        self.assertTrue(p1.exists())

        p2 = adz_manager.resolve_ad_video("ad_outro_2.mp4")
        self.assertIsNotNone(p2)
        self.assertTrue(p2.exists())
        self.assertEqual(p2.name, "ad_outro_2.mp4")

    def test_get_ad_thumbnail(self):
        thumb = adz_manager.get_or_create_thumbnail("ad_outro_1.mp4")
        self.assertIsNotNone(thumb)
        self.assertTrue(thumb.exists())
        self.assertGreater(thumb.stat().st_size, 500)

    def test_generate_reel_cli_arguments(self):
        import subprocess
        cmd = ["python", "scripts/generate_reel.py", "--help"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("--ads", res.stdout)
        self.assertIn("--combine-ad", res.stdout)
        self.assertIn("--remove-ad", res.stdout)


if __name__ == "__main__":
    unittest.main()
