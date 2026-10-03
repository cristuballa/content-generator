import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tests  # noqa: F401  (blocks network before core modules load)
from fastapi.testclient import TestClient

import app as app_module
from core.config import config_manager


class ApiPathSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        (root / "W01" / "long_form").mkdir(parents=True)
        (root / "W01" / "long_form" / "script_30min.txt").write_text("hello world", encoding="utf-8")
        (root / "secret.txt").write_text("top secret", encoding="utf-8")
        self.secret = root / "secret.txt"
        self.active = mock.patch.object(config_manager, "get_active_project", return_value=str(root))
        self.active.start()
        # No `with` block: the app's startup (OAuth bridge, scheduler) does not run
        self.client = TestClient(app_module.app)

    def tearDown(self):
        self.active.stop()
        self.tmp.cleanup()

    def script(self, **params):
        return self.client.get("/api/generator/script", params={"type": "long_form", **params})

    def test_reads_the_week_script(self):
        resp = self.script(week="1")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["content"], "hello world")

    def test_rejects_filename_traversal(self):
        for filename in ("../secret.txt", "..\\secret.txt", "../../secret.txt", str(self.secret), ".."):
            with self.subTest(filename=filename):
                self.assertEqual(self.script(week="1", filename=filename).status_code, 400)

    def test_rejects_week_traversal(self):
        for week in ("W01/..", "../W01", "W1/../../"):
            with self.subTest(week=week):
                self.assertEqual(self.script(week=week).status_code, 400)

    def test_format_endpoint_rejects_paths_outside_the_project(self):
        resp = self.client.get("/api/social/format", params={"rel_path": "../secret.txt"})
        self.assertEqual(resp.status_code, 404)


class FormatConnectionTests(unittest.TestCase):
    def test_unconnected_accounts_are_not_selectable(self):
        with tempfile.TemporaryDirectory() as tmp:
            reel = Path(tmp) / "W01" / "reels" / "01" / "final_reel.mp4"
            reel.parent.mkdir(parents=True)
            reel.write_bytes(b"\0" * 16)
            connections = {"youtube": True, "facebook": False, "instagram": False, "threads": True, "tiktok": True, "x": False}
            media = {"duration": "45s", "duration_sec": 45, "resolution": "1080x1920"}
            cfg = {p: {"enabled": True} for p in connections}
            with mock.patch.object(config_manager, "get_active_project", return_value=tmp), \
                    mock.patch.object(config_manager, "get_project_social_config", return_value=cfg), \
                    mock.patch.object(app_module.asset_manager, "get_media_info", return_value=media), \
                    mock.patch.object(app_module, "_platform_connections", return_value=connections):
                data = TestClient(app_module.app).get(
                    "/api/social/format", params={"rel_path": "W01/reels/01/final_reel.mp4"}
                ).json()
        eligible = {p for p, r in data["platforms"].items() if r["eligible"]}
        self.assertEqual(eligible, {"youtube", "threads", "tiktok"})
        self.assertIn("isn't connected", data["platforms"]["facebook"]["reason"])
        self.assertFalse(data["platforms"]["facebook"]["connected"])


if __name__ == "__main__":
    unittest.main()
