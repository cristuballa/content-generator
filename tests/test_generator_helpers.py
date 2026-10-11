"""Books/merch line enforcement and stale-recording detection in the long-form and reel generators."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

import tests  # noqa: F401  (blocks network before core modules load)

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GENERATORS = [load("generate_video"), load("generate_reel")]


class BooksLineTests(unittest.TestCase):
    def test_old_long_form_line_is_upgraded(self):
        gv = load("generate_video")
        text = ("The blood speaks better things. If this study opened your eyes, go deeper. Our books and sacred art "
                "merch are linked in the bio and comments. Until next time, keep searching the Scriptures.")
        out = gv.ensure_books_cta(text)
        self.assertIn(gv.BOOKS_LINE, out)
        self.assertNotIn("If this study opened your eyes", out)
        self.assertTrue(out.endswith("keep searching the Scriptures."))

    def test_missing_long_form_line_goes_before_the_sign_off(self):
        gv = load("generate_video")
        body = "word " * 200
        out = gv.ensure_books_cta(body + "Until next time, keep searching the Scriptures.")
        self.assertIn(gv.BOOKS_LINE + " Until next time", out)

    def test_missing_long_form_line_is_appended_without_a_sign_off(self):
        gv = load("generate_video")
        out = gv.ensure_books_cta("A short video about the Passover lamb.")
        self.assertTrue(out.endswith(gv.BOOKS_LINE))

    def test_current_long_form_line_is_left_alone(self):
        gv = load("generate_video")
        text = "Light before the sun. " + gv.BOOKS_LINE + " Until next time."
        self.assertEqual(gv.ensure_books_cta(text), text)

    def test_reel_strips_books_cta(self):
        gr = load("generate_reel")
        # Ensure any residual books line is completely stripped from clean reel narration
        with_books = (
            "Watch the full episode on our channel, and save this so you don't lose this scripture. "
            "If this blew your mind, it's just one part of what we uncover in our books. "
            "They're linked in the bio and comments, along with our sacred art merch. "
            "Follow for more secrets hidden in Scripture."
        )
        clean = gr.strip_books_cta(with_books)
        self.assertNotIn("If this blew your mind", clean)
        self.assertNotIn("linked in the bio and comments", clean)
        self.assertEqual(
            clean,
            "Watch the full episode on our channel, and save this so you don't lose this scripture. "
            "Follow for more secrets hidden in Scripture."
        )


class StaleRecordingTests(unittest.TestCase):
    def test_changed_script_moves_old_audio_aside(self):
        for g in GENERATORS:
            with tempfile.TemporaryDirectory() as tmp:
                temp = Path(tmp)
                (temp / "voice_script.txt").write_text("old narration", encoding="utf-8")
                (temp / "ep_voice_raw.mp3").write_bytes(b"x")
                (temp / "ep_voice_raw.mp3_chunks").mkdir()
                self.assertFalse(g.cached_script_differs(temp / "voice_script.txt", "old narration"))
                self.assertTrue(g.cached_script_differs(temp / "voice_script.txt", "new narration"))
                g.retire_stale_audio(temp, [temp / "ep_voice_raw.mp3", temp / "ep_voice_raw.mp3_chunks", temp / "missing.json"])
                self.assertFalse((temp / "ep_voice_raw.mp3").exists())
                self.assertTrue((temp / "_previous" / "ep_voice_raw.mp3").exists())
                self.assertTrue((temp / "_previous" / "ep_voice_raw.mp3_chunks").is_dir())

    def test_no_cached_script_means_no_change(self):
        for g in GENERATORS:
            with tempfile.TemporaryDirectory() as tmp:
                self.assertFalse(g.cached_script_differs(Path(tmp) / "voice_script.txt", "anything"))


if __name__ == "__main__":
    unittest.main()
