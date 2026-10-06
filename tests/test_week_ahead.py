"""Week-ahead scheduling: Facebook chunked uploads, staging YouTube / Facebook copies ahead of time, keeping those
copies in step with calendar edits, and the Business Suite hand-off for Instagram and Facebook Stories."""
import asyncio
import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (blocks network before core modules load)
import core.meta_uploader
import core.staging as staging
from core.calendar_manager import CalendarManager, PostBusyError
from core.meta_uploader import MetaUploader
from core.youtube_uploader import YouTubeUploader


def response(status=200, body=None):
    r = mock.Mock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    r.content = b"{}"
    r.text = str(body)
    return r


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


# ------------------------------------------------------------------------------------------------------------------
# Facebook long-form: start -> transfer -> finish
# ------------------------------------------------------------------------------------------------------------------
class FacebookChunkedUploadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.video = Path(self.tmp.name) / "episode.mp4"
        self.video.write_bytes(b"\x01" * 3000)
        self.uploader = MetaUploader(page_id="1", page_token="test-token", ig_user_id="2")
        for target, value in (("time.sleep", None), ("core.meta_uploader.THUMB_RETRY_SEC", 0)):
            p = mock.patch(target, return_value=value) if target == "time.sleep" else mock.patch(target, value)
            p.start()
            self.addCleanup(p.stop)

    START = response(200, {"video_id": "v9", "upload_session_id": "s1", "start_offset": "0", "end_offset": "1000"})

    def upload(self, posts, **kwargs):
        with mock.patch("core.meta_uploader.requests.post", side_effect=posts) as post, \
                mock.patch.object(self.uploader, "delete_video", return_value={"success": True}) as delete, \
                mock.patch.object(self.uploader, "_first_comment", return_value=None):
            res = self.uploader.upload_facebook_video(self.video, "Title", "Caption", **kwargs)
        return res, post, delete

    def test_sends_the_ranges_facebook_asks_for_then_schedules(self):
        posts = [self.START,
                 response(200, {"start_offset": "1000", "end_offset": "3000"}),
                 response(200, {"start_offset": "3000", "end_offset": "3000"}),
                 response(200, {"success": True})]
        res, post, delete = self.upload(posts, scheduled_timestamp=1900000000, pinned_comment="Links")
        self.assertEqual(res["status"], "published")
        self.assertTrue(res["scheduled"])
        self.assertEqual(res["id"], "v9")
        self.assertEqual(res["pending_comment"], "Links")
        sizes = [len(c.kwargs["files"]["video_file_chunk"][1]) for c in post.call_args_list[1:3]]
        self.assertEqual(sizes, [1000, 2000])
        finish = post.call_args_list[3].kwargs["data"]
        self.assertEqual(finish["upload_phase"], "finish")
        self.assertEqual(finish["published"], "false")
        self.assertEqual(finish["scheduled_publish_time"], "1900000000")
        delete.assert_not_called()

    def test_a_failed_piece_is_retried(self):
        posts = [self.START,
                 response(500, {"error": {"message": "temporary"}}),
                 response(200, {"start_offset": "1000", "end_offset": "3000"}),
                 response(200, {"start_offset": "3000", "end_offset": "3000"}),
                 response(200, {"success": True})]
        res, post, _ = self.upload(posts)
        self.assertEqual(res["status"], "published")
        self.assertEqual(post.call_args_list[2].kwargs["data"]["start_offset"], "0")

    def test_finish_without_thumbnail_when_facebook_rejects_it(self):
        from PIL import Image
        thumb = Path(self.tmp.name) / "thumbnail.jpg"
        Image.new("RGB", (64, 36)).save(thumb)
        posts = [self.START,
                 response(200, {"start_offset": "3000", "end_offset": "3000"}),
                 response(200, {"error": {"message": "Invalid thumb"}}),
                 response(200, {"success": True})]
        with mock.patch.object(self.uploader, "_set_video_thumbnail", return_value=True) as later:
            res, post, _ = self.upload(posts, thumbnail_path=thumb)
        self.assertEqual(res["status"], "published")
        self.assertIn("thumb", post.call_args_list[2].kwargs["files"])
        self.assertIsNone(post.call_args_list[3].kwargs["files"])
        later.assert_called_once_with("v9", thumb)
        self.assertTrue(res["thumbnail_attached"])

    def test_upload_that_keeps_failing_deletes_the_half_made_video(self):
        posts = [self.START] + [response(500, {"error": {"message": "down"}})] * 4
        res, _, delete = self.upload(posts)
        self.assertEqual(res["status"], "failed")
        delete.assert_called_once_with("v9")

    def test_rejected_finish_deletes_the_video(self):
        posts = [self.START, response(200, {"start_offset": "3000", "end_offset": "3000"}),
                 response(200, {"error": {"message": "Scheduled time too soon"}})]
        res, _, delete = self.upload(posts)
        self.assertEqual(res["status"], "failed")
        self.assertIn("too soon", res["error"])
        delete.assert_called_once_with("v9")

    def test_start_failure_reports_facebooks_message(self):
        res, _, delete = self.upload([response(400, {"error": {"message": "(#200) permissions"}})])
        self.assertEqual(res["status"], "failed")
        self.assertIn("permissions", res["error"])
        delete.assert_not_called()


