"""generate_reel.py: narration-timed scenes (at most 20 pictures), prompts written from each scene's words, pictures
shown while their words are heard; reels rendered earlier keep their pictures."""
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (blocks network before core modules load)
from PIL import Image

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(f"_rs_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gr = load("generate_reel")
gvm = gr.video_gen()


def _no_real_cli(*args, **kwargs):
    raise AssertionError("a test tried to run a real Claude/Gemini CLI")


gvm._run_cli = _no_real_cli

REEL_WORD_SEC = 0.46  # ~130 words a minute


def reel_script(sentences=24, words=10, commas=False):
    out = []
    for i in range(sentences):
        body = ["word"] * (words - 1)
        if commas:
            body[words // 2] = "word,"
        out.append(" ".join(body + [f"end{i}."]))
    return " ".join(out)


def write_transcript(path, text, word_sec=REEL_WORD_SEC):
    words = [{"word": " " + w, "start": round(i * word_sec, 2), "end": round(i * word_sec + word_sec - 0.05, 2)}
             for i, w in enumerate(text.split())]
    data = {"segments": [{"start": 0.0, "end": words[-1]["end"], "words": words}]}
    Path(path).write_text(json.dumps(data), encoding="utf-8")
    return data, words[-1]["end"]


def good_prompt(sid, by="claude"):
    return f"A towering angelic guardian with vast wings standing on a holy mountain at night for {sid} by {by}"


class ReelSplitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name) / "tr.json"

    def tearDown(self):
        self.tmp.cleanup()

    def split(self, text):
        _, total = write_transcript(self.t, text)
        target, split = gr.reel_split(total)
        return gvm.plan_scenes_from_transcript(text, self.t, total, target, **split), total

    def test_never_more_than_20_scenes(self):
        text = reel_script(sentences=48, words=5)  # 240 words in 48 short sentences
        scenes, total = self.split(text)
        self.assertLessEqual(len(scenes), gr.REEL_MAX_SCENES)
        self.assertGreaterEqual(len(scenes), 15)
        self.assertEqual(" ".join(sc["text"] for sc in scenes), text)  # every word in exactly one scene
        self.assertTrue(all(sc["text"].endswith(".") for sc in scenes))
        self.assertEqual(scenes[-1]["end"], round(total, 2))

    def test_fewer_scenes_when_the_narration_has_fewer_beats(self):
        text = reel_script(sentences=12, words=20)  # 12 long sentences, no commas
        scenes, _ = self.split(text)
        self.assertEqual(len(scenes), 12)

    def test_script_plan_uses_the_reel_pace(self):
        text = reel_script(sentences=24, words=10)
        target, split = gr.reel_split(len(text.split()) / (gr.REEL_WPM / 60))
        scenes = gvm.plan_scenes_from_script(text, target, wpm=gr.REEL_WPM, **split)
        self.assertLessEqual(len(scenes), 20)
        self.assertAlmostEqual(scenes[-1]["end"], len(text.split()) / (gr.REEL_WPM / 60), delta=1.0)

    def test_reel_prompt_rules(self):
        guide = gr.reel_prompt_guide(gvm)
        self.assertIn("vertical short-form Bible reel", guide)
        self.assertIn("9:16 vertical frame", guide)
        self.assertIn(gr.REEL_LOOK_RULE, guide)
        self.assertNotIn("{look}", guide)
        self.assertNotIn(gvm.HOUSE_LOOK_RULE, guide)  # reels keep their own look
        self.assertIn("Never write cherub", guide)

    def test_timeline_follows_the_plan(self):
        plan = {"scenes": [{"id": "scene_001", "start": 0.4, "end": 5.1}, {"id": "scene_002", "start": 5.1, "end": 9.8}]}
        scenes = [{"id": "scene_001", "motion": "a"}, {"id": "scene_002", "motion": "b"}]
        tl = gr.reel_timeline(scenes, plan, 10.5)
        self.assertEqual([(t["start"], t["end"]) for t in tl], [(0.0, 5.1), (5.1, 10.5)])


class ReelRenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.reel = Path(self.tmp.name) / "W05" / "reels" / "mon_1_test_reel"
        self.reel.mkdir(parents=True)
        (self.reel / "script.txt").write_text(reel_script(sentences=24, words=10), encoding="utf-8")
        (self.reel / "metadata.json").write_text(json.dumps({"title": "Test Reel", "global_episode": 401}),
                                                 encoding="utf-8")
        self.recordings = []
        self.drawn = []

        def fake_voice(text, temp_dir, name):
            self.recordings.append(text)
            data, total = write_transcript(Path(temp_dir) / f"{name}_transcript.json", text)
            return Path(temp_dir) / f"{name}_master_soundtrack.wav", data, total

        def fake_draw(prompt, scene_id, images_dir, custom_image=None, force=False):
            images_dir.mkdir(parents=True, exist_ok=True)
            img = images_dir / f"{scene_id}.png"
            if not img.exists() or force:
                self.drawn.append((scene_id, prompt))
                Image.new("RGB", (9, 16)).save(img)
            return img

        thumbs = types.ModuleType("reel_thumbnail_builder")
        thumbs.generate_composite_reel_thumbnail = lambda **kw: Image.new("RGB", (9, 16)).save(kw["out_path"])
        self.patches = [
            mock.patch.object(gr, "synthesize_and_align_audio", side_effect=fake_voice),
            mock.patch.object(gr, "generate_scene_image", side_effect=fake_draw),
            mock.patch.object(gr, "generate_text_card", return_value=None),
            mock.patch.dict(sys.modules, {"reel_thumbnail_builder": thumbs}),
            mock.patch.object(gr, "PROJECT_DIR", Path(self.tmp.name)),
            mock.patch.object(gvm, "free_comfyui_memory"),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def fill(self, plan, ep_p, writers, guide=None, extra_context=""):
        self.writer_call = {"guide": guide, "extra": extra_context}
        for sc in plan["scenes"]:
            sc["prompt"] = sc["prompt"] or good_prompt(sc["id"])
        (ep_p / gvm.SCENE_PLAN_FILE).write_text(json.dumps(plan), encoding="utf-8")
        return []

    def render(self, **kw):
        return gr.render_reel(week_num=5, reel_num=1, target_dir=self.reel, **kw)

    def plan(self):
        return json.loads((self.reel / gvm.SCENE_PLAN_FILE).read_text(encoding="utf-8"))

    class Stop(Exception):
        pass

    def render_until_frames(self, **kw):
        """Runs a full render up to the frame loop; returns the timeline it would play."""
        seen = {}
        real = gr.reel_timeline

        def capture(*a):
            seen["timeline"] = real(*a)
            return seen["timeline"]

        with mock.patch.object(gr, "reel_timeline", side_effect=capture), \
                mock.patch.object(gr, "load_chunked_captions", side_effect=self.Stop):
            with self.assertRaises(self.Stop):
                self.render(force_rebuild=True, **kw)
        return seen["timeline"]

    def test_voice_first_then_prompts_then_pictures_on_their_words(self):
        with mock.patch.object(gvm, "prompt_writer_order", return_value=["claude"]), \
                mock.patch.object(gvm, "write_scene_prompts_with_ai", side_effect=self.fill):
            timeline = self.render_until_frames()
        self.assertEqual(len(self.recordings), 1)
        plan = self.plan()
        self.assertEqual(plan["timing"], "recorded")
        self.assertLessEqual(len(plan["scenes"]), 20)
        self.assertEqual([d[0] for d in self.drawn], [sc["id"] for sc in plan["scenes"]])
        self.assertTrue(all(gr.REEL_IMAGE_STYLE in prompt for _, prompt in self.drawn))
        self.assertIn("vertical short-form Bible reel", self.writer_call["guide"])
        self.assertEqual([t["id"] for t in timeline], [sc["id"] for sc in plan["scenes"]])
        for t, sc in zip(timeline[1:], plan["scenes"][1:]):
            self.assertAlmostEqual(t["start"], sc["words"][0] * REEL_WORD_SEC, places=2)  # on its first word

    def test_pauses_for_prompts_when_no_writer_can(self):
        with mock.patch.object(gvm, "prompt_writer_order", return_value=[]):
            self.assertEqual(self.render(force_rebuild=True), "NEEDS_PROMPTS")
        self.assertEqual(len(self.recordings), 1)
        self.assertEqual(self.drawn, [])
        self.assertTrue(all(not sc["prompt"] for sc in self.plan()["scenes"]))

    def test_plan_ahead_then_draw_then_voice_keeps_prompts_and_pictures(self):
        with mock.patch.object(gvm, "prompt_writer_order", return_value=["claude"]), \
                mock.patch.object(gvm, "write_scene_prompts_with_ai", side_effect=self.fill):
            self.assertEqual(self.render(plan_only=True), "PLANNED")
            self.assertEqual(self.recordings, [])
            planned = self.plan()
            self.assertEqual(planned["timing"], "estimated")

            self.render(images_only=True)
            self.assertEqual(self.recordings, [])
            drawn_ahead = len(self.drawn)
            self.assertEqual(drawn_ahead, len(planned["scenes"]))

        with mock.patch.object(gvm, "prompt_writer_order", return_value=["claude"]), \
                mock.patch.object(gvm, "write_scene_prompts_with_ai") as writer:
            self.render_until_frames()
        writer.assert_not_called()
        self.assertEqual(len(self.drawn), drawn_ahead)  # nothing redrawn
        timed = self.plan()
        self.assertEqual(timed["timing"], "recorded")
        self.assertEqual([sc["words"] for sc in timed["scenes"]], [sc["words"] for sc in planned["scenes"]])

    def test_scenes_json_ideas_go_to_the_writer(self):
        (self.reel / "scenes.json").write_text(json.dumps({"prompts": ["golden ark in a dark tent", "a burning altar"]}),
                                               encoding="utf-8")
        with mock.patch.object(gvm, "prompt_writer_order", return_value=["claude"]), \
                mock.patch.object(gvm, "write_scene_prompts_with_ai", side_effect=self.fill):
            self.render(plan_only=True)
        self.assertIn("- golden ark in a dark tent", self.writer_call["extra"])

    def test_a_reel_with_its_earlier_pictures_keeps_them(self):
        images = self.reel / "images"
        images.mkdir()
        Image.new("RGB", (9, 16)).save(images / "reel401_dyn_1.png")
        legacy = [{"id": "reel401_dyn_1", "prompt": "old", "weight": 2.0, "motion": gr.MOTIONS_CYCLE[0]}]
        with mock.patch.object(gr, "load_or_build_scenes", return_value=legacy) as old_scenes, \
                mock.patch.object(gvm, "prompt_writer_order", return_value=["claude"]), \
                mock.patch.object(gvm, "write_scene_prompts_with_ai") as writer:
            self.render_until_frames()
        old_scenes.assert_called_once()
        writer.assert_not_called()
        self.assertFalse((self.reel / gvm.SCENE_PLAN_FILE).exists())

    def test_planning_leaves_a_reel_with_earlier_pictures_alone(self):
        images = self.reel / "images"
        images.mkdir()
        Image.new("RGB", (9, 16)).save(images / "reel401_dyn_1.png")
        with mock.patch.object(gr, "load_or_build_scenes") as old_scenes, \
                mock.patch.object(gvm, "prompt_writer_order", return_value=["claude"]):
            self.assertEqual(self.render(plan_only=True), "KEPT")
        old_scenes.assert_not_called()
        self.assertEqual(self.recordings, [])
        self.assertEqual(self.drawn, [])
        self.assertFalse((self.reel / gvm.SCENE_PLAN_FILE).exists())

    def test_rebuilds_keep_the_recording_of_narration_timed_reels(self):
        temp = self.reel / "temp"
        temp.mkdir()
        (temp / "mon_1_test_reel_raw_voice.wav").write_bytes(b"voice")
        (temp / "rendered_frames.mp4").write_bytes(b"frames")
        with mock.patch.object(gvm, "prompt_writer_order", return_value=[]):
            self.render(force_rebuild=True)
        self.assertTrue((temp / "mon_1_test_reel_raw_voice.wav").exists())
        self.assertFalse((temp / "rendered_frames.mp4").exists())

    def test_main_exits_3_when_a_reel_waits_for_prompts(self):
        week = Path(self.tmp.name) / "W05"
        with mock.patch.object(gr, "render_reel", return_value="NEEDS_PROMPTS"), \
                mock.patch("sys.argv", ["generate_reel.py", "--week", "5", "--reel", "mon_1"]):
            with self.assertRaises(SystemExit) as cm:
                gr.main()
        self.assertEqual(cm.exception.code, 3)
        self.assertTrue(week.exists())


class WeekRunnerAndStudioTests(unittest.TestCase):
    def test_week_runner_reports_a_paused_reel(self):
        gw = load("generate_week")
        with mock.patch.object(gw.subprocess, "run", return_value=mock.Mock(returncode=3)):
            self.assertEqual(gw.run("Reel 1", ["python", "generate_reel.py"], Path(".")), "paused")
        with mock.patch.object(gw.subprocess, "run", return_value=mock.Mock(returncode=1)):
            self.assertEqual(gw.run("Reel 1", ["python", "generate_reel.py"], Path(".")), "failed")

    def test_reel_buttons_pass_their_step(self):
        import app as app_module
        self.assertEqual(app_module.reel_mode_args("plan"), ["--plan-only"])
        self.assertEqual(app_module.reel_mode_args("images"), ["--images-only"])
        self.assertEqual(app_module.reel_mode_args(None), ["--force-rebuild"])


if __name__ == "__main__":
    unittest.main()
