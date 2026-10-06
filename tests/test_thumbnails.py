"""Thumbnail selection and preparation: the chosen thumbnail.jpg wins, YouTube gets a JPEG under 2 MB,
and older reels' metadata.txt gives a fitting headline/subtitle."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

import tests  # noqa: F401  (blocks network before core modules load)
from PIL import Image
from core.social_dispatcher import SocialDispatcher
from core.thumbnails import YOUTUBE_MAX_BYTES, jpeg_copy

_spec = importlib.util.spec_from_file_location(
    "generate_reel", Path(__file__).resolve().parent.parent / "scripts" / "generate_reel.py")
gr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gr)


class ThumbnailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "W02" / "long_form" / "01_ep"
        self.dir.mkdir(parents=True)
        (self.dir / "video_final_16x9.mp4").write_bytes(b"x")

    def image(self, name, size=(64, 36), color=(10, 20, 30)):
        p = self.dir / name
        Image.new("RGB", size, color).save(p)
        return p

    def test_chosen_thumbnail_wins_over_option_drafts(self):
        self.image("thumbnail_option_1.jpg")
        chosen = self.image("thumbnail.jpg")
        found = SocialDispatcher().find_custom_thumbnail(Path(self.tmp.name), "W02/long_form/01_ep/video_final_16x9.mp4")
        self.assertEqual(found, chosen)

    def test_option_one_is_used_when_there_is_no_chosen_thumbnail(self):
        option = self.image("thumbnail_option_1.jpg")
        found = SocialDispatcher().find_custom_thumbnail(Path(self.tmp.name), "W02/long_form/01_ep/video_final_16x9.mp4")
        self.assertEqual(found, option)

    def test_small_jpeg_is_used_as_is(self):
        p = self.image("thumbnail.jpg")
        self.assertEqual(jpeg_copy(p, YOUTUBE_MAX_BYTES), (p, False))

    def test_large_png_becomes_a_jpeg_under_the_youtube_limit(self):
        p = self.dir / "thumbnail.png"
        Image.frombytes("RGB", (1920, 1080), os.urandom(1920 * 1080 * 3)).save(p)  # noise: a large PNG
        self.assertGreater(p.stat().st_size, YOUTUBE_MAX_BYTES)
        out, is_temp = jpeg_copy(p, YOUTUBE_MAX_BYTES)
        try:
            self.assertTrue(is_temp)
            self.assertLessEqual(out.stat().st_size, YOUTUBE_MAX_BYTES)
            with Image.open(out) as im:
                self.assertEqual(im.format, "JPEG")
        finally:
            out.unlink()

    def test_legacy_reel_title_split_into_headline_and_subtitle(self):
        txt = self.dir / "metadata.txt"
        txt.write_text("TITLE: The First Prophecy of Jesus — Hidden in a CURSE on a Snake | Bible Secrets #51\n"
                       "HOOK: THE FIRST PROPHECY\nDESCRIPTION:\nIt is in Genesis 3:15 — the serpent's sentence.\n\nHASHTAGS:\n",
                       encoding="utf-8")
        m = gr.legacy_reel_metadata(txt)
        self.assertEqual(m["title"], "The First Prophecy of Jesus")
        self.assertEqual(m["thumbnail_kicker"], "HIDDEN IN A CURSE ON A SNAKE")
        self.assertEqual(m["thumbnail_scripture"], "GENESIS 3:15")

    def test_long_legacy_title_without_dash_gets_a_subtitle(self):
        txt = self.dir / "metadata.txt"
        txt.write_text("TITLE: The Thief on the Cross Destroys Every Religious System in One Sentence | Bible Secrets #84\n",
                       encoding="utf-8")
        m = gr.legacy_reel_metadata(txt)
        self.assertLessEqual(len(m["title"]), 24)
        self.assertTrue(m["thumbnail_kicker"])


if __name__ == "__main__":
    unittest.main()