# ------------------------------------------------------------------------------------------------------------------
# YouTube: move / release a waiting video
# ------------------------------------------------------------------------------------------------------------------
class YouTubePublishTimeTests(unittest.TestCase):
    def fake(self, status):
        captured = {}
        youtube = mock.Mock()
        youtube.videos.return_value.list.return_value.execute.return_value = {"items": [{"status": status}]}

        def update(part, body):
            captured["body"] = body
            return mock.Mock(execute=mock.Mock(return_value={}))
        youtube.videos.return_value.update.side_effect = update
        return youtube, captured

    STATUS = {"uploadStatus": "uploaded", "privacyStatus": "private", "publishAt": "2026-10-10T07:30:00Z",
              "selfDeclaredMadeForKids": False, "containsSyntheticMedia": True, "madeForKids": False, "license": "youtube"}

    def test_moves_only_the_publish_time_and_keeps_other_settings(self):
        youtube, captured = self.fake(dict(self.STATUS))
        res = YouTubeUploader().set_publish_time("abc", "2026-10-12T07:30:00.000Z", youtube=youtube)
        self.assertTrue(res["success"])
        status = captured["body"]["status"]
        self.assertEqual(status["publishAt"], "2026-10-12T07:30:00.000Z")
        self.assertEqual(status["privacyStatus"], "private")
        self.assertTrue(status["containsSyntheticMedia"])
        self.assertNotIn("uploadStatus", status)
        self.assertNotIn("madeForKids", status)

    def test_release_makes_it_public_now(self):
        youtube, captured = self.fake(dict(self.STATUS))
        YouTubeUploader().set_publish_time("abc", None, youtube=youtube)
        status = captured["body"]["status"]
        self.assertEqual(status["privacyStatus"], "public")
        self.assertNotIn("publishAt", status)


# ------------------------------------------------------------------------------------------------------------------
# Calendar helpers
# ------------------------------------------------------------------------------------------------------------------
CFG = {"stage_ahead_days": 7, "dry_run": False, "business_suite": {"instagram": True, "facebook_stories": True}}
REEL = "W03/reels/01_reel/final_reel.mp4"
STORY = "W03/stories/01_story/story_video_final.mp4"
LONG = "W03/long_form/01_ep/episode_final_16x9.mp4"


class CalendarCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        self.schedule = self.project / "schedule.json"
        self.schedule.write_text("[]", encoding="utf-8")
        self.cal = CalendarManager(schedule_file=self.schedule)
        self.cfg = json.loads(json.dumps(CFG))
        self.assets = mock.Mock()
        self.assets.get_asset_record.return_value = {"published": {}}
        self.assets.iter_published.return_value = []
        config = mock.Mock()
        config.get_project_social_config.side_effect = lambda *a, **k: self.cfg
        for target, value in (("core.calendar_manager.config_manager", config),
                              ("core.calendar_manager.asset_manager", self.assets)):
            p = mock.patch(target, value)
            p.start()
            self.addCleanup(p.stop)
        self.now = datetime.datetime.now().replace(microsecond=0)

    def add(self, post_id, rel, due, platforms=("youtube", "facebook", "instagram"), **extra):
        items = json.loads(self.schedule.read_text(encoding="utf-8"))
        items.append({"id": post_id, "status": "scheduled", "project_path": str(self.project), "video_rel_path": rel,
                      "platforms": list(platforms), "scheduled_date": due.strftime("%Y-%m-%d"),
                      "scheduled_time": due.strftime("%H:%M"), "scheduled_datetime_iso": iso(due), **extra})
        self.schedule.write_text(json.dumps(items), encoding="utf-8")

    def item(self, post_id):
        return self.cal.get_post_by_id(post_id)

    @staticmethod
    def dispatcher(results=None, side_effect=None):
        d = mock.Mock()
        d.publish_video = mock.AsyncMock(side_effect=side_effect, return_value=results)
        return d

    @staticmethod
    def staged_ok(*platforms):
        return {"success": True, "platforms": {p: {"status": "published", "scheduled": True, "id": f"{p}-1"} for p in platforms}}


