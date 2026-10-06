"""Custom thumbnails on Facebook videos and Reels, and covers on Instagram Reels."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (blocks network before core modules load)
import core.meta_uploader
from core.meta_uploader import MetaUploader
from PIL import Image


def response(status=200, body=None):
    r = mock.Mock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    r.content = b"{}"
    r.text = str(body)
    return r


class MetaThumbnailTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        d = Path(self.tmp.name)
        self.video = d / "reel.mp4"
        self.video.write_bytes(b"\x00" * 2048)
        self.thumb = d / "thumbnail.jpg"
        Image.new("RGB", (108, 192), (200, 150, 50)).save(self.thumb, "JPEG")
        self.uploader = MetaUploader(page_id="1", page_token="test-token", ig_user_id="2")
        patcher = mock.patch.object(core.meta_uploader, "THUMB_RETRY_SEC", 0)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_facebook_video_sends_the_thumbnail_with_the_upload(self):
        side = [
            response(200, {"video_id": "fb1", "upload_session_id": "s1", "start_offset": "0", "end_offset": "2048"}),
            response(200, {"start_offset": "2048", "end_offset": "2048"}),
            response(200, {"success": True}),
        ]
        with mock.patch("core.meta_uploader.requests.post", side_effect=side) as post, \
                mock.patch.object(self.uploader, "_first_comment", return_value=None):
            res = self.uploader.upload_facebook_video(self.video, "T", "D", thumbnail_path=self.thumb)
        self.assertEqual(res["status"], "published")
        self.assertTrue(res["thumbnail_attached"])
        # The thumbnail goes with the finish step
        self.assertEqual(post.call_args.kwargs["data"]["upload_phase"], "finish")
        self.assertIn("thumb", post.call_args.kwargs["files"])

    def reel(self, thumbnail_response):
        start = response(200, {"video_id": "v1", "upload_url": "https://rupload.test/v1"})
        finish = response(200, {"success": True})
        side = [start, response(200), finish] + thumbnail_response
        with mock.patch("core.meta_uploader.requests.post", side_effect=side) as post, \
                mock.patch.object(self.uploader, "_first_comment", return_value=None):
            res = self.uploader.upload_facebook_reel(self.video, "T", "D", thumbnail_path=self.thumb)
        return res, post

    def test_facebook_reel_sets_its_thumbnail_after_publishing(self):
        res, post = self.reel([response(200, {"success": True})])
        self.assertEqual(res["status"], "published")
        self.assertTrue(res["thumbnail_attached"])
        self.assertTrue(post.call_args_list[-1].args[0].endswith("/v1/thumbnails"))

    def test_thumbnail_failure_never_fails_the_reel(self):
        err = response(400, {"error": {"message": "not ready"}})
        res, _ = self.reel([err, err, err])
        self.assertEqual(res["status"], "published")
        self.assertFalse(res["thumbnail_attached"])

    def test_instagram_cover_is_hosted_used_and_removed(self):
        with mock.patch.object(self.uploader, "_host_cover", return_value=("https://cdn.test/cover.jpg", "p1")), \
                mock.patch.object(self.uploader, "_upload_instagram_media", return_value={"status": "published"}) as inner, \
                mock.patch.object(self.uploader, "_delete_object") as delete:
            res = self.uploader.upload_instagram_reel(self.video, "caption", thumbnail_path=self.thumb)
        self.assertEqual(inner.call_args.args[5], "https://cdn.test/cover.jpg")
        delete.assert_called_once_with("p1")
        self.assertTrue(res["thumbnail_attached"])

    def test_instagram_retries_without_cover_when_processing_fails(self):
        failed = {"status": "failed", "error": "Meta video processing failed with status ERROR: bad cover"}
        with mock.patch.object(self.uploader, "_host_cover", return_value=("https://cdn.test/cover.jpg", "p1")), \
                mock.patch.object(self.uploader, "_upload_instagram_media", side_effect=[failed, {"status": "published"}]) as inner, \
                mock.patch.object(self.uploader, "_delete_object"):
            res = self.uploader.upload_instagram_reel(self.video, "caption", thumbnail_path=self.thumb)
        self.assertEqual(inner.call_count, 2)
        self.assertIsNone(inner.call_args.args[5])
        self.assertEqual(res["status"], "published")
        self.assertFalse(res["thumbnail_attached"])

    def test_instagram_container_carries_the_cover_url(self):
        with mock.patch.object(MetaUploader, "prepare_compliant_instagram_video", return_value=(self.video, False)), \
                mock.patch("core.meta_uploader.requests.post", return_value=response(200, {"error": {"message": "stop"}})) as post:
            self.uploader._upload_instagram_media(self.video, "caption", None, None, "REELS", "https://cdn.test/c.jpg")
        self.assertEqual(post.call_args.kwargs["data"]["cover_url"], "https://cdn.test/c.jpg")

    def test_stories_get_no_cover(self):
        with mock.patch.object(self.uploader, "_host_cover") as host, \
                mock.patch.object(self.uploader, "_upload_instagram_media", return_value={"status": "published"}):
            res = self.uploader.upload_instagram_reel(self.video, "", media_type="STORIES", thumbnail_path=self.thumb)
        host.assert_not_called()
        self.assertNotIn("thumbnail_attached", res)

    def test_png_thumbnail_is_converted_to_jpeg(self):
        png = Path(self.tmp.name) / "thumb.png"
        Image.new("RGB", (64, 64)).save(png)
        out, is_temp = MetaUploader._thumbnail_jpeg(png)
        self.assertTrue(is_temp)
        with Image.open(out) as im:
            self.assertEqual(im.format, "JPEG")
        out.unlink()


if __name__ == "__main__":
    unittest.main()
