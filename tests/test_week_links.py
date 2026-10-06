"""Reels point to the week's documentary: link lookup, comment composition, late edits and the week links file."""
import asyncio
import datetime
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (blocks network before core modules load)
import core.social_dispatcher as sd_module
import core.week_links as wl
from core.asset_manager import AssetManager

EP1 = "W05/long_form/01_cain_abel/W05_ep1_final_16x9.mp4"
EP2 = "W05/long_form/02_blood_cries/W05_ep2_final_16x9.mp4"
REEL1 = "W05/reels/01_why_god_rejected/01_why_god_rejected_final_reel.mp4"
REEL2 = "W05/reels/02_abels_lamb/02_abels_lamb_final_reel.mp4"


def pub(url=None, when=None, **details):
    d = dict(details)
    if url:
        d["url"] = url
    return {"status": "published", "time": when or time.time(), "details": d}


class WeekLinksBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name) / "BHSR"
        for rel in (EP1, EP2, REEL1, REEL2):
            (self.project / rel).parent.mkdir(parents=True, exist_ok=True)
        self.catalog = Path(self.tmp.name) / "catalog.json"

    def use_catalog(self, assets, supports=None):
        self.catalog.write_text(json.dumps({"assets": assets}), encoding="utf-8")
        am = AssetManager(data_file=self.catalog)
        for rel, ep in (supports or {}).items():
            (self.project / rel).parent.joinpath("metadata.json").write_text(
                json.dumps({"supports_long_form": ep}), encoding="utf-8")
        for target in (wl, sd_module):
            patcher = mock.patch.object(target, "asset_manager", am)
            patcher.start()
            self.addCleanup(patcher.stop)
        cfg = mock.patch.object(sd_module.config_manager, "get_active_project", return_value=str(self.project))
        cfg.start()
        self.addCleanup(cfg.stop)
        return am


class LookupTests(WeekLinksBase):
    def test_reel_uses_the_episode_it_supports(self):
        self.use_catalog({EP1: {"published": {"youtube": pub("https://youtu.be/ep1")}},
                          EP2: {"published": {"youtube": pub("https://youtu.be/ep2")}}},
                         supports={REEL1: "02_blood_cries"})
        self.assertEqual(wl.live_documentary_url(self.project, REEL1), "https://youtu.be/ep2")

    def test_falls_back_to_the_weeks_first_episode(self):
        self.use_catalog({EP1: {"published": {"youtube": pub("https://youtu.be/ep1")}},
                          EP2: {"published": {"youtube": pub("https://youtu.be/ep2")}}})
        self.assertEqual(wl.live_documentary_url(self.project, REEL2), "https://youtu.be/ep1")

    def test_newest_upload_of_an_episode_wins(self):
        old = "W05/long_form/01_cain_abel/W05_old_final_16x9.mp4"
        self.use_catalog({old: {"published": {"youtube": pub("https://youtu.be/old", when=1000)}},
                          EP1: {"published": {"youtube": pub("https://youtu.be/new", when=2000)}}})
        self.assertEqual(wl.live_documentary_url(self.project, REEL2), "https://youtu.be/new")

    def test_scheduled_documentary_is_not_used_before_it_goes_live(self):
        future = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        self.use_catalog({EP1: {"published": {"youtube": pub("https://youtu.be/ep1", scheduled=True, scheduled_for=future)}}})
        self.assertIsNone(wl.live_documentary_url(self.project, REEL2))

    def test_superseded_upload_is_never_linked(self):
        self.use_catalog({EP1: {"published": {"youtube": pub("https://youtu.be/short", when=2000, superseded=True)}},
                          EP2: {"published": {"youtube": pub("https://youtu.be/ep2", when=1000)}}})
        self.assertEqual(wl.live_documentary_url(self.project, REEL2), "https://youtu.be/ep2")

    def test_documentary_line_is_added_once(self):
        once = wl.with_documentary_link("Books and merch", "https://youtu.be/x")
        self.assertTrue(once.startswith("🎬 Watch the full documentary: https://youtu.be/x"))
        self.assertEqual(wl.with_documentary_link(once, "https://youtu.be/x"), once)
        self.assertEqual(wl.with_documentary_link("Books", None), "Books")


