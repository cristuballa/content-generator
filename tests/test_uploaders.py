import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

import tests  # noqa: F401  (blocks network before core modules load)
import core.meta_uploader
from core.meta_uploader import MetaUploader
from core.youtube_uploader import youtube_uploader


def temp_video():
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(b"\0" * 16)
    return Path(f.name)


def response(status_code=200, payload=None):
    resp = mock.Mock(status_code=status_code, text="")
    resp.json.return_value = payload or {}
    return resp


class YouTubeUploaderTests(unittest.TestCase):
    def upload(self, description, tags, is_short=True):
        captured = {}

        class FakeInsert:
            def next_chunk(self):
                return None, {"id": "vid123"}

        class FakeYouTube:
            def videos(self):
                return self

            def insert(self, part, body, media_body):
                captured["body"] = body
                return FakeInsert()

        path = temp_video()
        try:
            with mock.patch.object(youtube_uploader, "get_credentials", return_value=object()), \
                    mock.patch("core.youtube_uploader.build", return_value=FakeYouTube()), \
                    mock.patch("core.youtube_uploader.MediaFileUpload"):
                res = youtube_uploader.upload_video(path, "Title", description, tags=tags, is_short=is_short)
        finally:
            path.unlink()
        return res, captured["body"]["snippet"]

    def test_does_not_mutate_callers_tags(self):
        tags = ["Bible", "Faith"]
        res, snippet = self.upload("Desc\n\n#Bible", tags)
        self.assertEqual(res["status"], "published")
        self.assertEqual(tags, ["Bible", "Faith"])
        self.assertIn("Shorts", snippet["tags"])

    def test_adds_shorts_hashtag_once_on_the_tag_line(self):
        _, snippet = self.upload("Desc\n\n#Bible #Faith", ["Bible"])
        self.assertTrue(snippet["description"].endswith("#Bible #Faith #Shorts"))
        _, snippet = self.upload("Desc\n\n#Shorts", ["Bible"])
        self.assertEqual(snippet["description"].count("#Shorts"), 1)

    def test_never_exceeds_youtube_hashtag_limit(self):
        desc = "Desc\n\n" + " ".join(f"#Tag{chr(65 + i)}" for i in range(15))
        _, snippet = self.upload(desc, ["Bible"])
        self.assertNotIn("#Shorts", snippet["description"])

    def test_discloses_synthetic_media_and_sanitizes_title(self):
        captured = {}

        class FakeInsert:
            def next_chunk(self):
                return None, {"id": "vid123"}

        class FakeYouTube:
            def videos(self):
                return self

            def insert(self, part, body, media_body):
                captured["body"] = body
                return FakeInsert()

        path = temp_video()
        try:
            with mock.patch.object(youtube_uploader, "get_credentials", return_value=object()), \
                    mock.patch("core.youtube_uploader.build", return_value=FakeYouTube()), \
                    mock.patch("core.youtube_uploader.MediaFileUpload"):
                res = youtube_uploader.upload_video(
                    path,
                    "Title With <Invalid> Characters",
                    "Description with raw link: https://unsafe.com and bit.ly/test\n\n#Bible",
                    tags=["Bible"]
                )
        finally:
            path.unlink()

        self.assertEqual(res["status"], "published")
        # Rule 7: Altered or synthetic content disclosure
        self.assertTrue(captured["body"]["status"].get("containsSyntheticMedia"))
        # Title sanitization (no < or >)
        self.assertEqual(captured["body"]["snippet"]["title"], "Title With Invalid Characters")
        # Description sanitization (no raw URLs)
        self.assertNotIn("https://", captured["body"]["snippet"]["description"])
        self.assertNotIn("bit.ly", captured["body"]["snippet"]["description"])


class MetaUploaderTests(unittest.TestCase):
    def setUp(self):
        self.uploader = MetaUploader(page_id="1", page_token="test-token", ig_user_id="2")
        self.video = temp_video()

    def tearDown(self):
        self.video.unlink()

    def reel(self, post_side_effect):
        with mock.patch("core.meta_uploader.requests.post", side_effect=post_side_effect) as post, \
                mock.patch.object(self.uploader, "upload_facebook_video", return_value={"status": "published"}) as fallback:
            res = self.uploader.upload_facebook_reel(self.video, "Title", "Description")
        return res, post, fallback

    def test_no_hardcoded_page_token(self):
        source = Path(core.meta_uploader.__file__).read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"EAA[A-Za-z0-9]{30,}", source))

    def test_falls_back_to_regular_video_when_reels_start_fails(self):
        res, _, fallback = self.reel([response(400, {"error": {"message": "(#200) permissions"}})])
        fallback.assert_called_once()
        self.assertEqual(res["status"], "published")

    def test_no_reupload_after_the_upload_started(self):
        start = response(200, {"video_id": "v1", "upload_url": "https://rupload.test/v1"})
        res, _, fallback = self.reel([start, requests.exceptions.Timeout("slow")])
        fallback.assert_not_called()
        self.assertEqual(res["status"], "failed")
        self.assertIn("v1", res["error"])

    def test_failed_binary_upload_is_not_reported_published(self):
        start = response(200, {"video_id": "v1", "upload_url": "https://rupload.test/v1"})
        res, post, fallback = self.reel([start, response(500)])
        fallback.assert_not_called()
        self.assertEqual(res["status"], "failed")
        self.assertEqual(post.call_count, 2)

    def test_finish_error_is_not_reported_published(self):
        start = response(200, {"video_id": "v1", "upload_url": "https://rupload.test/v1"})
        finish = response(200, {"error": {"message": "Video processing failed"}})
        res, _, fallback = self.reel([start, response(200), finish])
        fallback.assert_not_called()
        self.assertEqual(res["status"], "failed")



