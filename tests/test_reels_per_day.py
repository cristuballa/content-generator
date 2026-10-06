"""Several reels a day: day-named reel folders (mon_1_x, mon_2_x, tue_1_x), their posting order and times, the
generators finding them, stories keeping their reel, and renaming the older numbered folders."""
import datetime
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (blocks network before core modules load)
from core.calendar_manager import CalendarManager
from core.reels import find_reel, ordered_reels, reel_day_and_time, reel_key, recorded_reel_number

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def load(name):
    spec = importlib.util.spec_from_file_location(f"_t_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gr = load("generate_reel")
gs = load("generate_story")
sys.path.insert(0, str(SCRIPTS))
rename = load("rename_reels_by_day")


def make(root: Path, *names, meta=None):
    out = []
    for name in names:
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        if meta is not None:
            (d / "metadata.json").write_text(json.dumps(meta.get(name, {})), encoding="utf-8")
        out.append(d)
    return out


class OrderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.reels = Path(self.tmp.name) / "W06" / "reels"

    def test_day_named_reels_post_by_day_then_place(self):
        make(self.reels, "tue_1_c", "mon_2_b", "mon_1_a", "fri_1_e", "temp", "__pycache__")
        self.assertEqual([d.name for d in ordered_reels(self.reels)], ["mon_1_a", "mon_2_b", "tue_1_c", "fri_1_e"])
        self.assertEqual(reel_key(self.reels / "mon_2_b"), "mon_2")

    def test_numbered_reels_take_the_weekdays_in_number_order(self):
        make(self.reels, "150_e", "146_a", "147_b", "149_d", "148_c")
        self.assertEqual([reel_key(d) for d in ordered_reels(self.reels)], ["mon_1", "tue_1", "wed_1", "thu_1", "fri_1"])
        self.assertEqual(ordered_reels(self.reels)[0].name, "146_a")

    def test_find_by_key_folder_or_position(self):
        make(self.reels, "mon_1_a", "mon_2_b", "tue_1_c")
        self.assertEqual(find_reel(self.reels, "mon_2").name, "mon_2_b")
        self.assertEqual(find_reel(self.reels, "TUE_1_c").name, "tue_1_c")
        self.assertEqual(find_reel(self.reels, 2).name, "mon_2_b")
        self.assertIsNone(find_reel(self.reels, "wed_1"))

    def test_time_comes_from_the_place_in_the_day_unless_pinned(self):
        make(self.reels, "mon_1_a", "mon_2_b", "tue_3_c", meta={"tue_3_c": {"post_time": "12:15"}})
        times = ["07:30", "17:30"]
        self.assertEqual(reel_day_and_time(self.reels / "mon_2_b", times), (0, "17:30"))
        self.assertEqual(reel_day_and_time(self.reels / "tue_3_c", times), (1, "12:15"))
        (self.reels / "tue_3_c" / "metadata.json").write_text("{}", encoding="utf-8")
        self.assertEqual(reel_day_and_time(self.reels / "tue_3_c", times), (1, "17:30"))  # past the list: last time


class ReelGeneratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        p = mock.patch.object(gr, "PROJECT_DIR", self.project)
        p.start()
        self.addCleanup(p.stop)
        self.week = self.project / "W06"
        make(self.week / "reels", "mon_1_a", "mon_2_b", "tue_1_c", "tue_2_d",
             meta={"mon_1_a": {"global_episode": 26}, "mon_2_b": {}, "tue_1_c": {"global_episode": 27}, "tue_2_d": {}})
        old = self.project / "W30" / "reels" / "146_old"
        old.mkdir(parents=True)
        (old / "metadata.txt").write_text("EPISODE 146 — METADATA\n\nTITLE: Old\n", encoding="utf-8")

    def test_finds_reels_by_key_and_position(self):
        self.assertEqual(gr.find_reel_folder(self.week, "tue_2").name, "tue_2_d")
        self.assertEqual(gr.find_reel_folder(self.week, "2").name, "mon_2_b")

    def test_numbers_come_from_metadata_or_the_next_free_one_which_is_saved(self):
        self.assertEqual(gr.reel_global_number(self.week / "reels" / "mon_1_a"), 26)
        self.assertEqual(gr.reel_global_number(self.project / "W30" / "reels" / "146_old"), 146)
        new = gr.reel_global_number(self.week / "reels" / "mon_2_b")
        self.assertEqual(new, 147)
        saved = json.loads((self.week / "reels" / "mon_2_b" / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(saved["global_episode"], 147)
        self.assertEqual(gr.reel_global_number(self.week / "reels" / "tue_2_d"), 148)
        self.assertEqual(gr.find_reel_by_number(27), (6, self.week / "reels" / "tue_1_c"))

    def test_older_numbered_reel_without_a_number_keeps_its_usual_one(self):
        (old,) = make(self.project / "W05" / "reels", "02_lamb", meta={"02_lamb": {"title": "Lamb"}})
        make(self.project / "W05" / "reels", "01_fruit")
        self.assertEqual(gr.reel_global_number(old), 22)
        self.assertNotIn("global_episode", json.loads((old / "metadata.json").read_text(encoding="utf-8")))

    def run_main(self, *argv):
        with mock.patch.object(gr, "render_reel", return_value=Path("final_reel.mp4")) as render, \
                mock.patch.object(sys, "argv", ["generate_reel.py", *argv]):
            gr.main()
        return [c.kwargs["target_dir"].name for c in render.call_args_list]

    def test_a_failed_reel_fails_the_run(self):
        with mock.patch.object(gr, "render_reel", side_effect=RuntimeError("ComfyUI could not generate scene")), \
                mock.patch.object(sys, "argv", ["generate_reel.py", "--week", "6", "--reel", "mon_1"]), \
                self.assertRaises(SystemExit) as stop:
            gr.main()
        self.assertEqual(stop.exception.code, 1)

    def test_scenes_json_prompts_follow_the_narration(self):
        folder = self.week / "reels" / "mon_1_a"
        (folder / "scenes.json").write_text(json.dumps({"prompts": ["first picture", "middle picture", "last picture"]}),
                                            encoding="utf-8")
        sentences = [f"Sentence number {i} has enough words to stand alone here." for i in range(18)]
        scenes = gr.load_or_build_scenes(folder, sentences, "26")
        firsts = [s["prompt"].split(",")[0] for s in scenes]
        self.assertEqual((firsts[0], firsts[9], firsts[-1]), ("first picture", "middle picture", "last picture"))
        self.assertEqual(firsts, sorted(firsts, key=["first picture", "middle picture", "last picture"].index))

    def test_fallback_prompt_reads_the_sentence_and_cta_gets_books(self):
        prompt = gr.build_scene_prompt("Jesus humbled Himself and became obedient unto death.", title="The Morning Star")
        self.assertIn("Jesus humbled Himself and became obedient unto death", prompt)
        self.assertIn("The Morning Star", prompt)
        cta = gr.build_scene_prompt("If this blew your mind, it's just one part of what we uncover in our books.")
        self.assertIn("leather-bound books", cta)

    def test_all_renders_every_reel_in_posting_order(self):
        self.assertEqual(self.run_main("--week", "6", "--all"), ["mon_1_a", "mon_2_b", "tue_1_c", "tue_2_d"])

    def test_single_reel_by_key_and_by_number(self):
        self.assertEqual(self.run_main("--week", "6", "--reel", "tue_1"), ["tue_1_c"])
        self.assertEqual(self.run_main("--episode", "27"), ["tue_1_c"])


class ComfyWaitTests(unittest.TestCase):
    """A scene waits while it is in ComfyUI's queue (other tools may be using ComfyUI) instead of giving up at 6 min."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.images = Path(self.tmp.name)
        for target, value in (("time.sleep", None),):
            p = mock.patch.object(gr.time, "sleep", return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def fake_comfy(self, waits_in_queue, final_history):
        """urlopen stand-in: the job sits in the queue for `waits_in_queue` polls, then history shows final_history."""
        state = {"polls": 0}

        class Resp:
            def __init__(self, body):
                self.body = json.dumps(body).encode("utf-8")

            def read(self):
                return self.body

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def urlopen(req, timeout=None):
            url = req.full_url if hasattr(req, "full_url") else req
            if url.endswith("/system_stats"):
                return Resp({})
            if url.endswith("/prompt"):
                return Resp({"prompt_id": "p1"})
            if url.endswith("/history"):
                return Resp({})
            if "/history/p1" in url:
                state["polls"] += 1
                return Resp({"p1": final_history} if state["polls"] > waits_in_queue else {})
            if url.endswith("/queue"):
                done = state["polls"] > waits_in_queue
                return Resp({"queue_running": [] if done else [[1, "other-tool-job", {}]],
                             "queue_pending": [] if done else [[2, "p1", {}]]})
            raise AssertionError(url)

        def urlretrieve(url, path):
            from PIL import Image
            Image.new("RGB", (768, 1344), (120, 90, 30)).save(path)
            Image.effect_noise((768, 1344), 80).convert("RGB").save(path)
        return urlopen, urlretrieve

    def generate(self, waits, history):
        urlopen, urlretrieve = self.fake_comfy(waits, history)
        with mock.patch.object(gr.urllib.request, "urlopen", side_effect=urlopen), \
                mock.patch.object(gr.urllib.request, "urlretrieve", side_effect=urlretrieve), \
                mock.patch.object(gr, "is_comfyui_running", return_value=True):
            return gr.generate_scene_image("a scene", "reel301_dyn_8", self.images)

    def test_keeps_waiting_behind_other_jobs_past_the_old_limit(self):
        done = {"outputs": {"9": {"images": [{"filename": "x.png"}]}}, "status": {"status_str": "success"}}
        img = self.generate(waits=400, history=done)  # 400 polls x 2 s = well past the old 6-minute cap
        self.assertTrue(img.exists())

    def test_comfyui_error_fails_the_scene(self):
        failed = {"outputs": {}, "status": {"status_str": "error"}}
        with self.assertRaises(RuntimeError):
            self.generate(waits=3, history=failed)


class StoryReelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.reels = Path(self.tmp.name) / "W06" / "reels"
        make(self.reels, "mon_1_a", "mon_2_b", "tue_1_c", "wed_1_d")

    def test_key_wins_and_an_old_number_means_that_days_first_reel(self):
        self.assertEqual(gs.story_reel(self.reels, reel="mon_2").name, "mon_2_b")
        # reel_num 2 was Tuesday's reel before mon_2 existed, and still is
        self.assertEqual(gs.story_reel(self.reels, reel_num=2).name, "tue_1_c")
        self.assertEqual(gs.story_reel(self.reels, story_idx=3).name, "wed_1_d")


class ReelSlotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.cal = CalendarManager(schedule_file=self.project / "schedule.json")
        cfg = {"default_posting_time": "07:30", "reel_posting_times": ["07:30", "17:30"]}
        p = mock.patch("core.calendar_manager.config_manager")
        self.config = p.start()
        self.addCleanup(p.stop)
        self.config.get_project_social_config.return_value = cfg
        make(self.project / "W06" / "reels", "mon_1_a", "mon_2_b", "tue_2_c")
        self.start = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()

    def slot(self, rel):
        return self.cal.find_next_available_slot(str(self.project), ["youtube"], start_date_str=self.start, video_rel_path=rel)

    def book(self, rel, slot):
        path = self.project / "schedule.json"
        items = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
        items.append({"id": rel, "project_path": str(self.project), "video_rel_path": rel, "status": "scheduled",
                      "platforms": ["youtube"], "scheduled_date": slot["date"], "scheduled_time": slot["time"]})
        path.write_text(json.dumps(items), encoding="utf-8")

    def test_two_reels_share_a_monday_and_tue_2_goes_to_tuesday_evening(self):
        first = self.slot("W06/reels/mon_1_a/mon_1_a_final_reel.mp4")
        self.book("W06/reels/mon_1_a/mon_1_a_final_reel.mp4", first)
        second = self.slot("W06/reels/mon_2_b/mon_2_b_final_reel.mp4")
        self.assertEqual(datetime.date.fromisoformat(first["date"]).weekday(), 0)
        self.assertEqual((first["time"], second["time"], second["date"]), ("07:30", "17:30", first["date"]))
        tue = self.slot("W06/reels/tue_2_c/tue_2_c_final_reel.mp4")
        self.assertEqual((datetime.date.fromisoformat(tue["date"]).weekday(), tue["time"]), (1, "17:30"))

    def test_a_taken_reel_slot_moves_a_week_and_long_form_is_not_blocked(self):
        first = self.slot("W06/reels/mon_1_a/mon_1_a_final_reel.mp4")
        self.book("W06/reels/mon_1_a/mon_1_a_final_reel.mp4", first)
        self.book("W06/reels/mon_2_b/mon_2_b_final_reel.mp4", self.slot("W06/reels/mon_2_b/mon_2_b_final_reel.mp4"))
        again = self.slot("W06/reels/mon_1_a/mon_1_a_final_reel.mp4")
        gap = datetime.date.fromisoformat(again["date"]) - datetime.date.fromisoformat(first["date"])
        self.assertEqual(gap.days, 7)
        self.assertTrue(self.cal.validate_slot(str(self.project), first["date"], ["youtube"])["valid"])


class WeekEndpointTests(unittest.TestCase):
    def test_lists_every_reel_in_posting_order_with_its_time(self):
        from fastapi.testclient import TestClient
        import app as app_module
        from core.config import config_manager
        with tempfile.TemporaryDirectory() as tmp:
            reels = Path(tmp) / "W06" / "reels"
            make(reels, "tue_1_c", "mon_2_b", "mon_1_a", meta={"mon_1_a": {"title": "A", "global_episode": 26},
                                                              "mon_2_b": {"title": "B"}, "tue_1_c": {"title": "C"}})
            with mock.patch.object(config_manager, "get_active_project", return_value=tmp):
                data = TestClient(app_module.app).get("/api/generator/week/6").json()
        got = [(r["key"], r["day"], r["post_time"], r["folder_name"]) for r in data["reels"]]
        self.assertEqual(got, [("mon_1", "Monday", "07:30", "mon_1_a"), ("mon_2", "Monday", "17:30", "mon_2_b"),
                               ("tue_1", "Tuesday", "07:30", "tue_1_c")])
        self.assertEqual(data["reels"][0]["global_num"], 26)


class PostStatusTests(unittest.TestCase):
    def test_posted_waiting_and_not_posted(self):
        import app as app_module
        future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        record = {"published": {
            "youtube": {"status": "published", "details": {"url": "https://youtu.be/a", "scheduled": True, "scheduled_for": future}},
            "facebook": {"status": "published", "details": {"url": "https://facebook.com/reel/1"}},
            "instagram": {"status": "published", "details": {"url": "https://instagram.com/reel/2", "scheduled": True,
                                                             "scheduled_for": "2020-01-01T00:00:00.000Z"}},
        }}
        with mock.patch.object(app_module.asset_manager, "get_asset_record", return_value=record):
            posts = app_module.video_post_status("W03/reels/mon_1_a/mon_1_a_final_reel.mp4")
        self.assertEqual(posts["youtube"]["state"], "scheduled")
        self.assertTrue(posts["youtube"]["live_at"])
        self.assertEqual((posts["facebook"]["state"], posts["facebook"]["url"]), ("posted", "https://facebook.com/reel/1"))
        self.assertEqual(posts["instagram"]["state"], "posted")  # its time has passed: it's live
        self.assertNotIn("tiktok", posts)
        self.assertEqual(app_module.video_post_status(None), {})


class StoryMapWeekTests(unittest.TestCase):
    """The dashboard's week table lists what the week's folders hold, not the 5-a-week placeholders."""

    def test_reels_and_stories_come_from_the_folders(self):
        import core.story_map_manager as smm
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "BHSR"
            reels = root / "W03" / "reels"
            make(reels, "tue_1_c", "mon_2_b", "mon_1_a",
                 meta={"mon_1_a": {"title": "A", "global_episode": 11}, "mon_2_b": {"title": "B", "global_episode": 301},
                       "tue_1_c": {"title": "C"}})
            stories = root / "W03" / "stories"
            make(stories, "01_old", "06_new_morning", "07_new_evening",
                 meta={"01_old": {"title": "Old", "day": "Wednesday", "post_time": "13:00"},
                       "06_new_morning": {"title": "Morning", "day": "Monday", "post_time": "08:00", "final_cta": "NEW REEL ON OUR PAGE"},
                       "07_new_evening": {"title": "Evening", "day": "Monday", "post_time": "20:00"}})
            plan = [{"week": 3, "documentary": {}, "reels": [{"id": f"R{i}", "hook_type": f"H{i}", "title": f"Part {i}"} for i in range(5)],
                     "stories": [{"id": f"S{i}", "caption": f"Placeholder {i}"} for i in range(5)], "community_posts": []},
                    {"week": 4, "documentary": {}, "reels": [{"id": "keep"}], "stories": [{"id": "keep"}], "community_posts": []}]
            data_file = Path(tmp) / "story_map_data.json"
            data_file.write_text(json.dumps({"weeks": plan}), encoding="utf-8")
            with mock.patch.object(smm, "BHSR_ROOT", root), \
                    mock.patch.object(smm.asset_manager, "get_asset_record", return_value={"published": {}}):
                smm.StoryMapManager(data_file=data_file).refresh_covered_status()
            weeks = json.loads(data_file.read_text(encoding="utf-8"))["weeks"]
        w3, w4 = weeks
        self.assertEqual([(r["key"], r["title"], r["post_time"]) for r in w3["reels"]],
                         [("mon_1", "A", "07:30"), ("mon_2", "B", "17:30"), ("tue_1", "C", "07:30")])
        self.assertEqual(w3["reels"][1]["badge"], "Bible Secrets #301 [W03 mon_2]")
        self.assertEqual(w3["reels"][0]["hook_type"], "H0")  # Monday's first reel keeps its planned hook label
        self.assertEqual([(s["day"], s["post_time"], s["caption"]) for s in w3["stories"]],
                         [("Mon", "08:00", "Morning"), ("Mon", "20:00", "Evening"), ("Wed", "13:00", "Old")])
        self.assertEqual(w3["stories"][0]["sticker_type"], "new_reel")
        self.assertEqual(w4["reels"], [{"id": "keep"}])  # no folders yet: the plan stays


class RenameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.project, self.data = root / "BHSR", root / "data"
        self.data.mkdir()
        week = self.project / "W02"
        (week / "stories" / "09_story").mkdir(parents=True)
        (week / "stories" / "09_story" / "metadata.json").write_text(json.dumps({"reel_num": 2}), encoding="utf-8")
        (week / "metadata.json").write_text(json.dumps({"reels": [{"num": n, "day": d} for n, d in
                                                                   enumerate(["Mon", "Tue", "Wed", "Thu", "Fri"], 1)]}), encoding="utf-8")
        for n in range(1, 6):
            d = week / "reels" / f"0{n}_topic{n}"
            (d / "temp").mkdir(parents=True)
            (d / f"0{n}_topic{n}_final_reel.mp4").write_bytes(b"v")
            (d / "temp" / f"0{n}_topic{n}_voice_script.txt").write_text("words", encoding="utf-8")
            (d / "metadata.json").write_text(json.dumps({"title": f"T{n}"}), encoding="utf-8")
        rel = "W02/reels/02_topic2/02_topic2_final_reel.mp4"
        (self.data / "media_catalog.json").write_text(json.dumps({"assets": {rel: {"status": "approved", "published": {
            "youtube": {"details": {"url": "https://youtu.be/x", "thumbnail": f"C:\\BHSR\\W02\\reels\\02_topic2\\thumbnail.jpg"}}}}}}),
            encoding="utf-8")
        (self.data / "posting_schedule.json").write_text(json.dumps([{"video_rel_path": rel, "video_filename": "02_topic2_final_reel.mp4",
                                                                     "thumbnail_url": f"/api/thumbnail/{rel}"}]), encoding="utf-8")
        (self.data / "story_map_data.json").write_text(json.dumps({"x": {"video_url": f"/api/media/{rel}?t=1"}}), encoding="utf-8")
        self.originals = {p: p.read_bytes() for p in self.data.glob("*.json")}

    def run_apply(self):
        plan = rename.plan_week(self.project / "W02")
        return plan, rename.apply(self.project, plan, self.data / "backups" / "run", data_dir=self.data)

    def test_plan_names_reels_by_day(self):
        plan = rename.plan_week(self.project / "W02")
        self.assertEqual([(p["old"], p["new"], p["number"]) for p in plan][:2],
                         [("01_topic1", "mon_1_topic1", 6), ("02_topic2", "tue_1_topic2", 7)])
        self.assertTrue((self.project / "W02" / "reels" / "01_topic1").exists())  # planning changes nothing

    def test_apply_renames_folders_files_and_records(self):
        self.run_apply()
        reel = self.project / "W02" / "reels" / "tue_1_topic2"
        self.assertTrue((reel / "tue_1_topic2_final_reel.mp4").exists())
        self.assertTrue((reel / "temp" / "tue_1_topic2_voice_script.txt").exists())
        self.assertEqual(json.loads((reel / "metadata.json").read_text(encoding="utf-8"))["global_episode"], 7)
        catalog = json.loads((self.data / "media_catalog.json").read_text(encoding="utf-8"))
        new_rel = "W02/reels/tue_1_topic2/tue_1_topic2_final_reel.mp4"
        self.assertIn(new_rel, catalog["assets"])
        self.assertIn("W02\\reels\\tue_1_topic2\\thumbnail.jpg", catalog["assets"][new_rel]["published"]["youtube"]["details"]["thumbnail"])
        sched = json.loads((self.data / "posting_schedule.json").read_text(encoding="utf-8"))[0]
        self.assertEqual((sched["video_rel_path"], sched["video_filename"]), (new_rel, "tue_1_topic2_final_reel.mp4"))
        self.assertEqual(sched["thumbnail_url"], f"/api/thumbnail/{new_rel}")
        story_map = json.loads((self.data / "story_map_data.json").read_text(encoding="utf-8"))
        self.assertEqual(story_map["x"]["video_url"], f"/api/media/{new_rel}?t=1")
        story = json.loads((self.project / "W02" / "stories" / "09_story" / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(story["reel"], "tue_1")
        week = json.loads((self.project / "W02" / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(week["reels"][1]["folder"], "tue_1_topic2")

    def test_undo_restores_everything(self):
        _, log = self.run_apply()
        rename.undo(Path(log["backup_dir"]) / "rename_log.json")
        self.assertTrue((self.project / "W02" / "reels" / "02_topic2" / "temp" / "02_topic2_voice_script.txt").exists())
        for path, content in self.originals.items():
            self.assertEqual(path.read_bytes(), content)
        story = json.loads((self.project / "W02" / "stories" / "09_story" / "metadata.json").read_text(encoding="utf-8"))
        self.assertNotIn("reel", story)

    def test_a_similar_folder_name_is_not_touched(self):
        self.assertEqual(rename.rewrite_path("W02/reels/02_topic22/a.mp4", "W02", "02_topic2", "tue_1_topic2"),
                         "W02/reels/02_topic22/a.mp4")
        self.assertEqual(recorded_reel_number(self.project / "W02" / "reels" / "01_topic1"), None)


if __name__ == "__main__":
    unittest.main()