class LateDocumentaryTests(WeekLinksBase):
    def assets(self):
        return {
            EP1: {"published": {"youtube": pub("https://youtu.be/ep1")}},
            REEL1: {"published": {
                "youtube": pub("https://youtu.be/r1", id="r1", comment_id="c-yt", comment_text="Books and merch"),
                "facebook": pub("https://fb/r1", id="fb-r1", comment_text="Books and merch",
                                first_comment={"status": "posted", "comment_id": "c-fb"}),
                "instagram": pub("https://ig/r1", id="ig-r1", first_comment={"status": "posted", "comment_id": "c-ig"}),
            }},
            REEL2: {"published": {"youtube": pub("https://youtu.be/r2", id="r2", comment_text="Books and merch")}},
        }

    def run_update(self):
        with mock.patch.object(sd_module.youtube_uploader, "update_comment", return_value={"success": True}) as yt_up, \
                mock.patch.object(sd_module.meta_uploader, "update_comment", return_value={"success": True}) as fb_up, \
                mock.patch.object(sd_module.youtube_uploader, "post_comment", return_value={"success": True, "id": "c-new"}) as yt_post:
            asyncio.run(sd_module.social_dispatcher.update_documentary_links())
        return yt_up, fb_up, yt_post

    def test_edits_youtube_and_facebook_comments_and_skips_instagram(self):
        am = self.use_catalog(self.assets())
        yt_up, fb_up, yt_post = self.run_update()
        self.assertEqual(yt_up.call_args.args[0], "c-yt")
        self.assertIn("https://youtu.be/ep1", yt_up.call_args.args[1])
        self.assertIn("Books and merch", yt_up.call_args.args[1])
        self.assertEqual(fb_up.call_args.args[0], "c-fb")
        yt_post.assert_called_once()  # reel 2 had no comment yet: a new one is posted
        ig = am.get_asset_record(REEL1)["published"]["instagram"]["details"]
        self.assertNotIn("documentary_link", ig)
        self.assertEqual(am.get_asset_record(REEL2)["published"]["youtube"]["details"]["comment_id"], "c-new")
        links = json.loads((self.project / "W05" / "published_links.json").read_text(encoding="utf-8"))
        self.assertEqual(links["long_form"]["01_cain_abel"]["youtube"], "https://youtu.be/ep1")
        self.assertEqual(links["reels"]["01_why_god_rejected"]["documentary_link_in_comment"], "https://youtu.be/ep1")

    def test_reels_posted_before_this_feature_are_left_alone(self):
        assets = self.assets()
        for plat in ("youtube", "facebook"):
            assets[REEL1]["published"][plat]["details"].pop("comment_text")
        assets[REEL2]["published"]["youtube"]["details"].pop("comment_text")
        self.use_catalog(assets)
        yt_up, fb_up, yt_post = self.run_update()
        yt_up.assert_not_called()
        fb_up.assert_not_called()
        yt_post.assert_not_called()

    def test_second_run_makes_no_calls(self):
        self.use_catalog(self.assets())
        self.run_update()
        yt_up, fb_up, yt_post = self.run_update()
        yt_up.assert_not_called()
        fb_up.assert_not_called()
        yt_post.assert_not_called()

    def test_nothing_happens_before_the_documentary_is_live(self):
        assets = self.assets()
        del assets[EP1]
        self.use_catalog(assets)
        yt_up, fb_up, yt_post = self.run_update()
        yt_up.assert_not_called()
        fb_up.assert_not_called()
        yt_post.assert_not_called()

    def test_scheduled_reel_comment_picks_up_the_link_when_posted(self):
        am = self.use_catalog({
            EP1: {"published": {"youtube": pub("https://youtu.be/ep1")}},
            REEL1: {"published": {"youtube": pub("https://youtu.be/r1", id="r1", pending_comment="Books and merch",
                                                 comment_due_at=0)}},
        })
        with mock.patch.object(sd_module.youtube_uploader, "post_comment", return_value={"success": True, "id": "c1"}) as post:
            asyncio.run(sd_module.social_dispatcher.post_due_comments())
        self.assertTrue(post.call_args.args[1].startswith("🎬 Watch the full documentary: https://youtu.be/ep1"))
        details = am.get_asset_record(REEL1)["published"]["youtube"]["details"]
        self.assertEqual(details["documentary_link"], "https://youtu.be/ep1")
        self.assertNotIn("pending_comment", details)


if __name__ == "__main__":
    unittest.main()
