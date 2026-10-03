"""
TikTok Native Direct Uploader using Session Cookie / Web Automation.
Supports direct `sessionid` token or exported Netscape/JSON cookie files.
Uses Playwright and tiktok-uploader for headless background publishing.
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger("tiktok_uploader")

class TikTokUploader:
    def __init__(self, data_dir: Optional[Path] = None):
        self.root_dir = Path(__file__).resolve().parent.parent
        self.data_dir = data_dir or (self.root_dir / "data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.session_file = self.data_dir / "tiktok_session.json"
        self.cookies_file = self.data_dir / "tiktok_cookies.txt"
        
        self.sessionid = ""
        self.username = ""
        self.account_name = ""
        self.load_session()

    def load_session(self) -> bool:
        """Loads saved sessionid or cookies from data/tiktok_session.json."""
        if self.session_file.exists():
            try:
                with open(self.session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.sessionid = data.get("sessionid", "").strip()
                self.username = data.get("username", "").strip()
                self.account_name = data.get("account_name", "").strip()
                if self.sessionid:
                    return True
            except Exception as e:
                logger.error(f"[TikTokUploader] Error loading session file: {e}")

        # Fallback check for cookies.txt
        if self.cookies_file.exists() and self.cookies_file.stat().st_size > 0:
            return True

        return False

    def save_session(self, sessionid: str, username: str = "", account_name: str = "") -> Dict[str, Any]:
        """Saves TikTok sessionid or cookies."""
        clean_sid = sessionid.strip()
        self.sessionid = clean_sid
        if username:
            self.username = username.strip()
        if account_name:
            self.account_name = account_name.strip()

        data = {
            "sessionid": self.sessionid,
            "username": self.username,
            "account_name": self.account_name,
            "updated_at": int(time.time())
        }

        with open(self.session_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return {"success": True, "authenticated": bool(self.sessionid)}

    def is_authenticated(self) -> bool:
        """Checks if sessionid or cookies file is present."""
        if not self.sessionid:
            self.load_session()
        return bool(self.sessionid or (self.cookies_file.exists() and self.cookies_file.stat().st_size > 0))

    def get_status(self) -> Dict[str, Any]:
        """Returns the current TikTok configuration and authentication status."""
        self.load_session()
        has_auth = self.is_authenticated()
        return {
            "platform": "TikTok",
            "authenticated": has_auth,
            "username": self.username or "biblestories832",
            "account_name": self.account_name or "BibleStories",
            "has_sessionid": bool(self.sessionid),
            "has_cookies_file": self.cookies_file.exists(),
            "method": "browser_session"
        }

    def upload_video(
        self,
        video_path: Path | str,
        caption: str,
        tags: Optional[List[str]] = None,
        visibility: str = "everyone",
        headless: bool = True
    ) -> Dict[str, Any]:
        """
        Uploads an MP4 video directly to TikTok using the authenticated session.
        """
        v_path = Path(video_path).resolve()
        if not v_path.exists() or not v_path.is_file():
            return {
                "success": False,
                "status": "failed",
                "error": f"Video file not found: {video_path}"
            }

        if not self.is_authenticated():
            return {
                "success": False,
                "status": "failed",
                "error": "TikTok is not authenticated. Please provide your sessionid or cookies file in Studio Settings."
            }

        try:
            from tiktok_uploader.upload import upload_video as tt_upload

            # Clean and sanitize caption
            final_caption = (caption or "").strip()

            logger.info(f"[TikTokUploader] Starting upload for '{v_path.name}' to TikTok...")
            
            # Run upload
            upload_kwargs = {
                "filename": str(v_path),
                "description": final_caption,
                "visibility": visibility if visibility in ["everyone", "friends", "only_you"] else "everyone",
                "headless": headless
            }

            if self.sessionid:
                upload_kwargs["sessionid"] = self.sessionid
            elif self.cookies_file.exists():
                upload_kwargs["cookies"] = str(self.cookies_file)

            failed_videos = tt_upload(**upload_kwargs)

            if not failed_videos:
                logger.info(f"[TikTokUploader] Successfully uploaded '{v_path.name}' to TikTok!")
                return {
                    "success": True,
                    "status": "published",
                    "platform": "TikTok",
                    "video": v_path.name,
                    "caption": final_caption,
                    "message": f"Successfully published video '{v_path.name}' to TikTok!"
                }
            else:
                err_msg = f"TikTok upload failed for video: {failed_videos}"
                logger.error(f"[TikTokUploader] {err_msg}")
                return {
                    "success": False,
                    "status": "failed",
                    "platform": "TikTok",
                    "error": err_msg
                }

        except Exception as e:
            err = str(e)
            logger.error(f"[TikTokUploader] Exception during upload: {err}")
            return {
                "success": False,
                "status": "failed",
                "platform": "TikTok",
                "error": err
            }

tiktok_uploader = TikTokUploader()
