"""
Threads API Native Direct Uploader for Reels & Video Posts.
Communicates directly with Meta's Threads Graph API (https://graph.threads.net/v1.0/)
using OAuth 2.0 authorization with Instagram login.
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import requests
from core.config import config_manager

THREADS_API_BASE = "https://graph.threads.net"
DEFAULT_THREADS_APP_ID = "1067654339604613"  # KCT Video Publisher Meta App ID

class ThreadsUploader:
    def __init__(self, token_file: Optional[Path] = None):
        self.root_dir = Path(__file__).resolve().parent.parent
        self.token_file = token_file or (self.root_dir / "data" / "threads_token.json")
        self.app_id = DEFAULT_THREADS_APP_ID
        self.app_secret = ""
        self.access_token = ""
        self.threads_user_id = ""
        self.username = ""
        self.name = ""
        self.profile_picture_url = ""
        self.public_base_url = ""
        self.expires_at = 0
        self.load_token()

    def load_token(self) -> bool:
        """Loads saved Threads credentials and tokens from data/threads_token.json."""
        if not self.token_file.exists():
            return False
        try:
            with open(self.token_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.app_id = data.get("app_id") or self.app_id or DEFAULT_THREADS_APP_ID
            self.app_secret = data.get("app_secret", "")
            self.access_token = data.get("access_token", "")
            self.threads_user_id = data.get("threads_user_id", "")
            self.username = data.get("username", "")
            self.name = data.get("name", "")
            self.profile_picture_url = data.get("profile_picture_url", "")
            self.public_base_url = data.get("public_base_url", "")
            self.expires_at = data.get("expires_at", 0)
            return bool(self.access_token)
        except Exception as e:
            logging.error(f"[ThreadsUploader] Error loading token file: {e}")
            return False

    def save_token_data(self, data: Dict[str, Any]):
        """Persists Threads credentials to disk."""
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        current = {}
        if self.token_file.exists():
            try:
                with open(self.token_file, "r", encoding="utf-8") as f:
                    current = json.load(f)
            except Exception:
                current = {}

        current.update(data)
        with open(self.token_file, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2)

        # Update local instance
        self.load_token()

    def is_authenticated(self) -> bool:
        """Checks if a valid access token is present."""
        return bool(self.access_token)

    def get_status(self) -> Dict[str, Any]:
        """Validates token against Threads API and returns profile status."""
        if not self.access_token:
            return {
                "configured": False,
                "authenticated": False,
                "app_id": self.app_id,
                "public_base_url": self.public_base_url
            }

        try:
            url = f"{THREADS_API_BASE}/v1.0/me"
            params = {
                "fields": "id,username,name,threads_profile_picture_url,threads_biography",
                "access_token": self.access_token
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()

            if "id" in data:
                self.threads_user_id = data["id"]
                self.username = data.get("username", self.username)
                self.name = data.get("name", self.name)
                self.profile_picture_url = data.get("threads_profile_picture_url", self.profile_picture_url)
                return {
                    "configured": True,
                    "authenticated": True,
                    "user_id": self.threads_user_id,
                    "username": self.username,
                    "name": self.name,
                    "profile_picture_url": self.profile_picture_url,
                    "public_base_url": self.public_base_url,
                    "app_id": self.app_id
                }
            else:
                err_msg = data.get("error", {}).get("message", "Invalid Threads access token")
                return {
                    "configured": True,
                    "authenticated": False,
                    "error": err_msg,
                    "app_id": self.app_id,
                    "public_base_url": self.public_base_url
                }
        except Exception as e:
            return {
                "configured": True,
                "authenticated": False,
                "error": str(e),
                "app_id": self.app_id,
                "public_base_url": self.public_base_url
            }

    def generate_auth_url(self, redirect_uri: Optional[str] = None, app_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates the Threads OAuth 2.0 authorization URL.
        Prompts user to 'Log In with Instagram' to link their Threads account.
        """
        aid = app_id or self.app_id or DEFAULT_THREADS_APP_ID
        r_uri = redirect_uri or config_manager.get_oauth_redirect_uri()
        
        scopes = "threads_basic,threads_content_publish,threads_manage_replies"
        auth_url = (
            f"https://threads.net/oauth/authorize"
            f"?client_id={aid}"
            f"&redirect_uri={requests.utils.quote(r_uri)}"
            f"&scope={scopes}"
            f"&response_type=code"
        )
        return {
            "success": True,
            "auth_url": auth_url,
            "client_id": aid,
            "redirect_uri": r_uri
        }

    def exchange_code(
        self,
        code: str,
        redirect_uri: Optional[str] = None,
        app_id: Optional[str] = None,
        app_secret: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Exchanges the authorization code for a short-lived user access token,
        then automatically upgrades it to a 60-day long-lived token.
        """
        aid = app_id or self.app_id or DEFAULT_THREADS_APP_ID
        secret = app_secret or self.app_secret
        r_uri = redirect_uri or config_manager.get_oauth_redirect_uri()

        # Clean code if full redirect URL was pasted
        clean_code = code.strip()
        if "code=" in clean_code:
            match = re.search(r"code=([^&#]+)", clean_code)
            if match:
                clean_code = match.group(1)

        # Remove trailing '#_' often appended by Meta redirect
        if clean_code.endswith("#_"):
            clean_code = clean_code[:-2]

        try:
            # Step 1: Exchange code for short-lived token
            token_url = f"{THREADS_API_BASE}/oauth/access_token"
            payload = {
                "client_id": aid,
                "client_secret": secret,
                "grant_type": "authorization_code",
                "redirect_uri": r_uri,
                "code": clean_code
            }
            resp = requests.post(token_url, data=payload, timeout=20)
            token_data = resp.json()

            if "access_token" not in token_data:
                err_msg = token_data.get("error_message") or token_data.get("error", {}).get("message") or "Token exchange failed"
                return {"success": False, "error": err_msg, "details": token_data}

            short_token = token_data["access_token"]
            user_id = str(token_data.get("user_id", ""))
            long_token = short_token
            expires_at = time.time() + 3600

            # Step 2: Upgrade to 60-day long-lived token if app_secret is available
            if secret:
                try:
                    ll_url = f"{THREADS_API_BASE}/access_token"
                    ll_params = {
                        "grant_type": "th_exchange_token",
                        "client_secret": secret,
                        "access_token": short_token
                    }
                    ll_resp = requests.get(ll_url, params=ll_params, timeout=15)
                    ll_data = ll_resp.json()
                    if "access_token" in ll_data:
                        long_token = ll_data["access_token"]
                        expires_in = ll_data.get("expires_in", 5184000)
                        expires_at = time.time() + int(expires_in)
                        logging.info("[ThreadsUploader] Exchanged for 60-day long-lived Threads token.")
                except Exception as e:
                    logging.warning(f"[ThreadsUploader] Long-lived token exchange notice: {e}")

            # Step 3: Fetch profile information
            prof_url = f"{THREADS_API_BASE}/v1.0/me"
            prof_params = {
                "fields": "id,username,name,threads_profile_picture_url",
                "access_token": long_token
            }
            p_resp = requests.get(prof_url, params=prof_params, timeout=10)
            prof_data = p_resp.json()

            save_dict = {
                "app_id": aid,
                "app_secret": secret,
                "access_token": long_token,
                "threads_user_id": prof_data.get("id", user_id),
                "username": prof_data.get("username", ""),
                "name": prof_data.get("name", ""),
                "profile_picture_url": prof_data.get("threads_profile_picture_url", ""),
                "expires_at": expires_at,
                "saved_at": time.time()
            }
            self.save_token_data(save_dict)

            logging.info(f"[ThreadsUploader] Connected Threads account: @{save_dict['username']} ({save_dict['threads_user_id']})")
            return {
                "success": True,
                "user_id": save_dict["threads_user_id"],
                "username": save_dict["username"],
                "name": save_dict["name"],
                "profile_picture_url": save_dict["profile_picture_url"],
                "message": f"Successfully connected Threads account: @{save_dict['username']}"
            }
        except Exception as e:
            logging.error(f"[ThreadsUploader] OAuth exception: {e}")
            return {"success": False, "error": str(e)}

    def save_token_direct(
        self,
        token: str,
        threads_user_id: Optional[str] = None,
        username: Optional[str] = None,
        app_secret: Optional[str] = None,
        public_base_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """Allows direct saving of a Threads Access Token (e.g. from Meta Developer Dashboard)."""
        clean_token = token.strip()
        if not clean_token:
            return {"success": False, "error": "Token string cannot be empty"}

        try:
            url = f"{THREADS_API_BASE}/v1.0/me"
            params = {
                "fields": "id,username,name,threads_profile_picture_url",
                "access_token": clean_token
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()

            if "id" in data:
                u_id = data["id"]
                u_name = data.get("username", username or "")
                d_name = data.get("name", "")
                p_pic = data.get("threads_profile_picture_url", "")
                save_dict = {
                    "access_token": clean_token,
                    "threads_user_id": u_id,
                    "username": u_name,
                    "name": d_name,
                    "profile_picture_url": p_pic,
                    "saved_at": time.time()
                }
                if app_secret:
                    save_dict["app_secret"] = app_secret.strip()
                if public_base_url:
                    save_dict["public_base_url"] = public_base_url.strip().rstrip("/")
                self.save_token_data(save_dict)
                return {
                    "success": True,
                    "user_id": u_id,
                    "username": u_name,
                    "name": d_name,
                    "profile_picture_url": p_pic,
                    "message": f"Saved Threads token for @{u_name}"
                }
            else:
                err_msg = data.get("error", {}).get("message", "Token validation failed")
                return {"success": False, "error": err_msg, "details": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def post_reply(self, post_id: str, text: str) -> Dict[str, Any]:
        """Replies to a Threads post (text container with reply_to_id, then publish). Needs threads_manage_replies."""
        try:
            base = f"{THREADS_API_BASE}/v1.0/{self.threads_user_id}"
            container = requests.post(f"{base}/threads", data={
                "media_type": "TEXT",
                "text": text.strip()[:500],
                "reply_to_id": post_id,
                "access_token": self.access_token
            }, timeout=30).json()
            if "id" not in container:
                return {"success": False, "error": container.get("error", {}).get("message", "Reply container rejected")}
            time.sleep(2)
            published = requests.post(f"{base}/threads_publish", data={
                "creation_id": container["id"],
                "access_token": self.access_token
            }, timeout=30).json()
            if "id" in published:
                logging.info(f"[ThreadsUploader] Reply posted under {post_id}: {published['id']}")
                return {"success": True, "id": published["id"]}
            return {"success": False, "error": published.get("error", {}).get("message", "Reply publish rejected")}
        except Exception as e:
            logging.warning(f"[ThreadsUploader] Could not reply to {post_id}: {e}")
            return {"success": False, "error": str(e)}

    def upload_threads_video(
        self,
        video_path: Path,
        caption: str,
        tags: Optional[List[str]] = None,
        public_video_url: Optional[str] = None,
        pinned_comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publishes a Video / Reel to Threads via the official 2-step Container API:
        1. POST /{threads_user_id}/threads with media_type=VIDEO, video_url=<public_url>, text=<caption/tags>
        2. Poll container status until FINISHED
        3. POST /{threads_user_id}/threads_publish with creation_id
        """
        if not self.is_authenticated():
            return {
                "status": "failed",
                "platform": "Threads",
                "error": "Threads is not authenticated. Please connect via Threads OAuth (Log In with Instagram)."
            }

        if not video_path.exists():
            return {"status": "failed", "platform": "Threads", "error": f"Video file not found: {video_path}"}

        # Resolve public video URL
        final_video_url = public_video_url
        if not final_video_url and self.public_base_url:
            # Construct URL from media streaming endpoint
            try:
                rel = video_path.relative_to(self.root_dir).as_posix()
            except ValueError:
                rel = video_path.name
            base = self.public_base_url.rstrip("/")
            final_video_url = f"{base}/api/media/{rel}"

        if not final_video_url:
            return {
                "status": "failed",
                "platform": "Threads",
                "error": (
                    "Threads API requires a publicly reachable 'video_url' so Meta's servers can retrieve the video. "
                    "Please configure 'Public Base URL' (e.g. Cloudflare tunnel, ngrok, or domain) in Threads Settings."
                )
        }

        # Check duration (Threads limit is 5 minutes / 300s)
        try:
            from core.asset_manager import asset_manager
            minfo = asset_manager.get_media_info(video_path)
            dur_sec = minfo.get("duration_sec", 0.0)
            if dur_sec > 300:
                dur_m = int(dur_sec // 60)
                dur_s = int(dur_sec % 60)
                return {
                    "status": "failed",
                    "platform": "Threads",
                    "error": f"Video duration ({dur_m}m {dur_s}s) exceeds Threads limit of 5 minutes (300 seconds)."
                }
        except Exception:
            pass

        # Caption arrives complete (house format incl. its tag); Threads limit is 500 characters
        full_text = caption.strip()
        if len(full_text) > 500:
            full_text = full_text[:497] + "..."

        logging.info(f"[ThreadsUploader] Creating video container for @{self.username} via {final_video_url}...")

        # Step 1: Create Media Container
        container_url = f"{THREADS_API_BASE}/v1.0/{self.threads_user_id}/threads"
        container_params = {
            "media_type": "VIDEO",
            "video_url": final_video_url,
            "text": full_text,
            "access_token": self.access_token
        }

        try:
            c_resp = requests.post(container_url, data=container_params, timeout=30).json()
            if "id" not in c_resp:
                err_msg = c_resp.get("error", {}).get("message", "Failed to create Threads video container")
                return {"status": "failed", "platform": "Threads", "error": err_msg, "details": c_resp}

            container_id = c_resp["id"]
            logging.info(f"[ThreadsUploader] Container created: {container_id}. Polling processing status...")

            # Step 2: Poll Container Status
            status_url = f"{THREADS_API_BASE}/v1.0/{container_id}"
            status_params = {"fields": "status,error_message", "access_token": self.access_token}

            max_polls = 45
            poll_interval = 4
            current_status = "IN_PROGRESS"

            for poll_idx in range(max_polls):
                time.sleep(poll_interval)
                s_resp = requests.get(status_url, params=status_params, timeout=15).json()
                current_status = s_resp.get("status", "UNKNOWN")
                logging.info(f"[ThreadsUploader] Container {container_id} poll {poll_idx+1}/{max_polls}: {current_status}")

                if current_status == "FINISHED":
                    break
                elif current_status in ("ERROR", "EXPIRED"):
                    err_detail = s_resp.get("error_message", "Processing failed on Threads servers")
                    return {
                        "status": "failed",
                        "platform": "Threads",
                        "error": f"Threads video processing failed: {err_detail}",
                        "details": s_resp
                    }

            if current_status != "FINISHED":
                return {
                    "status": "failed",
                    "platform": "Threads",
                    "error": f"Threads video processing timed out after {max_polls * poll_interval}s. Status: {current_status}"
                }

            # Step 3: Publish Container
            pub_url = f"{THREADS_API_BASE}/v1.0/{self.threads_user_id}/threads_publish"
            pub_params = {
                "creation_id": container_id,
                "access_token": self.access_token
            }
            pub_resp = requests.post(pub_url, data=pub_params, timeout=30).json()

            if "id" in pub_resp:
                post_id = pub_resp["id"]
                # Step 4: Get permalink
                try:
                    info_url = f"{THREADS_API_BASE}/v1.0/{post_id}"
                    info_resp = requests.get(
                        info_url,
                        params={"fields": "permalink", "access_token": self.access_token},
                        timeout=10
                    ).json()
                    threads_url = info_resp.get("permalink") or f"https://www.threads.com/@{self.username}/post/{post_id}"
                except Exception:
                    threads_url = f"https://www.threads.com/@{self.username}/post/{post_id}"

                logging.info(f"[ThreadsUploader] Video Reel published successfully to Threads: {threads_url}")
                result = {
                    "status": "published",
                    "platform": "Threads",
                    "id": post_id,
                    "url": threads_url,
                    "message": f"Published video to @{self.username} on Threads: {threads_url}"
                }
                # Links comment right after posting, as a reply to the new post
                if pinned_comment and pinned_comment.strip():
                    reply = self.post_reply(post_id, pinned_comment)
                    result["comment_posted"] = reply["success"]
                    result["comment_id" if reply["success"] else "comment_error"] = reply.get("id") or reply.get("error")
                return result
            else:
                err_msg = pub_resp.get("error", {}).get("message", "Failed to publish Threads container")
                return {"status": "failed", "platform": "Threads", "error": err_msg, "details": pub_resp}

        except Exception as e:
            logging.error(f"[ThreadsUploader] Exception during Threads publish: {e}")
            return {"status": "failed", "platform": "Threads", "error": str(e)}

threads_uploader = ThreadsUploader()
