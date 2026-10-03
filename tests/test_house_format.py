"""
House caption format (HOOK / scriptures / description / hashtags, no links) and the links comment
posted after publishing, including scheduled posts.
"""

import asyncio
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (blocks network before core modules load)
from core.hashtags import find_hashtags
from core.meta_uploader import MetaUploader
from core.social_dispatcher import DEFAULT_BHRS_PINNED_COMMENT, SocialDispatcher as SD, social_dispatcher
from core.youtube_uploader import youtube_uploader

EPISODE = {
    "title": "What Happened BEFORE Genesis 1:1? The Secret Pre-Creation War [Full Documentary]",
    "hook": "WHAT HAPPENED BEFORE THE FOUNDATION OF THE WORLD?",
    "scriptures": "Job 38:4-7, Proverbs 8:22-31, John 1:1-14",
    "description": (
        "The Bible opens at Genesis 1:1... but what happened BEFORE the foundation of the world?\n\n"
        "TIMESTAMPS / CHAPTERS:\n00:00 - The Silence Before Creation\n04:15 - The Divine Council"
    ),
    "hashtags": ["#WhatHappenedBeforeGenesis", "#Genesis1:1", "#Pre-CosmicFall", "#LuciferBeforeEden"],
    "merch_block": "=====================\n🛒 OFFICIAL MERCH & BOOKS:\n✨ Etsy Store: https://www.etsy.com/shop/X\n=====================",
    "facebook_caption": "old caption with https://www.etsy.com/shop/X\n\n📖 Official Books & Sacred Art collection linked in the pinned comment below 👇"
}

EXPECTED_FACEBOOK = (
    "WHAT HAPPENED BEFORE THE FOUNDATION OF THE WORLD?\n\n"
    "Job 38:4-7, Proverbs 8:22-31, John 1:1-14\n\n"
    "The Bible opens at Genesis 1:1... but what happened BEFORE the foundation of the world?\n\n"
    "#WhatHappenedBeforeGenesis #Genesis1 #PreCosmicFall #LuciferBeforeEden"
)


class HouseFormatTests(unittest.TestCase):
    def setUp(self):
        self.caps = SD.build_platform_captions(EPISODE)

    def test_facebook_matches_the_house_post(self):
        self.assertEqual(self.caps["facebook_caption"], EXPECTED_FACEBOOK)

    def test_no_links_or_merch_in_any_caption(self):
        for key in ("facebook_caption", "youtube_description", "instagram_caption", "tiktok_caption", "threads_caption"):
            with self.subTest(key=key):
                self.assertNotIn("http", self.caps[key])
                self.assertNotIn("OFFICIAL MERCH", self.caps[key])
                self.assertNotIn("pinned comment", self.caps[key].lower())

    def test_chapters_only_in_youtube(self):
        self.assertNotIn("00:00", self.caps["facebook_caption"])
        self.assertIn("TIMESTAMPS:\n00:00 - The Silence Before Creation\n04:15 - The Divine Council", self.caps["youtube_description"])

    def test_platform_specific_tags(self):
        self.assertNotIn("#LuciferBeforeEden", self.caps["instagram_caption"])
        self.assertEqual(len(find_hashtags(self.caps["threads_caption"])), 1)
        self.assertLessEqual(len(self.caps["threads_caption"]), 500)

    def test_comment_is_the_links_comment(self):
        self.assertEqual(self.caps["pinned_comment"], DEFAULT_BHRS_PINNED_COMMENT)
        self.assertTrue(DEFAULT_BHRS_PINNED_COMMENT.startswith("🛒 OFFICIAL MERCH & SACRED BOOKS:"))
        self.assertIn("https://www.etsy.com/shop/BibleHiddenGems", DEFAULT_BHRS_PINNED_COMMENT)

    def test_reel_caption_with_inline_tags(self):
        caps = SD.build_platform_captions({
            "hook": "How was there light on Day 1?",
            "scriptures": "Genesis 1:1-31",
            "caption": "Quantum physics and theology answer it. #Genesis1 #LetThereBeLight",
            "hashtags": ["#Genesis1", "#ScienceAndFaith"]
        })
        self.assertEqual(
            caps["facebook_caption"],
            "HOW WAS THERE LIGHT ON DAY 1?\n\nGenesis 1:1-31\n\nQuantum physics and theology answer it.\n\n"
            "#Genesis1 #ScienceAndFaith #LetThereBeLight"
        )

    def test_legacy_caption_is_cleaned_at_publish_time(self):
        legacy = (
            "Hook\n\nBody text.\n\n=====================\n🛒 OFFICIAL MERCH & BOOKS:\n"
            "📖 Book 1 (Amazon): https://www.amazon.com/dp/X\n=====================\n\n"
            "📖 Official Books & Sacred Art collection linked in the pinned comment below 👇\n\n#Faith"
        )
        self.assertEqual(SD.sanitize_caption_for_facebook(legacy), "Hook\n\nBody text.\n\n#Faith")

    def test_older_metadata_txt(self):
        txt = (
            "EPISODE 051 — METADATA\n=======\n🛒 OFFICIAL MERCH & BOOKS (Link in Bio):\n=======\n\n"
            "HASHTAGS:\n#BibleSecrets #Prophecy\n\n"
            "YOUTUBE SHORTS TITLE: The First Prophecy of Jesus | Bible Secrets #51\n"
            "FACEBOOK CAPTION: God's first promise was hidden in a curse.\n📖 Check our books & merch: https://www.etsy.com/x #BibleSecrets\n"
            "EDITING:\n- Captions: template"
        )
        caps = SD.build_platform_captions(SD.parse_metadata_txt(txt))
        self.assertEqual(
            caps["facebook_caption"],
            "THE FIRST PROPHECY OF JESUS\n\nGod's first promise was hidden in a curse.\n\n#BibleSecrets #Prophecy"
        )


