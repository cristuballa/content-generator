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
        for g in GENERATORS:
            text = ("The blood speaks better things. If this study opened your eyes, go deeper. Our books and sacred art "
                    "merch are linked in the bio and comments. Until next time, keep searching the Scriptures.")
            out = g.ensure_books_cta(text)
            self.assertIn(g.BOOKS_LINE, out)
            self.assertNotIn("If this study opened your eyes", out)
            self.assertTrue(out.endswith("keep searching the Scriptures."))

    def test_old_reel_line_is_upgraded(self):
        for g in GENERATORS:
            text = "Christ is the Lamb. Our books and sacred art merch are linked in the bio and comments. Follow for more secrets hidden in Scripture."
            out = g.ensure_books_cta(text)
            self.assertEqual(out.count("linked in the bio and comments"), 1)
            self.assertTrue(out.endswith(g.BOOKS_LINE + " Follow for more secrets hidden in Scripture."))

    def test_missing_line_goes_before_the_sign_off(self):
        for g in GENERATORS:
            body = "word " * 200
            out = g.ensure_books_cta(body + "Until next time, keep searching the Scriptures.")
            self.assertIn(g.BOOKS_LINE + " Until next time", out)

    def test_missing_line_is_appended_without_a_sign_off(self):
        for g in GENERATORS:
            out = g.ensure_books_cta("A short reel about the Passover lamb.")
            self.assertTrue(out.endswith(g.BOOKS_LINE))

    def test_current_line_is_left_alone(self):
        for g in GENERATORS:
            text = "Light before the sun. " + g.BOOKS_LINE + " Until next time."
            self.assertEqual(g.ensure_books_cta(text), text)


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