class MetaCredentialTests(unittest.TestCase):
    def setUp(self):
        # Never pick up the real saved token (data/meta_token.json)
        with mock.patch.object(core.meta_uploader, "load_meta_credentials", return_value={}):
            self.uploader = MetaUploader(page_id="1", page_token="", ig_user_id="2")
        self.tmp = tempfile.TemporaryDirectory()
        self.token_file = Path(self.tmp.name) / "meta_token.json"
        self.file_patch = mock.patch.object(core.meta_uploader, "META_TOKEN_FILE", self.token_file)
        self.file_patch.start()

    def tearDown(self):
        self.file_patch.stop()
        self.tmp.cleanup()

    def test_rejected_token_is_not_saved(self):
        with mock.patch.object(self.uploader, "get_status", return_value={"configured": False, "error": "Invalid OAuth access token"}):
            res = self.uploader.save_credentials("bad-token")
        self.assertFalse(res["success"])
        self.assertEqual(self.uploader.page_token, "")
        self.assertFalse(self.token_file.exists())

    def test_valid_token_is_saved_and_used_immediately(self):
        status = {"configured": True, "facebook": {"page_id": "1"}, "instagram": {"ig_id": "99", "active": True}}
        with mock.patch.object(self.uploader, "get_status", return_value=status), \
                mock.patch.object(self.uploader, "missing_permissions", return_value=["pages_manage_posts"]):
            res = self.uploader.save_credentials("good-token")
        self.assertTrue(res["success"])
        self.assertIn("pages_manage_posts", res["warning"])
        self.assertEqual(self.uploader.page_token, "good-token")
        self.assertEqual(self.uploader.ig_user_id, "99")
        self.assertIn("good-token", self.token_file.read_text(encoding="utf-8"))



class InstagramChunkedUploadTests(unittest.TestCase):
    def setUp(self):
        self.uploader = MetaUploader(page_id="1", page_token="t", ig_user_id="2")
        self.path = Path(tempfile.mkdtemp()) / "v.mp4"
        self.path.write_bytes(b"x" * 10)

    def tearDown(self):
        self.path.unlink()

    def test_uploads_in_pieces_until_meta_confirms(self):
        with mock.patch.object(core.meta_uploader, "UPLOAD_CHUNK", 4), \
                mock.patch("core.meta_uploader.requests.post", side_effect=[response(206), response(206), response(200)]) as post:
            self.assertTrue(self.uploader._resumable_upload("https://rupload.test/c1", self.path)["success"])
        offsets = [c.kwargs["headers"]["offset"] for c in post.call_args_list]
        self.assertEqual(offsets, ["0", "4", "8"])
        self.assertEqual([len(c.kwargs["data"]) for c in post.call_args_list], [4, 4, 2])

    def test_resumes_from_the_offset_meta_reports(self):
        with mock.patch.object(core.meta_uploader, "UPLOAD_CHUNK", 4), \
                mock.patch("core.meta_uploader.time.sleep"), \
                mock.patch("core.meta_uploader.requests.get", return_value=response(200, {"offset": 4})), \
                mock.patch("core.meta_uploader.requests.post",
                           side_effect=[response(206), requests.exceptions.Timeout("slow"), response(206), response(200)]) as post:
            self.assertTrue(self.uploader._resumable_upload("https://rupload.test/c1", self.path)["success"])
        self.assertEqual([c.kwargs["headers"]["offset"] for c in post.call_args_list], ["0", "4", "4", "8"])

    def test_gives_up_after_repeated_failures(self):
        with mock.patch.object(core.meta_uploader, "UPLOAD_CHUNK", 4), \
                mock.patch("core.meta_uploader.time.sleep"), \
                mock.patch("core.meta_uploader.requests.get", return_value=response(200, {"offset": 0})), \
                mock.patch("core.meta_uploader.requests.post", return_value=response(400)):
            res = self.uploader._resumable_upload("https://rupload.test/c1", self.path)
        self.assertFalse(res["success"])


if __name__ == "__main__":
    unittest.main()