class CommentAfterPostingTests(unittest.TestCase):
    def youtube_upload(self, scheduled_iso=None):
        class FakeInsert:
            def next_chunk(self):
                return None, {"id": "vid123"}

        class FakeYouTube:
            def videos(self):
                return self

            def insert(self, part, body, media_body):
                return FakeInsert()

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            f.write(b"\0" * 16)
        path = Path(f.name)
        try:
            with mock.patch.object(youtube_uploader, "get_credentials", return_value=object()), \
                    mock.patch("core.youtube_uploader.build", return_value=FakeYouTube()), \
                    mock.patch("core.youtube_uploader.MediaFileUpload"), \
                    mock.patch.object(youtube_uploader, "post_comment", return_value={"success": True, "id": "c1"}) as post:
                res = youtube_uploader.upload_video(path, "Title", "Desc", is_short=False,
                                                    scheduled_publish_iso=scheduled_iso, pinned_comment="Links!")
        finally:
            path.unlink()
        return res, post

    def test_youtube_comments_right_after_a_live_upload(self):
        res, post = self.youtube_upload()
        post.assert_called_once()
        self.assertTrue(res["comment_posted"])
        self.assertNotIn("pending_comment", res)

    def test_youtube_queues_the_comment_for_a_scheduled_upload(self):
        res, post = self.youtube_upload("2030-01-01T10:00:00.000Z")
        post.assert_not_called()
        self.assertEqual(res["pending_comment"], "Links!")
        self.assertGreater(res["comment_due_at"], time.time())

    def test_facebook_queues_the_comment_for_a_scheduled_post(self):
        uploader = MetaUploader(page_id="1", page_token="t", ig_user_id="2")
        with mock.patch.object(uploader, "post_comment") as post:
            self.assertEqual(uploader._first_comment("v1", "Links!", 1893456000)["status"], "queued")
            post.assert_not_called()
        self.assertEqual(uploader._pending_comment_fields("Links!", 1893456000),
                         {"pending_comment": "Links!", "comment_due_at": 1893456060})
        self.assertEqual(uploader._pending_comment_fields("Links!", None), {})

    def test_scheduler_posts_due_comments_once(self):
        published = {
            ("a.mp4", "youtube"): {"id": "vid1", "pending_comment": "Links!", "comment_due_at": time.time() - 5},
            ("b.mp4", "facebook"): {"id": "fb1", "pending_comment": "Links!", "comment_due_at": time.time() + 3600},
            ("c.mp4", "facebook"): {"id": "fb2", "pending_comment": "Links!", "comment_due_at": time.time() - 5}
        }
        assets = mock.Mock()
        assets.iter_published.side_effect = lambda: ((rel, plat, d) for (rel, plat), d in published.items())
        assets.get_asset_record.side_effect = lambda rel: {
            "published": {plat: {"details": d} for (r, plat), d in published.items() if r == rel}
        }

        def fake_post(platform, object_id, text):
            return {"success": True, "id": "c1"} if platform == "youtube" else {"success": False, "error": "not live yet"}

        with mock.patch("core.social_dispatcher.asset_manager", assets), \
                mock.patch.object(SD, "_post_comment", side_effect=fake_post) as post:
            posted = asyncio.run(social_dispatcher.post_due_comments())
            self.assertEqual(posted, 1)
            self.assertEqual(post.call_count, 2)  # b.mp4 isn't due yet

            yt = published[("a.mp4", "youtube")]
            self.assertTrue(yt["comment_posted"])
            self.assertNotIn("pending_comment", yt)

            fb = published[("c.mp4", "facebook")]
            self.assertEqual(fb["pending_comment"], "Links!")  # kept for a retry
            self.assertEqual(fb["comment_attempts"], 1)
            self.assertGreater(fb["comment_due_at"], time.time())

            asyncio.run(social_dispatcher.post_due_comments())  # nothing new is due: no duplicate comment
            self.assertEqual(post.call_count, 2)
        assets.save.assert_called()

    def test_comment_routing(self):
        with mock.patch("core.social_dispatcher.threads_uploader") as threads, \
                mock.patch("core.social_dispatcher.meta_uploader") as meta:
            social_dispatcher._post_comment("threads", "t1", "Links!")
            social_dispatcher._post_comment("instagram", "ig1", "Links!")
        threads.post_reply.assert_called_once_with("t1", "Links!")
        meta.post_comment.assert_called_once_with("ig1", "Links!")


if __name__ == "__main__":
    unittest.main()
