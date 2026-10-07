"""generate_video.py: narration first, then scenes timed to what is said, a prompt per scene, pictures in sync."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (blocks network before core modules load)

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gv = load("generate_video")


def _no_real_cli(*args, **kwargs):
    raise AssertionError("a test tried to run a real Claude/Gemini CLI")


gv._run_cli = _no_real_cli  # tests mock the writers; a real CLI call is a test bug

WORD_SEC = 0.4


def narration(sentences=60, words_per_sentence=8):
    return " ".join(" ".join(["word"] * (words_per_sentence - 1) + [f"end{i}."]) for i in range(sentences))


def write_transcript(path, text, word_sec=WORD_SEC):
    """A Whisper-style transcript: every word lasts word_sec."""
    words = [{"word": " " + w, "start": round(i * word_sec, 2), "end": round(i * word_sec + word_sec - 0.05, 2)}
             for i, w in enumerate(text.split())]
    Path(path).write_text(json.dumps({"segments": [{"start": 0.0, "end": words[-1]["end"], "words": words}]}),
                          encoding="utf-8")
    return words[-1]["end"]


class ScenePlanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ep = Path(self.tmp.name)
        self.transcript = self.ep / "transcript.json"

    def tearDown(self):
        self.tmp.cleanup()

    def test_scenes_follow_the_narration(self):
        text = narration()
        total = write_transcript(self.transcript, text)
        scenes = gv.plan_scenes_from_transcript(text, self.transcript, total, target_sec=20)

        self.assertEqual(scenes[0]["start"], 0.0)
        self.assertEqual(scenes[-1]["end"], round(total, 2))
        for a, b in zip(scenes, scenes[1:]):
            self.assertEqual(a["end"], b["start"])  # no gaps, no overlaps
        for sc in scenes:
            self.assertTrue(sc["text"].endswith("."), sc["text"][-20:])  # cut at sentence ends
            self.assertLessEqual(sc["end"] - sc["start"], gv.SCENE_MAX_SEC)
            self.assertEqual(sc["prompt"], "")
        self.assertEqual(" ".join(sc["text"] for sc in scenes), text)  # every word in exactly one scene
        avg = total / len(scenes)
        self.assertTrue(15 <= avg <= 25, avg)

    def test_a_scene_starts_when_its_first_word_is_spoken(self):
        text = narration()
        total = write_transcript(self.transcript, text)
        scenes = gv.plan_scenes_from_transcript(text, self.transcript, total, target_sec=20)
        for sc in scenes[1:]:
            self.assertAlmostEqual(sc["start"], sc["words"][0] * WORD_SEC, places=2)

    def test_a_short_last_scene_joins_the_one_before(self):
        text = narration(sentences=12) + " Until next time."
        total = write_transcript(self.transcript, text)
        scenes = gv.plan_scenes_from_transcript(text, self.transcript, total, target_sec=20)
        self.assertTrue(scenes[-1]["text"].endswith("Until next time."))
        self.assertGreaterEqual(scenes[-1]["end"] - scenes[-1]["start"], gv.SCENE_MIN_SEC)

    def test_a_long_sentence_is_split_at_a_clause(self):
        long_sentence = " ".join(["word,"] * 120) + " done."
        total = write_transcript(self.transcript, long_sentence)
        scenes = gv.plan_scenes_from_transcript(long_sentence, self.transcript, total, target_sec=20)
        self.assertGreater(len(scenes), 1)
        for sc in scenes[:-1]:
            self.assertLessEqual(sc["end"] - sc["start"], gv.SCENE_MAX_SEC + 1)


class PlanFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ep = Path(self.tmp.name)
        self.transcript = self.ep / "transcript.json"

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, text, total):
        return gv.load_or_build_scene_plan(self.ep, text, self.transcript, total, 20)

    def test_plan_is_saved_and_reused(self):
        text = narration()
        total = write_transcript(self.transcript, text)
        plan = self.plan(text, total)
        saved = json.loads((self.ep / gv.SCENE_PLAN_FILE).read_text(encoding="utf-8"))
        self.assertEqual(saved["narration_hash"], gv.narration_hash(text))
        self.assertEqual(len(saved["scenes"]), len(plan["scenes"]))

        saved["scenes"][0]["prompt"] = "a cherub with spread wings over a golden mercy seat"
        (self.ep / gv.SCENE_PLAN_FILE).write_text(json.dumps(saved), encoding="utf-8")
        again = self.plan(text, total)
        self.assertEqual(again["scenes"][0]["prompt"], "a cherub with spread wings over a golden mercy seat")

    def test_new_recording_of_the_same_words_retimes_and_keeps_prompts(self):
        text = narration()
        total = write_transcript(self.transcript, text)
        plan = self.plan(text, total)
        for sc in plan["scenes"]:
            sc["prompt"] = f"picture for {sc['id']}"
        (self.ep / gv.SCENE_PLAN_FILE).write_text(json.dumps(plan), encoding="utf-8")

        slower_total = write_transcript(self.transcript, text, word_sec=0.5)
        retimed = self.plan(text, slower_total)
        self.assertEqual([sc["text"] for sc in retimed["scenes"]], [sc["text"] for sc in plan["scenes"]])
        self.assertTrue(all(sc["prompt"] == f"picture for {sc['id']}" for sc in retimed["scenes"]))
        self.assertEqual(retimed["scenes"][-1]["end"], round(slower_total, 2))
        self.assertAlmostEqual(retimed["scenes"][1]["start"], retimed["scenes"][1]["words"][0] * 0.5, places=2)

    def test_changed_narration_rebuilds_and_keeps_matching_prompts(self):
        text = narration()
        total = write_transcript(self.transcript, text)
        plan = self.plan(text, total)
        first_text = plan["scenes"][0]["text"]
        plan["scenes"][0]["prompt"] = "kept prompt"
        plan["scenes"][-1]["prompt"] = "prompt for the old ending"
        (self.ep / gv.SCENE_PLAN_FILE).write_text(json.dumps(plan), encoding="utf-8")

        new_text = text + " A brand new closing sentence that was not there before."
        new_total = write_transcript(self.transcript, new_text)
        rebuilt = self.plan(new_text, new_total)
        self.assertTrue((self.ep / "scene_plan.previous.json").exists())
        self.assertEqual(rebuilt["narration_hash"], gv.narration_hash(new_text))
        self.assertEqual(rebuilt["scenes"][0]["text"], first_text)
        self.assertEqual(rebuilt["scenes"][0]["prompt"], "kept prompt")
        self.assertEqual(rebuilt["scenes"][-1]["prompt"], "")  # its words changed: needs a new prompt


class SceneImageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ep = Path(self.tmp.name)
        (self.ep / "images").mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def img(self, sid, content=b"x" * 50000):
        (self.ep / "images" / f"{sid}.png").write_bytes(content)

    def test_pictures_from_another_prompt_file_are_set_aside(self):
        self.img("scene_001")  # drawn by an older prompt file, no record
        scenes = [{"id": "scene_001", "prompt": "new prompt"}]
        gv.retire_stale_scene_images(scenes, self.ep)
        self.assertFalse((self.ep / "images" / "scene_001.png").exists())
        self.assertEqual(len(list((self.ep / "images" / "_replaced").glob("scene_001_*.png"))), 1)

    def test_matching_pictures_stay_and_renumbered_scenes_get_theirs_back(self):
        self.img("scene_001", b"a" * 50000)
        self.img("scene_002", b"b" * 50000)
        gv.record_scene_prompts([{"id": "scene_001", "prompt": "P1"}, {"id": "scene_002", "prompt": "P2"}], self.ep)

        # A sentence was added at the start: the old scene 1 is now scene 2, the old scene 2 is gone
        scenes = [{"id": "scene_001", "prompt": "P0"}, {"id": "scene_002", "prompt": "P1"}]
        gv.retire_stale_scene_images(scenes, self.ep)
        self.assertFalse((self.ep / "images" / "scene_001.png").exists())  # to be drawn for P0
        self.assertEqual((self.ep / "images" / "scene_002.png").read_bytes(), b"a" * 50000)

    def test_unchanged_pictures_are_kept(self):
        self.img("scene_001")
        gv.record_scene_prompts([{"id": "scene_001", "prompt": "P1"}], self.ep)
        gv.retire_stale_scene_images([{"id": "scene_001", "prompt": "P1"}], self.ep)
        self.assertTrue((self.ep / "images" / "scene_001.png").exists())
        self.assertFalse((self.ep / "images" / "_replaced").exists())


class VoiceFirstBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ep = Path(self.tmp.name) / "02_episode"
        self.ep.mkdir()
        (self.ep / "script_30min.txt").write_text(narration(sentences=40), encoding="utf-8")
        self.spoken = {}

        def fake_voice(text, temp_dir, prefix, speed=1.0, force_rebuild=False):
            tp = Path(temp_dir) / f"{prefix}_transcript.json"
            total = write_transcript(tp, text)
            self.spoken["text"] = text
            return str(Path(temp_dir) / "audio.wav"), str(tp), total

        self.patches = [mock.patch.object(gv, "generate_speech_and_timestamps", side_effect=fake_voice),
                        mock.patch.object(gv, "free_comfyui_memory"),
                        mock.patch.object(gv, "prompt_writer_order", return_value=[])]  # never call real CLIs
        self.voice = self.patches[0].start()
        self.free = self.patches[1].start()
        self.patches[2].start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_records_the_voice_then_pauses_for_prompts(self):
        with mock.patch.object(gv, "ensure_scene_images") as images:
            result = gv.build_16x9_video(self.ep, ep_num=3)
        self.assertEqual(result, "NEEDS_PROMPTS")
        self.free.assert_called_once()
        self.voice.assert_called_once()
        images.assert_not_called()  # no pictures until the prompts are written
        plan = json.loads((self.ep / gv.SCENE_PLAN_FILE).read_text(encoding="utf-8"))
        self.assertTrue(plan["scenes"])
        self.assertIn(gv.BOOKS_LINE.split(".")[0], " ".join(sc["text"] for sc in plan["scenes"]))
        self.assertFalse((self.ep / "prompts_78_scenes.json").exists())

    def test_with_prompts_the_pictures_follow_the_plan(self):
        gv.build_16x9_video(self.ep, ep_num=3)
        plan_p = self.ep / gv.SCENE_PLAN_FILE
        plan = json.loads(plan_p.read_text(encoding="utf-8"))
        for sc in plan["scenes"]:
            sc["prompt"] = f"the scene where {sc['id']} is spoken"
        plan_p.write_text(json.dumps(plan), encoding="utf-8")

        class Stop(Exception):
            pass

        with mock.patch.object(gv, "ensure_scene_images", return_value={}) as images, \
                mock.patch.object(gv, "load_chunked_captions_16x9", side_effect=Stop):
            with self.assertRaises(Stop):
                gv.build_16x9_video(self.ep, ep_num=3)
        scenes = images.call_args[0][0]
        self.assertEqual([s["id"] for s in scenes], [sc["id"] for sc in plan["scenes"]])
        self.assertTrue(scenes[0]["prompt"].startswith("the scene where scene_001 is spoken, "))
        self.assertIn(gv.DOC_IMAGE_STYLE, scenes[0]["prompt"])
        self.assertFalse(images.call_args[1]["allow_legacy_copy"])

    def test_auto_prompts_fill_the_plan_instead_of_pausing(self):
        with mock.patch.object(gv, "ensure_scene_images", return_value={"scene_001": "x"}) as images:
            result = gv.build_16x9_video(self.ep, ep_num=3, images_only=True, auto_prompts=True)
        self.assertIsNone(result)
        images.assert_called_once()
        plan = json.loads((self.ep / gv.SCENE_PLAN_FILE).read_text(encoding="utf-8"))
        self.assertTrue(all(sc["prompt"] for sc in plan["scenes"]))

    def test_an_older_episode_with_its_pictures_keeps_them(self):
        prompts = [{"id": f"scene_{i:02d}", "prompt": f"old {i}", "weight": 1.0, "motion": "zoom_in"} for i in range(1, 13)]
        (self.ep / "prompts_78_scenes.json").write_text(json.dumps(prompts), encoding="utf-8")
        (self.ep / "images").mkdir()
        for p in prompts:
            (self.ep / "images" / f"{p['id']}.png").write_bytes(b"x" * 50000)

        class Stop(Exception):
            pass

        with mock.patch.object(gv, "ensure_scene_images", return_value={}) as images, \
                mock.patch.object(gv, "load_chunked_captions_16x9", side_effect=Stop):
            with self.assertRaises(Stop):
                gv.build_16x9_video(self.ep, ep_num=3)
        self.assertEqual(len(images.call_args[0][0]), 12)
        self.assertFalse((self.ep / gv.SCENE_PLAN_FILE).exists())
        self.free.assert_not_called()

    def test_main_exits_3_when_prompts_are_needed(self):
        with mock.patch.object(gv, "find_episode_info", return_value=(str(self.ep), 3)), \
                mock.patch.object(gv, "build_16x9_video", return_value="NEEDS_PROMPTS"), \
                mock.patch("sys.argv", ["generate_video.py", "--week", "3", "--video", "2"]):
            with self.assertRaises(SystemExit) as cm:
                gv.main()
        self.assertEqual(cm.exception.code, gv.EXIT_NEEDS_PROMPTS)


def good_prompt(sid, writer="w"):
    return f"A towering angelic guardian with four vast wings standing on a holy mountain for {sid} by {writer}"


class PromptWriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ep = Path(self.tmp.name)
        (self.ep / "metadata.json").write_text(json.dumps({
            "episode_title": "The Anointed Cherub Cast Out", "scriptures": "Ezekiel 28:13-16"}), encoding="utf-8")
        self.plan = {"scenes": [{"id": f"scene_{i:03d}", "text": f"narration {i}.", "prompt": ""} for i in range(1, 61)]}
        self.requests = []

    def tearDown(self):
        self.tmp.cleanup()

    def writer(self, name, answer_ids=None, fail=None):
        def ask(request):
            self.requests.append((name, request))
            if fail:
                raise fail
            ids = [line.split(":")[0] for line in request.split("Scenes:\n")[1].split("\n\n")[0].splitlines()]
            if answer_ids is not None:
                ids = [i for i in ids if i in answer_ids]
            return "Here you go:\n```json\n" + json.dumps({i: good_prompt(i, name) for i in ids}) + "\n```"
        return ask

    def run_writers(self, writers, order):
        with mock.patch.dict(gv.PROMPT_WRITERS, writers):
            return gv.write_scene_prompts_with_ai(self.plan, self.ep, order)

    def test_claude_writes_every_prompt_in_batches(self):
        notes = self.run_writers({"claude": self.writer("claude")}, ["claude"])
        self.assertEqual(notes, [])
        self.assertTrue(all(sc["prompt"] and sc["prompt_by"] == "claude" for sc in self.plan["scenes"]))
        self.assertEqual(len(self.requests), 3)  # 60 scenes in batches of 25
        saved = json.loads((self.ep / gv.SCENE_PLAN_FILE).read_text(encoding="utf-8"))
        self.assertTrue(all(sc["prompt"] for sc in saved["scenes"]))
        first = self.requests[0][1]
        self.assertIn("Episode: The Anointed Cherub Cast Out", first)
        self.assertIn("scene_001: narration 1.", first)
        self.assertIn("Prompts already written", self.requests[1][1])  # later batches see earlier prompts

    def test_gemini_takes_over_when_claude_is_not_signed_in(self):
        notes = self.run_writers({"claude": self.writer("claude", fail=gv.PromptWriterUnavailable("not signed in")),
                                  "gemini": self.writer("gemini")}, ["claude", "gemini"])
        self.assertTrue(all(sc["prompt_by"] == "gemini" for sc in self.plan["scenes"]))
        self.assertEqual(sum(1 for n, _ in self.requests if n == "claude"), 1)  # not retried after "not signed in"
        self.assertIn("claude, then type /login", notes[0])

    def test_missing_scenes_are_asked_again(self):
        answered = {"scene_001", "scene_002"}
        calls = {"n": 0}
        partial = self.writer("claude", answer_ids=answered)
        full = self.writer("claude")

        def ask(request):
            calls["n"] += 1
            return partial(request) if calls["n"] == 1 else full(request)

        self.run_writers({"claude": ask}, ["claude"])
        self.assertTrue(all(sc["prompt"] for sc in self.plan["scenes"]))
        retry = self.requests[1][1]
        self.assertNotIn("scene_001:", retry)
        self.assertIn("scene_003:", retry)

    def test_nobody_available_leaves_prompts_empty(self):
        notes = self.run_writers({"claude": self.writer("claude", fail=gv.PromptWriterUnavailable("not signed in")),
                                  "gemini": self.writer("gemini", fail=gv.PromptWriterUnavailable("not signed in"))},
                                 ["claude", "gemini"])
        self.assertEqual(len(notes), 2)
        self.assertTrue(all(not sc["prompt"] for sc in self.plan["scenes"]))
        self.assertEqual(len(self.requests), 2)

    def test_reply_cleaning(self):
        reply = 'Sure! {"scene_001": "Two golden cherubim over the ark of the covenant in a dark holy chamber, wings stretched forward.", "scene_002": "too short", "scene_009": "not asked for at all, but long enough to count as a prompt"}'
        got = gv.parse_prompt_reply(reply, ["scene_001", "scene_002", "scene_003"])
        self.assertEqual(list(got), ["scene_001"])
        self.assertTrue(got["scene_001"].startswith("Two golden towering angelic guardians over the ark"))
        self.assertFalse(got["scene_001"].endswith("."))
        self.assertEqual(gv.parse_prompt_reply("no json here", ["scene_001"]), {})

    def test_order_comes_from_the_flag_then_the_settings_file(self):
        settings = self.ep / "generator_settings.json"
        with mock.patch.object(gv, "GENERATOR_SETTINGS_FILE", settings):
            self.assertEqual(gv.prompt_writer_order(), ["claude", "gemini"])  # default
            settings.write_text(json.dumps({"scene_prompt_writer": "gemini"}), encoding="utf-8")
            self.assertEqual(gv.prompt_writer_order(), ["gemini"])
            self.assertEqual(gv.prompt_writer_order("claude,gemini"), ["claude", "gemini"])
            self.assertEqual(gv.prompt_writer_order("manual"), [])

    def test_claude_not_signed_in_is_reported(self):
        reply = mock.Mock(stdout=json.dumps({"is_error": True, "result": "Not logged in · Please run /login"}),
                          stderr="", returncode=1)
        with mock.patch.object(gv, "find_claude_cli", return_value="claude.exe"), \
                mock.patch.object(gv, "_run_cli", return_value=reply):
            with self.assertRaises(gv.PromptWriterUnavailable):
                gv.ask_claude("request")
        ok = mock.Mock(stdout=json.dumps({"is_error": False, "result": '{"scene_001": "x"}'}), stderr="", returncode=0)
        with mock.patch.object(gv, "find_claude_cli", return_value="claude.exe"), \
                mock.patch.object(gv, "_run_cli", return_value=ok) as run:
            self.assertEqual(gv.ask_claude("request"), '{"scene_001": "x"}')
        cmd = run.call_args[0][0]
        self.assertIn("--tools", cmd)
        self.assertEqual(cmd[cmd.index("--tools") + 1], "")  # no tools: it only answers

    def test_claude_native_install_is_found_without_path(self):
        from core import prompt_writers
        with tempfile.TemporaryDirectory() as home:
            exe = Path(home) / ".local" / "bin" / "claude.exe"
            exe.parent.mkdir(parents=True)
            exe.write_bytes(b"")
            for find in (gv.find_claude_cli, prompt_writers.find_claude_cli):
                with mock.patch("shutil.which", return_value=None), \
                        mock.patch.object(Path, "home", return_value=Path(home)):
                    self.assertEqual(find(), str(exe))

    def test_gemini_sign_in_is_checked_without_sending_the_request(self):
        not_signed = mock.Mock(stdout="", stderr="Authentication cancelled", returncode=130)
        with mock.patch.object(gv, "find_gemini_cli", return_value="gemini.cmd"), \
                mock.patch.object(gv, "_run_cli", return_value=not_signed) as run:
            with self.assertRaises(gv.PromptWriterUnavailable):
                gv.ask_gemini("the request")
        self.assertEqual(run.call_count, 1)
        self.assertIsNone(run.call_args[0][1])  # no input on the sign-in check
        self.assertEqual(run.call_args[1]["env"]["NO_BROWSER"], "true")


class AutoPromptBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.ep = Path(self.tmp.name) / "02_episode"
        self.ep.mkdir()
        (self.ep / "script_30min.txt").write_text(narration(sentences=40), encoding="utf-8")

        def fake_voice(text, temp_dir, prefix, speed=1.0, force_rebuild=False):
            tp = Path(temp_dir) / f"{prefix}_transcript.json"
            return str(Path(temp_dir) / "audio.wav"), str(tp), write_transcript(tp, text)

        self.patches = [mock.patch.object(gv, "generate_speech_and_timestamps", side_effect=fake_voice),
                        mock.patch.object(gv, "free_comfyui_memory")]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def test_written_prompts_go_straight_to_the_pictures(self):
        def fill(plan, ep_p, writers):
            for sc in plan["scenes"]:
                sc["prompt"] = good_prompt(sc["id"])
            return []

        with mock.patch.object(gv, "prompt_writer_order", return_value=["claude"]), \
                mock.patch.object(gv, "write_scene_prompts_with_ai", side_effect=fill) as writer, \
                mock.patch.object(gv, "ensure_scene_images", return_value={}) as images:
            result = gv.build_16x9_video(self.ep, ep_num=3, images_only=True)
        self.assertIsNone(result)  # no pause
        writer.assert_called_once()
        images.assert_called_once()

    def test_existing_prompts_are_used_without_asking_a_writer(self):
        with mock.patch.object(gv, "prompt_writer_order", return_value=[]), \
                mock.patch.object(gv, "ensure_scene_images") as images:
            gv.build_16x9_video(self.ep, ep_num=3)  # records the voice, plans, pauses
        plan_p = self.ep / gv.SCENE_PLAN_FILE
        plan = json.loads(plan_p.read_text(encoding="utf-8"))
        for sc in plan["scenes"]:
            sc["prompt"] = good_prompt(sc["id"], "hand")
        plan_p.write_text(json.dumps(plan), encoding="utf-8")

        with mock.patch.object(gv, "prompt_writer_order", return_value=["claude", "gemini"]), \
                mock.patch.object(gv, "write_scene_prompts_with_ai") as writer, \
                mock.patch.object(gv, "ensure_scene_images", return_value={}) as images:
            self.assertIsNone(gv.build_16x9_video(self.ep, ep_num=3, images_only=True))
        writer.assert_not_called()
        self.assertTrue(all(s["prompt"].startswith(good_prompt(f"scene_{i + 1:03d}", "hand"))
                            for i, s in enumerate(images.call_args[0][0])))

    def test_only_missing_prompts_are_written(self):
        with mock.patch.object(gv, "prompt_writer_order", return_value=[]):
            gv.build_16x9_video(self.ep, ep_num=3)
        plan_p = self.ep / gv.SCENE_PLAN_FILE
        plan = json.loads(plan_p.read_text(encoding="utf-8"))
        plan["scenes"][0]["prompt"] = good_prompt("scene_001", "hand")
        plan_p.write_text(json.dumps(plan), encoding="utf-8")
        seen = {}

        def fill(plan, ep_p, writers):
            seen["empty"] = [sc["id"] for sc in plan["scenes"] if not sc["prompt"]]
            for sc in plan["scenes"]:
                sc["prompt"] = sc["prompt"] or good_prompt(sc["id"], "claude")
            return []

        with mock.patch.object(gv, "prompt_writer_order", return_value=["claude"]), \
                mock.patch.object(gv, "write_scene_prompts_with_ai", side_effect=fill), \
                mock.patch.object(gv, "ensure_scene_images", return_value={}):
            gv.build_16x9_video(self.ep, ep_num=3, images_only=True)
        self.assertNotIn("scene_001", seen["empty"])
        self.assertEqual(json.loads(plan_p.read_text(encoding="utf-8"))["scenes"][0]["prompt"],
                         good_prompt("scene_001", "hand"))

    def test_pause_names_the_sign_in_step(self):
        out = []
        with mock.patch.object(gv, "prompt_writer_order", return_value=["claude"]), \
                mock.patch.object(gv, "write_scene_prompts_with_ai",
                                  return_value=["Claude Code: not signed in. To sign in, open a terminal, run claude, then type /login."]), \
                mock.patch("builtins.print", side_effect=lambda *a, **k: out.append(" ".join(map(str, a)))):
            result = gv.build_16x9_video(self.ep, ep_num=3)
        self.assertEqual(result, "NEEDS_PROMPTS")
        self.assertTrue(any("run claude, then type /login" in line for line in out))


class StudioPromptWriterTests(unittest.TestCase):
    def test_setting_is_saved_in_the_project(self):
        from core import prompt_writers
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(prompt_writers.get_setting(tmp), "claude,gemini")
            prompt_writers.set_setting(tmp, "gemini")
            self.assertEqual(prompt_writers.get_setting(tmp), "gemini")
            self.assertEqual(json.loads((Path(tmp) / "generator_settings.json").read_text())["scene_prompt_writer"], "gemini")
            with self.assertRaises(ValueError):
                prompt_writers.set_setting(tmp, "chatgpt")
            # The generator reads the same file
            with mock.patch.object(gv, "GENERATOR_SETTINGS_FILE", Path(tmp) / "generator_settings.json"):
                self.assertEqual(gv.prompt_writer_order(), ["gemini"])


class StudioSummaryTests(unittest.TestCase):
    def test_week_card_shows_how_many_prompts_are_missing(self):
        import app as app_module
        with tempfile.TemporaryDirectory() as tmp:
            ep = Path(tmp)
            self.assertIsNone(app_module.scene_plan_summary(ep))
            (ep / "scene_plan.json").write_text(json.dumps({"scenes": [
                {"id": "scene_001", "prompt": "a cherub"}, {"id": "scene_002", "prompt": ""}, {"id": "scene_003"}]}),
                encoding="utf-8")
            self.assertEqual(app_module.scene_plan_summary(ep), {"scenes": 3, "missing_prompts": 2})


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class ComfyQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        (self.out / "Doc_16x9_Scene_00001_.png").write_bytes(b"x" * 50000)
        self.target = self.out / "images" / "scene_001.png"
        self.target.parent.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_waits_while_queued_behind_other_jobs(self):
        polls = {"n": 0}

        def urlopen(req, timeout=None):
            url = req if isinstance(req, str) else req.full_url
            if url.endswith("/prompt"):
                return FakeResponse({"prompt_id": "abc"})
            if "/history/" in url:
                polls["n"] += 1
                if polls["n"] < 200:  # about 8 minutes behind another tool's jobs
                    return FakeResponse({})
                return FakeResponse({"abc": {"outputs": {"9": {"images": [{"filename": "Doc_16x9_Scene_00001_.png"}]}}}})
            if url.endswith("/queue"):
                return FakeResponse({"queue_running": [[1, "other"]], "queue_pending": [[2, "abc"]]})
            raise AssertionError(url)

        with mock.patch.object(gv.urllib.request, "urlopen", side_effect=urlopen), \
                mock.patch.object(gv.time, "sleep"), \
                mock.patch.object(gv, "COMFY_OUTPUT_DIR", str(self.out)):
            self.assertTrue(gv._render_16x9_in_comfyui("a prompt", "scene_001", self.target))
        self.assertTrue(self.target.exists())

    def test_a_dropped_job_is_reported(self):
        clock = {"t": 0.0}

        def urlopen(req, timeout=None):
            url = req if isinstance(req, str) else req.full_url
            if url.endswith("/prompt"):
                return FakeResponse({"prompt_id": "abc"})
            if "/history/" in url:
                return FakeResponse({})
            if url.endswith("/queue"):
                return FakeResponse({"queue_running": [], "queue_pending": []})
            raise AssertionError(url)

        def sleep(sec):
            clock["t"] += sec

        with mock.patch.object(gv.urllib.request, "urlopen", side_effect=urlopen), \
                mock.patch.object(gv.time, "sleep", side_effect=sleep), \
                mock.patch.object(gv.time, "time", side_effect=lambda: clock["t"]):
            self.assertFalse(gv._render_16x9_in_comfyui("a prompt", "scene_001", self.target))

    def test_comfyui_error_is_raised(self):
        def urlopen(req, timeout=None):
            url = req if isinstance(req, str) else req.full_url
            if url.endswith("/prompt"):
                return FakeResponse({"prompt_id": "abc"})
            if "/history/" in url:
                return FakeResponse({"abc": {"outputs": {}, "status": {"status_str": "error"}}})
            raise AssertionError(url)

        with mock.patch.object(gv.urllib.request, "urlopen", side_effect=urlopen), \
                mock.patch.object(gv.time, "sleep"):
            with self.assertRaises(RuntimeError):
                gv._render_16x9_in_comfyui("a prompt", "scene_001", self.target)


if __name__ == "__main__":
    unittest.main()