# ------------------------------------------------------------------------------------------------------------------
# Staging ahead
# ------------------------------------------------------------------------------------------------------------------
class StagingTests(CalendarCase):
    def test_stages_posts_inside_the_window_only(self):
        self.add("soon", REEL, self.now + datetime.timedelta(minutes=10))
        self.add("in2days", REEL, self.now + datetime.timedelta(days=2))
        self.add("in10days", REEL, self.now + datetime.timedelta(days=10))
        d = self.dispatcher(self.staged_ok("youtube", "facebook"))
        staged = asyncio.run(self.cal.stage_upcoming_posts(d))
        self.assertEqual(staged, ["in2days"])
        kwargs = d.publish_video.call_args.kwargs
        self.assertEqual(kwargs["platforms"], ["youtube", "facebook"])
        self.assertEqual(kwargs["publish_mode"], "schedule")
        item = self.item("in2days")
        self.assertEqual(sorted(item["staged_platforms"]), ["facebook", "youtube"])
        self.assertEqual(item["staged_for"]["youtube"], item["scheduled_datetime_iso"])

    def test_stories_go_to_youtube_only(self):
        self.add("s", STORY, self.now + datetime.timedelta(days=1))
        d = self.dispatcher(self.staged_ok("youtube"))
        asyncio.run(self.cal.stage_upcoming_posts(d))
        self.assertEqual(d.publish_video.call_args.kwargs["platforms"], ["youtube"])

    def test_nothing_is_uploaded_in_dry_run_or_when_off(self):
        self.add("p", REEL, self.now + datetime.timedelta(days=1))
        d = self.dispatcher(self.staged_ok("youtube", "facebook"))
        self.cfg["dry_run"] = True
        asyncio.run(self.cal.stage_upcoming_posts(d))
        self.cfg["dry_run"], self.cfg["stage_ahead_days"] = False, 0
        asyncio.run(self.cal.stage_upcoming_posts(d))
        d.publish_video.assert_not_called()

    def test_youtube_quota_error_pauses_youtube_without_using_an_attempt(self):
        self.add("p", REEL, self.now + datetime.timedelta(days=1))
        d = self.dispatcher({"success": True, "platforms": {
            "youtube": {"status": "failed", "error": "HttpError 403: quotaExceeded"},
            "facebook": {"status": "published", "scheduled": True, "id": "fb"}}})
        asyncio.run(self.cal.stage_upcoming_posts(d))
        item = self.item("p")
        self.assertEqual(item["staged_platforms"], ["facebook"])
        self.assertNotIn("attempts", item["stage"]["youtube"])
        self.assertGreater(self.cal._youtube_paused_until, datetime.datetime.now().timestamp() + 5 * 3600)
        self.assertEqual(self.cal._platforms_to_stage(item, self.cfg, datetime.datetime.now().timestamp()), [])

    def test_a_failure_backs_off_and_gives_up_after_three(self):
        self.add("p", REEL, self.now + datetime.timedelta(days=1), platforms=["youtube"])
        d = self.dispatcher({"success": False, "platforms": {"youtube": {"status": "failed", "error": "boom"}}})
        asyncio.run(self.cal.stage_upcoming_posts(d))
        item = self.item("p")
        self.assertEqual(item["stage"]["youtube"]["attempts"], 1)
        self.assertGreater(item["stage"]["youtube"]["retry_at"], datetime.datetime.now().timestamp() + 60)
        item["stage"]["youtube"] = {"attempts": 3, "error": "boom", "retry_at": 0}
        self.assertEqual(self.cal._platforms_to_stage(item, self.cfg, datetime.datetime.now().timestamp()), [])
        self.assertEqual(self.cal._platform_states(item)["youtube"]["state"], "stage_failed")
        self.assertTrue(self.cal._platform_states(item)["youtube"]["gave_up"])

    def test_half_made_facebook_upload_is_deleted(self):
        self.add("p", REEL, self.now + datetime.timedelta(days=1), platforms=["facebook"])
        d = self.dispatcher({"success": False, "platforms": {"facebook": {"status": "failed", "id": "fb7", "error": "finish"}}})
        with mock.patch("core.calendar_manager.meta_uploader") as meta:
            asyncio.run(self.cal.stage_upcoming_posts(d))
        meta.delete_video.assert_called_once_with("fb7")

    def test_changes_made_during_an_upload_are_kept(self):
        self.add("p", REEL, self.now + datetime.timedelta(days=1), platforms=["youtube"])
        self.add("other", REEL.replace("01_reel", "02_reel"), self.now + datetime.timedelta(days=30))

        async def slow_upload(**kwargs):
            # The user edits another post while the upload runs
            items = json.loads(self.schedule.read_text(encoding="utf-8"))
            items[1]["title"] = "Edited meanwhile"
            self.schedule.write_text(json.dumps(items), encoding="utf-8")
            return self.staged_ok("youtube")
        d = self.dispatcher(side_effect=slow_upload)
        asyncio.run(self.cal.stage_upcoming_posts(d))
        self.assertEqual(self.item("other")["title"], "Edited meanwhile")
        self.assertEqual(self.item("p")["staged_platforms"], ["youtube"])

    def test_a_post_being_uploaded_is_not_posted_twice(self):
        self.add("p", REEL, self.now - datetime.timedelta(minutes=1), platforms=["youtube"])
        self.cal._busy.add("p")
        d = self.dispatcher(self.staged_ok("youtube"))
        self.assertEqual(asyncio.run(self.cal.execute_due_posts(d)), [])
        d.publish_video.assert_not_called()
        with self.assertRaises(PostBusyError):
            asyncio.run(self.cal.remove_post("p"))

    def test_staged_platforms_are_not_uploaded_again_when_due(self):
        self.add("p", REEL, self.now - datetime.timedelta(minutes=1), platforms=["youtube", "facebook"],
                 staged_platforms=["youtube", "facebook"])
        d = self.dispatcher(self.staged_ok())
        executed = asyncio.run(self.cal.execute_due_posts(d))
        d.publish_video.assert_not_called()
        self.assertEqual(executed[0]["status"], "posted")


