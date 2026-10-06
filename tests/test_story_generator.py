"""Story folder lookup for weeks with 5 or 15 stories (3 a day)."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

import tests  # noqa: F401  (blocks network before core modules load)

_spec = importlib.util.spec_from_file_location(
    "generate_story", Path(__file__).resolve().parent.parent / "scripts" / "generate_story.py")
gs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gs)


class StoryFolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.week = Path(self.tmp.name) / "W02"
        names = ["01_dawn", "02_bara", "03_six_day_cosmic_temple", "04_imago_dei", "05_sabbath", "temp"]
        names += [f"{n:02d}_extra_{n}" for n in range(6, 16)]
        for name in names:
            (self.week / "stories" / name).mkdir(parents=True)
        for r in range(1, 6):
            images = self.week / "reels" / f"0{r}_reel" / "images"
            images.mkdir(parents=True)
            for i in range(1, 9):
                (images / f"reel{r}_dyn_{i}.png").write_bytes(b"x")
            (images / f"reel{r}_card_hook.png").write_bytes(b"x")

    def test_temple_is_a_story_not_a_temp_folder(self):
        self.assertEqual(gs.find_story_folder(self.week, 3).name, "03_six_day_cosmic_temple")
        self.assertEqual(gs.find_story_folder(self.week, 4).name, "04_imago_dei")

    def test_week_counts_all_fifteen_stories(self):
        self.assertEqual(gs.count_week_stories(self.week), 15)
        self.assertEqual(gs.find_story_folder(self.week, 10).name, "10_extra_10")
        self.assertEqual(gs.find_story_folder(self.week, 15).name, "15_extra_15")

    def test_extra_stories_borrow_their_days_reel_art(self):
        story = self.week / "stories" / "08_extra_8"
        bgs = gs.get_story_background_candidates(story, self.week, 8, reel_num=2)
        self.assertTrue(bgs)
        self.assertTrue(all(p.parent.parent.name == "02_reel" for p in bgs))
        self.assertFalse(any("card" in p.name for p in bgs))
        # Two stories on the same reel start on different images
        other = gs.get_story_background_candidates(self.week / "stories" / "09_extra_9", self.week, 9, reel_num=2)
        self.assertNotEqual(bgs[0], other[0])

    def test_daily_story_uses_its_own_reel(self):
        bgs = gs.get_story_background_candidates(self.week / "stories" / "04_imago_dei", self.week, 4)
        self.assertEqual(bgs[0].name, "reel4_dyn_1.png")


if __name__ == "__main__":
    unittest.main()