# ------------------------------------------------------------------------------------------------------------------
# Calendar edits keep waiting copies in step
# ------------------------------------------------------------------------------------------------------------------
class StagedEditTests(CalendarCase):
    def setUp(self):
        super().setUp()
        self.due = (self.now + datetime.timedelta(days=3)).replace(second=0)
        self.add("p", LONG, self.due, platforms=["youtube", "facebook"], staged=True,
                 staged_platforms=["youtube", "facebook"], published_platforms=["youtube", "facebook"],
                 staged_for={"youtube": iso(self.due), "facebook": iso(self.due)})
        self.move = mock.patch("core.calendar_manager.move_copy", side_effect=lambda rel, p, due:
                               {"success": True} if p == "youtube" else {"success": False, "replace": True})
        self.cancel = mock.patch("core.calendar_manager.cancel_copy", return_value={"success": True})
        self.release = mock.patch("core.calendar_manager.release_copy", return_value={"success": True})
        self.move_m, self.cancel_m, self.release_m = self.move.start(), self.cancel.start(), self.release.start()
        for p in (self.move, self.cancel, self.release):
            self.addCleanup(p.stop)

    def test_reschedule_moves_youtube_and_replaces_facebook(self):
        new = self.due + datetime.timedelta(days=1)
        res = asyncio.run(self.cal.change_post("p", new.strftime("%Y-%m-%d"), new.strftime("%H:%M")))
        self.move_m.assert_any_call(LONG, "youtube", new)
        self.cancel_m.assert_called_once_with(LONG, "facebook")
        entry = res["entry"]
        self.assertEqual(entry["staged_platforms"], ["youtube"])
        self.assertEqual(entry["staged_for"]["youtube"], iso(new))
        self.assertEqual(entry["scheduled_datetime_iso"], iso(new))
        # The waiting YouTube copy's publish record is kept (only Facebook, now gone, may be cleared)
        cleared = [c.args[1] for c in self.assets.set_social_posted.call_args_list]
        self.assertNotIn("youtube", cleared)
        self.assertFalse(res["errors"])

    def test_saving_without_a_time_change_touches_nothing(self):
        asyncio.run(self.cal.change_post("p", self.due.strftime("%Y-%m-%d"), self.due.strftime("%H:%M")))
        self.move_m.assert_not_called()
        self.cancel_m.assert_not_called()

    def test_unticked_platform_copy_is_deleted(self):
        res = asyncio.run(self.cal.change_post("p", self.due.strftime("%Y-%m-%d"), self.due.strftime("%H:%M"),
                                               platforms=["youtube"]))
        self.cancel_m.assert_called_once_with(LONG, "facebook")
        self.assertEqual(res["entry"]["staged_platforms"], ["youtube"])

    def test_remove_deletes_waiting_copies(self):
        res = asyncio.run(self.cal.remove_post("p"))
        self.assertTrue(res["success"])
        self.assertEqual(sorted(res["deleted_copies"]), ["facebook", "youtube"])
        self.assertIsNone(self.item("p"))

    def test_remove_keeps_the_post_when_a_copy_cannot_be_deleted(self):
        self.cancel_m.side_effect = lambda rel, p: {"success": p == "youtube", "error": "Facebook said no"}
        res = asyncio.run(self.cal.remove_post("p"))
        self.assertFalse(res["success"])
        self.assertIn("Facebook said no", res["errors"][0])
        self.assertEqual(self.item("p")["staged_platforms"], ["facebook"])

    def test_live_copies_are_never_deleted(self):
        past = self.now - datetime.timedelta(hours=1)
        items = json.loads(self.schedule.read_text(encoding="utf-8"))
        items[0]["staged_for"] = {"youtube": iso(past), "facebook": iso(past)}
        self.schedule.write_text(json.dumps(items), encoding="utf-8")
        res = asyncio.run(self.cal.remove_post("p"))
        self.assertTrue(res["success"])
        self.cancel_m.assert_not_called()

    def test_post_now_releases_youtube_and_replaces_facebook(self):
        out = asyncio.run(self.cal.release_staged("p", ["youtube", "facebook"]))
        self.assertEqual(out["released"], ["youtube"])
        self.assertEqual(out["replaced"], ["facebook"])
        self.release_m.assert_called_once_with(LONG, "youtube")
        self.assertEqual(self.item("p")["staged_platforms"], ["youtube"])

    def test_restage_replaces_the_waiting_copies(self):
        d = self.dispatcher(self.staged_ok("youtube", "facebook"))
        res = asyncio.run(self.cal.pre_upload_post("p", ["youtube", "facebook"], d, replace=True))
        self.assertEqual(self.cancel_m.call_count, 2)
        self.assertTrue(res["success"])
        self.assertEqual(sorted(self.item("p")["staged_platforms"]), ["facebook", "youtube"])

    def test_scheduling_the_video_again_does_not_drop_its_waiting_copies(self):
        with self.assertRaises(ValueError):
            self.cal.schedule_video(str(self.project), LONG, date_str=self.due.strftime("%Y-%m-%d"), time_str="09:00",
                                    platforms=["youtube"], title="T")


# ------------------------------------------------------------------------------------------------------------------
# Copy operations on a platform
# ------------------------------------------------------------------------------------------------------------------
class CopyOperationTests(unittest.TestCase):
    def setUp(self):
        self.details = {"id": "yt1", "scheduled": True, "pending_comment": "Links", "comment_due_at": 0}
        self.assets = mock.Mock()
        self.assets.get_asset_record.return_value = {"published": {"youtube": {"details": self.details},
                                                                   "facebook": {"details": {"id": "fb1"}}}}
        for target, value in (("core.staging.asset_manager", self.assets),):
            p = mock.patch(target, value)
            p.start()
            self.addCleanup(p.stop)

    def test_move_updates_the_record(self):
        new_due = datetime.datetime(2030, 5, 1, 7, 30)
        with mock.patch("core.staging.youtube_uploader") as yt:
            yt.set_publish_time.return_value = {"success": True}
            res = staging.move_copy("r.mp4", "youtube", new_due)
        self.assertTrue(res["success"])
        self.assertEqual(self.details["scheduled_for"], staging.to_utc_iso(new_due))
        self.assertEqual(self.details["comment_due_at"], int(new_due.timestamp()) + 60)

    def test_facebook_asks_to_be_replaced(self):
        self.assertTrue(staging.move_copy("r.mp4", "facebook", datetime.datetime(2030, 5, 1))["replace"])

    def test_cancel_deletes_then_clears_the_record(self):
        with mock.patch("core.staging.meta_uploader") as meta:
            meta.delete_video.return_value = {"success": True}
            self.assertTrue(staging.cancel_copy("r.mp4", "facebook")["success"])
        meta.delete_video.assert_called_once_with("fb1")
        self.assets.set_social_posted.assert_called_once_with("r.mp4", "facebook", False)

    def test_failed_delete_keeps_the_record(self):
        with mock.patch("core.staging.youtube_uploader") as yt:
            yt.delete_video.return_value = {"success": False, "error": "nope"}
            self.assertFalse(staging.cancel_copy("r.mp4", "youtube")["success"])
        self.assets.set_social_posted.assert_not_called()


# ------------------------------------------------------------------------------------------------------------------
# Business Suite: Instagram and Facebook Stories by hand
# ------------------------------------------------------------------------------------------------------------------
class BusinessSuiteTests(CalendarCase):
    def test_due_posts_leave_instagram_and_facebook_stories_alone(self):
        self.add("reel", REEL, self.now - datetime.timedelta(minutes=1), platforms=["youtube", "facebook", "instagram"])
        self.add("story", STORY, self.now - datetime.timedelta(minutes=1), platforms=["youtube", "facebook", "instagram"])
        d = self.dispatcher(side_effect=lambda **kw: {"success": True, "platforms": {
            p: {"status": "published", "id": "x"} for p in kw["platforms"]}})
        executed = asyncio.run(self.cal.execute_due_posts(d))
        sent = [c.kwargs["platforms"] for c in d.publish_video.call_args_list]
        self.assertEqual(sent, [["youtube", "facebook"], ["youtube"]])
        self.assertEqual([e["status"] for e in executed], ["posted", "posted"])

    def test_checklist_lists_reels_and_stories_but_not_long_form(self):
        due = self.now + datetime.timedelta(days=1)
        self.add("reel", REEL, due)
        self.add("story", STORY, due)
        self.add("long", LONG, due)
        tasks = self.cal.business_suite_tasks(str(self.project), 7)
        self.assertEqual(sorted((t["post_id"], t["platform"]) for t in tasks),
                         [("reel", "instagram"), ("story", "facebook"), ("story", "instagram")])
        self.cal.set_manual_state("reel", "instagram", True)
        self.assertEqual(self.cal._platform_states(self.item("reel"))["instagram"]["step"], "scheduled")

    def test_live_reel_is_found_recorded_and_gets_its_comment_queued(self):
        due = self.now - datetime.timedelta(hours=2)
        self.add("reel", REEL, due)
        posted = (due + datetime.timedelta(minutes=1)).astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+0000")
        media = [{"id": "ig55", "caption": "The First Prophecy  hidden in a curse! #bible", "timestamp": posted,
                  "permalink": "https://instagram.com/reel/ig55", "media_product_type": "REELS"}]
        d = mock.Mock()
        d.compose_post_texts.return_value = {"captions": {"instagram": "The first prophecy, hidden in a curse #bible"},
                                             "pinned_comment": "Links comment"}
        with mock.patch("core.calendar_manager.meta_uploader") as meta, \
                mock.patch("core.calendar_manager.export_week_links") as export:
            meta.recent_instagram_media.return_value = media
            found = asyncio.run(self.cal.sync_business_suite_posts(d, now=datetime.datetime.now()))
        self.assertEqual(found, 1)
        rel, platform, details = self.assets.mark_published.call_args.args
        self.assertEqual((rel, platform, details["id"]), (REEL, "instagram", "ig55"))
        self.assertEqual(details["pending_comment"], "Links comment")
        export.assert_called_once()
        self.assertEqual(self.item("reel")["manual"]["instagram"]["state"], "live")

    def test_reel_not_found_after_three_days_is_reported_missing(self):
        self.add("reel", REEL, self.now - datetime.timedelta(days=4))
        d = mock.Mock()
        d.compose_post_texts.return_value = {"captions": {"instagram": "A caption that is long enough"}, "pinned_comment": "x"}
        with mock.patch("core.calendar_manager.meta_uploader") as meta:
            meta.recent_instagram_media.return_value = []
            asyncio.run(self.cal.sync_business_suite_posts(d, now=datetime.datetime.now()))
        self.assertEqual(self.item("reel")["manual"]["instagram"]["state"], "missing")


class InstagramMatchTests(unittest.TestCase):
    DUE = datetime.datetime(2026, 10, 8, 7, 30)

    def media(self, caption, minutes_after=5, mid="m1", kind="REELS"):
        ts = (self.DUE + datetime.timedelta(minutes=minutes_after)).astimezone(datetime.timezone.utc)
        return {"id": mid, "caption": caption, "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S+0000"), "media_product_type": kind}

    def test_matches_the_caption_opening_closest_to_the_time(self):
        far = self.media("Why the serpent was cursed first, a hidden", minutes_after=60 * 30, mid="far")
        near = self.media("Why the serpent was cursed first — a hidden", minutes_after=3, mid="near")
        m = staging.match_instagram_post("Why the serpent was cursed first: a hidden prophecy", self.DUE, [far, near])
        self.assertEqual(m["id"], "near")

    def test_ignores_other_captions_used_posts_and_old_posts(self):
        caption = "Why the serpent was cursed first: a hidden prophecy"
        self.assertIsNone(staging.match_instagram_post(caption, self.DUE, [self.media("A different reel entirely here")]))
        self.assertIsNone(staging.match_instagram_post(caption, self.DUE, [self.media(caption, mid="used")], ["used"]))
        self.assertIsNone(staging.match_instagram_post(caption, self.DUE, [self.media(caption, minutes_after=-60 * 48)]))
        self.assertIsNone(staging.match_instagram_post(caption, self.DUE, [self.media(caption, kind="FEED")]))


if __name__ == "__main__":
    unittest.main()
