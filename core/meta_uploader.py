"""
Meta Graph API Native Direct Uploader for Facebook Pages & Instagram Reels.
Directly communicates with Meta Graph API v20.0 without any intermediate middleware.
"""

import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
import requests

BHSR_PAGE_ID = "1095048317029830"
BHSR_IG_ID = "17841429371050878"
META_TOKEN_FILE = Path(__file__).resolve().parent.parent / "data" / "meta_token.json"
# Meta's upload server fails any single request that runs past ~40s, so videos go up in pieces this size
UPLOAD_CHUNK = 4 * 1024 * 1024
# Above this video bitrate, Instagram uploads are re-encoded to ~5 Mbps first (Instagram recompresses Reels anyway)
IG_MAX_UPLOAD_BITRATE = 8_000_000


def load_meta_credentials() -> Dict[str, str]:
    """Loads Meta credentials from env vars (META_PAGE_TOKEN, META_PAGE_ID, META_IG_USER_ID)
    or data/meta_token.json ({"page_token": ..., "page_id": ..., "ig_user_id": ...}). Never hardcode tokens."""
    creds: Dict[str, str] = {}
    if META_TOKEN_FILE.exists():
        try:
            with open(META_TOKEN_FILE, "r", encoding="utf-8") as f:
                creds = {k: str(v).strip() for k, v in json.load(f).items() if v}
        except Exception as e:
            logging.error(f"[MetaUploader] Error loading {META_TOKEN_FILE.name}: {e}")
    for env_key, key in (("META_PAGE_TOKEN", "page_token"), ("META_PAGE_ID", "page_id"), ("META_IG_USER_ID", "ig_user_id")):
        if os.environ.get(env_key):
            creds[key] = os.environ[env_key].strip()
    return creds


class MetaUploader:
    def __init__(self, page_id: Optional[str] = None, page_token: Optional[str] = None, ig_user_id: Optional[str] = None):
        creds = load_meta_credentials()
        self.page_id = page_id or creds.get("page_id") or BHSR_PAGE_ID
        self.page_token = page_token or creds.get("page_token", "")
        self.ig_user_id = ig_user_id or creds.get("ig_user_id") or BHSR_IG_ID
        self.api_version = "v20.0"
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        self._ensure_page_token()

    def _ensure_page_token(self):
        """If the configured token is a System User token, query /me/accounts to get the real Page Access Token."""
        if not self.page_token:
            return
        try:
            url = f"{self.base_url}/me/accounts"
            resp = requests.get(url, params={"access_token": self.page_token}, timeout=5)
            data = resp.json()
            for acc in data.get("data", []):
                if acc.get("id") == self.page_id and acc.get("access_token"):
                    self.page_token = acc["access_token"]
                    logging.info(f"[MetaUploader] Acquired dynamic Page Token for {self.page_id}.")
                    break
        except Exception as e:
            logging.debug(f"[MetaUploader] Page token check: {e}")

    # Permissions Facebook Page video/Reel posting and Instagram publishing need
    REQUIRED_SCOPES = ("pages_manage_posts", "pages_read_engagement", "instagram_content_publish")

    def missing_permissions(self) -> List[str]:
        """Best-effort permission check via debug_token; returns [] when it can't be determined."""
        try:
            data = requests.get(
                f"{self.base_url}/debug_token",
                params={"input_token": self.page_token, "access_token": self.page_token},
                timeout=10
            ).json().get("data", {})
            scopes = set(data.get("scopes") or [])
            return [s for s in self.REQUIRED_SCOPES if s not in scopes] if scopes else []
        except Exception:
            return []

    def save_credentials(self, page_token: str, page_id: Optional[str] = None, ig_user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Validates a Page (or System User) access token against the Graph API and stores it in
        data/meta_token.json (gitignored). The running app uses it immediately, no restart needed.
        """
        previous = (self.page_id, self.page_token, self.ig_user_id)
        self.page_token = (page_token or "").strip()
        self.page_id = (page_id or "").strip() or self.page_id
        self.ig_user_id = (ig_user_id or "").strip() or self.ig_user_id
        if not self.page_token:
            self.page_id, self.page_token, self.ig_user_id = previous
            return {"success": False, "error": "Paste a Page access token."}

        self._ensure_page_token()
        status = self.get_status()
        if not status.get("configured"):
            self.page_id, self.page_token, self.ig_user_id = previous
            return {"success": False, "error": status.get("error") or "Meta rejected this token."}

        if status["instagram"].get("active"):
            self.ig_user_id = status["instagram"]["ig_id"]
        META_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(META_TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump({"page_token": self.page_token, "page_id": self.page_id, "ig_user_id": self.ig_user_id}, f, indent=2)
        logging.info(f"[MetaUploader] Saved Meta credentials for Page {self.page_id}.")

        result = {"success": True, "status": status}
        missing = self.missing_permissions()
        if missing:
            result["warning"] = (
                f"Connected, but the token is missing: {', '.join(missing)}. "
                "Uploads will fail with 'No permission to publish' until you generate a token with those permissions."
            )
        if not status["instagram"].get("active"):
            result["warning"] = (result.get("warning", "") + " No Instagram Business account is linked to this Page.").strip()
        return result

    def get_status(self) -> Dict[str, Any]:
        """Validates token and returns Page & Instagram info."""
        if not self.page_token:
            return {"configured": False, "error": "No page token configured"}
        
        try:
            url = f"{self.base_url}/{self.page_id}"
            params = {
                "fields": "id,name,fan_count,instagram_business_account{id,username,name}",
                "access_token": self.page_token
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            if "error" in data:
                return {
                    "configured": False,
                    "error": data["error"].get("message", "Invalid Meta token")
                }
            
            ig_acc = data.get("instagram_business_account", {})
            return {
                "configured": True,
                "facebook": {
                    "page_id": data.get("id"),
                    "page_name": data.get("name"),
                    "fan_count": data.get("fan_count", 0),
                    "active": True
                },
                "instagram": {
                    "ig_id": ig_acc.get("id", self.ig_user_id),
                    "username": ig_acc.get("username", "biblesecretsrevealed2318"),
                    "name": ig_acc.get("name", "Bible Secrets Revealed"),
                    "active": bool(ig_acc.get("id"))
                }
            }
        except Exception as e:
            return {"configured": False, "error": str(e)}

    def post_comment(self, object_id: str, text: str) -> Dict[str, Any]:
        """Comments as the Page on a Facebook video/reel or an Instagram media item."""
        try:
            resp = requests.post(
                f"{self.base_url}/{object_id}/comments",
                data={"message": text.strip(), "access_token": self.page_token},
                timeout=20
            ).json()
            if "id" in resp:
                logging.info(f"[MetaUploader] Comment posted on {object_id}: {resp['id']}")
                return {"success": True, "id": resp["id"]}
            logging.warning(f"[MetaUploader] Could not comment on {object_id}: {resp}")
            return {"success": False, "error": resp.get("error", {}).get("message", "Comment rejected")}
        except Exception as e:
            logging.warning(f"[MetaUploader] Comment error on {object_id}: {e}")
            return {"success": False, "error": str(e)}

    def _first_comment(self, object_id: str, text: Optional[str], scheduled_timestamp: Optional[int]) -> Optional[Dict[str, Any]]:
        """Posts the links comment now, or reports it as queued when the post is scheduled (not live yet)."""
        if not text or not text.strip():
            return None
        if scheduled_timestamp:
            return {"status": "queued", "post_after": scheduled_timestamp}
        time.sleep(2)
        res = self.post_comment(object_id, text)
        return {"status": "posted", "comment_id": res["id"]} if res["success"] else {"status": "failed", "error": res["error"]}

    @staticmethod
    def _pending_comment_fields(text: Optional[str], scheduled_timestamp: Optional[int]) -> Dict[str, Any]:
        """For scheduled posts: the comment the scheduler posts once the post is live (SocialDispatcher.post_due_comments)."""
        if not scheduled_timestamp or not text or not text.strip():
            return {}
        return {"pending_comment": text.strip(), "comment_due_at": int(scheduled_timestamp) + 60}

    def upload_facebook_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        scheduled_timestamp: Optional[int] = None,
        pinned_comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uploads a video directly to the Facebook Page using Graph API.
        Supports both immediate publishing and native cloud scheduling.
        Automatically posts Strategy B first comment (merch & store links) if provided.
        """
        if not video_path.exists():
            return {"status": "failed", "platform": "Facebook", "error": f"File not found: {video_path}"}

        file_size = video_path.stat().st_size
        logging.info(f"[MetaUploader] Uploading to Facebook Page {self.page_id}: '{title}' ({round(file_size/(1024*1024), 1)} MB)")

        upload_url = f"https://graph-video.facebook.com/{self.api_version}/{self.page_id}/videos"

        # The caption arrives complete (house format incl. its hashtag line)
        full_desc = description.strip()

        # Build payload
        data = {
            "title": title,
            "description": full_desc,
            "access_token": self.page_token
        }

        if scheduled_timestamp:
            data["published"] = "false"
            data["scheduled_publish_time"] = str(scheduled_timestamp)
        else:
            data["published"] = "true"

        # Direct multipart upload for reliable single-step transfer
        try:
            with open(video_path, "rb") as f:
                files = {"source": (video_path.name, f, "video/mp4")}
                resp = requests.post(upload_url, data=data, files=files, timeout=max(600, int(file_size / (50 * 1024))))
                
            try:
                res_json = resp.json()
            except Exception:
                res_json = {"error": {"message": f"HTTP {resp.status_code}: {resp.text[:300]}"}}

            if "id" in res_json:
                fb_id = res_json["id"]
                watch_url = f"https://www.facebook.com/watch/?v={fb_id}"
                msg = f"{'Scheduled on' if scheduled_timestamp else 'Published to'} Facebook Page: {watch_url}"
                logging.info(f"[MetaUploader] Facebook upload successful: {fb_id}")

                first_comment_info = self._first_comment(fb_id, pinned_comment, scheduled_timestamp)

                return {
                    "status": "published",
                    "platform": "Facebook",
                    "id": fb_id,
                    "url": watch_url,
                    "scheduled": bool(scheduled_timestamp),
                    "scheduled_timestamp": scheduled_timestamp,
                    "first_comment": first_comment_info,
                    **self._pending_comment_fields(pinned_comment, scheduled_timestamp),
                    "message": msg
                }
            else:
                err_msg = res_json.get("error", {}).get("message", "Unknown Graph API error")
                logging.error(f"[MetaUploader] Facebook upload failed: {res_json}")
                return {
                    "status": "failed",
                    "platform": "Facebook",
                    "error": err_msg,
                    "details": res_json
                }
        except Exception as e:
            logging.error(f"[MetaUploader] Facebook upload exception: {e}")
            return {
                "status": "failed",
                "platform": "Facebook",
                "error": str(e)
            }

    def upload_facebook_reel(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        scheduled_timestamp: Optional[int] = None,
        pinned_comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Uploads a short vertical video (Reel) directly to the Facebook Page Reels feed
        using the Meta Reels Publishing API (/{page_id}/video_reels).
        Supports native scheduling and Strategy B automatic first comments.
        Gracefully falls back to upload_facebook_video if Reels endpoint is unavailable.
        """
        if not video_path.exists():
            return {"status": "failed", "platform": "Facebook Reels", "error": f"File not found: {video_path}"}

        file_size = video_path.stat().st_size
        logging.info(f"[MetaUploader] Uploading Reel to Facebook Page {self.page_id}: '{title}' ({round(file_size/(1024*1024), 1)} MB)")

        # The caption arrives complete (house format incl. its hashtag line)
        full_desc = description.strip()

        # Step 1: Initialize Facebook Reel upload session
        reels_init_url = f"{self.base_url}/{self.page_id}/video_reels"
        init_payload = {
            "upload_phase": "start",
            "access_token": self.page_token
        }

        # Only the start phase may fall back to /videos: nothing has been uploaded yet.
        # Once bytes are sent, a fallback could publish the same video twice.
        try:
            init_resp = requests.post(reels_init_url, data=init_payload, timeout=20)
            init_data = init_resp.json()
        except Exception as e:
            logging.warning(f"[MetaUploader] Facebook video_reels start exception ({e}). Falling back to upload_facebook_video.")
            return self.upload_facebook_video(video_path, title, description, tags, scheduled_timestamp, pinned_comment)

        video_id = init_data.get("video_id")
        upload_url = init_data.get("upload_url")
        if not video_id:
            logging.warning(f"[MetaUploader] Facebook video_reels start failed ({init_data}). Falling back to upload_facebook_video.")
            return self.upload_facebook_video(video_path, title, description, tags, scheduled_timestamp, pinned_comment)

        try:
            # Step 2: Binary Video Upload to rupload endpoint
            if not upload_url:
                upload_url = f"https://rupload.facebook.com/video-upload/{self.api_version}/{video_id}"

            headers = {
                "Authorization": f"OAuth {self.page_token}",
                "offset": "0",
                "file_size": str(file_size)
            }

            with open(video_path, "rb") as f:
                up_resp = requests.post(upload_url, headers=headers, data=f, timeout=max(600, int(file_size / (50 * 1024))))

            if up_resp.status_code != 200:
                return {
                    "status": "failed",
                    "platform": "Facebook Reels",
                    "id": video_id,
                    "error": f"Reel binary upload failed with HTTP {up_resp.status_code}: {up_resp.text[:300]}"
                }

            # Step 3: Finish & Publish Reel
            finish_payload = {
                "upload_phase": "finish",
                "video_id": video_id,
                "video_state": "SCHEDULED" if scheduled_timestamp else "PUBLISHED",
                "description": full_desc,
                "access_token": self.page_token
            }
            if scheduled_timestamp:
                finish_payload["scheduled_publish_time"] = str(scheduled_timestamp)

            fin_resp = requests.post(reels_init_url, data=finish_payload, timeout=30)
            fin_data = fin_resp.json()

            if "error" not in fin_data and (fin_data.get("success") or "id" in fin_data):
                reel_url = f"https://www.facebook.com/reel/{video_id}"
                msg = f"{'Scheduled Reel on' if scheduled_timestamp else 'Published Reel to'} Facebook Page: {reel_url}"
                logging.info(f"[MetaUploader] Facebook Reel published successfully: {video_id}")

                first_comment_info = self._first_comment(video_id, pinned_comment, scheduled_timestamp)

                return {
                    "status": "published",
                    "platform": "Facebook Reels",
                    "id": video_id,
                    "url": reel_url,
                    "is_reel": True,
                    "scheduled": bool(scheduled_timestamp),
                    "scheduled_timestamp": scheduled_timestamp,
                    "first_comment": first_comment_info,
                    **self._pending_comment_fields(pinned_comment, scheduled_timestamp),
                    "message": msg
                }
            else:
                err_msg = fin_data.get("error", {}).get("message", "Failed to finish Facebook Reel upload")
                logging.error(f"[MetaUploader] Facebook Reel finish error for {video_id}: {fin_data}")
                return {
                    "status": "failed",
                    "platform": "Facebook Reels",
                    "id": video_id,
                    "error": f"{err_msg} (check the Page's Reels for video {video_id} before reposting)",
                    "details": fin_data
                }

        except Exception as e:
            # The reel may already be live (e.g. finish timed out after Meta accepted it): never re-upload here
            logging.error(f"[MetaUploader] Facebook Reel upload exception for {video_id}: {e}")
            return {
                "status": "failed",
                "platform": "Facebook Reels",
                "id": video_id,
                "error": f"{e} (check the Page's Reels for video {video_id} before reposting)"
            }

    def upload_facebook_story(self, video_path: Path) -> Dict[str, Any]:
        """
        Publishes a vertical video as a Facebook Page Story via /{page_id}/video_stories
        (start -> rupload binary -> finish). Stories have no caption, comments or scheduling.
        """
        if not video_path.exists():
            return {"status": "failed", "platform": "Facebook Story", "error": f"File not found: {video_path}"}

        file_size = video_path.stat().st_size
        stories_url = f"{self.base_url}/{self.page_id}/video_stories"
        video_id = None
        try:
            init_data = requests.post(stories_url, data={"upload_phase": "start", "access_token": self.page_token}, timeout=20).json()
            video_id = init_data.get("video_id")
            if not video_id:
                err = init_data.get("error", {}).get("message", "Could not start Facebook Story upload")
                return {"status": "failed", "platform": "Facebook Story", "error": err, "details": init_data}

            upload_url = init_data.get("upload_url") or f"https://rupload.facebook.com/video-upload/{self.api_version}/{video_id}"
            headers = {"Authorization": f"OAuth {self.page_token}", "offset": "0", "file_size": str(file_size)}
            with open(video_path, "rb") as f:
                up_resp = requests.post(upload_url, headers=headers, data=f, timeout=max(600, int(file_size / (50 * 1024))))
            if up_resp.status_code != 200:
                return {
                    "status": "failed",
                    "platform": "Facebook Story",
                    "id": video_id,
                    "error": f"Story binary upload failed with HTTP {up_resp.status_code}: {up_resp.text[:300]}"
                }

            fin_data = requests.post(
                stories_url,
                data={"upload_phase": "finish", "video_id": video_id, "access_token": self.page_token},
                timeout=30
            ).json()
            if "error" in fin_data or not fin_data.get("success"):
                err = fin_data.get("error", {}).get("message", "Failed to finish Facebook Story upload")
                return {"status": "failed", "platform": "Facebook Story", "id": video_id, "error": err, "details": fin_data}

            post_id = fin_data.get("post_id") or video_id
            story_url = f"https://www.facebook.com/{post_id}"
            logging.info(f"[MetaUploader] Facebook Story published: {post_id}")
            return {
                "status": "published",
                "platform": "Facebook Story",
                "id": post_id,
                "url": story_url,
                "is_story": True,
                "message": f"Published Story to Facebook Page: {story_url}"
            }
        except Exception as e:
            logging.error(f"[MetaUploader] Facebook Story upload exception for {video_id}: {e}")
            return {
                "status": "failed",
                "platform": "Facebook Story",
                "id": video_id,
                "error": f"{e} (check the Page's Stories before reposting)" if video_id else str(e)
            }

    def _resumable_upload(self, upload_uri: str, path: Path) -> Dict[str, Any]:
        """
        Sends a file to Meta's rupload endpoint in UPLOAD_CHUNK pieces using the `offset` header. Meta fails any single
        upload request that runs longer than ~40s ("ProcessingFailedError"), which a whole Reel does on a slow uplink.
        A 206 answer means the piece was stored; after an error the upload resumes from the offset the server reports.
        """
        size = path.stat().st_size
        auth = {"Authorization": f"OAuth {self.page_token}"}
        offset, failures, error = 0, 0, ""
        with open(path, "rb") as f:
            while offset < size:
                f.seek(offset)
                chunk = f.read(UPLOAD_CHUNK)
                try:
                    resp = requests.post(
                        upload_uri,
                        headers={**auth, "offset": str(offset), "file_size": str(size)},
                        data=chunk,
                        timeout=120
                    )
                    if resp.status_code == 200:
                        return {"success": True}
                    if resp.status_code == 206:
                        offset += len(chunk)
                        failures = 0
                        logging.info(f"[MetaUploader] Uploaded {round(offset / size * 100)}% of {path.name}")
                        continue
                    error = f"HTTP {resp.status_code}: {resp.text[:300]}"
                except requests.RequestException as e:
                    error = str(e)
                failures += 1
                logging.warning(f"[MetaUploader] Upload piece at offset {offset} failed ({error}), attempt {failures}")
                if failures > 3:
                    return {"success": False, "error": error}
                time.sleep(2 * failures)
                try:
                    offset = int(requests.get(upload_uri, headers=auth, timeout=30).json().get("offset", offset))
                except Exception:
                    pass
        return {"success": True}

    @staticmethod
    def prepare_compliant_instagram_video(video_path: Path) -> tuple[Path, bool]:
        """
        Inspects video and ensures it strictly satisfies Meta Instagram Reels container rules:
        - moov atom at beginning of file (+faststart)
        - no edit lists (-use_editlist 0)
        - stereo AAC audio 48kHz (-ac 2 -ar 48000)
        - video above 8 Mbps re-encoded to ~5 Mbps: Instagram recompresses Reels far lower anyway, and a lighter
          file uploads in less than half the time on a slow uplink
        Returns (target_path, is_temp).
        """
        import subprocess, json
        try:
            needs_remux = False
            needs_reencode = False
            with open(video_path, "rb") as f:
                header = f.read(1024)
                if b"moov" not in header:
                    needs_remux = True
                f.seek(0)
                data_sample = f.read(min(video_path.stat().st_size, 2 * 1024 * 1024))
                if b"elst" in data_sample:
                    needs_remux = True

            try:
                probe_cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", str(video_path)]
                probe_data = json.loads(subprocess.check_output(probe_cmd, timeout=10))
                streams = probe_data.get("streams", [])
                a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
                if a_stream and (int(a_stream.get("channels", 2)) != 2 or int(a_stream.get("sample_rate", 48000)) != 48000):
                    needs_remux = True
                v_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
                bitrate = int(v_stream.get("bit_rate") or probe_data.get("format", {}).get("bit_rate") or 0)
                needs_reencode = bitrate > IG_MAX_UPLOAD_BITRATE
            except Exception:
                pass

            if not needs_remux and not needs_reencode:
                return video_path, False

            temp_dir = video_path.parent / ".temp_meta"
            temp_dir.mkdir(parents=True, exist_ok=True)
            normalized_path = temp_dir / f"ig_{video_path.stem}.mp4"
            video_args = (
                ["-c:v", "libx264", "-preset", "veryfast", "-profile:v", "high", "-pix_fmt", "yuv420p",
                 "-b:v", "5M", "-maxrate", "6M", "-bufsize", "10M"]
                if needs_reencode else ["-c:v", "copy"]
            )
            cmd = [
                "ffmpeg", "-y", "-i", str(video_path),
                *video_args,
                "-c:a", "aac", "-b:a", "128k", "-ac", "2", "-ar", "48000",
                "-use_editlist", "0",
                "-movflags", "+faststart",
                str(normalized_path)
            ]
            res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if res.returncode == 0 and normalized_path.exists() and normalized_path.stat().st_size > 0:
                logging.info(f"[MetaUploader] Remuxed video to Instagram-compliant container: {normalized_path.name}")
                return normalized_path, True
        except Exception as e:
            logging.warning(f"[MetaUploader] Faststart/stereo normalization check failed: {e}")
        return video_path, False

    def upload_instagram_reel(
        self,
        video_path: Path,
        caption: str,
        tags: Optional[List[str]] = None,
        pinned_comment: Optional[str] = None,
        media_type: str = "REELS"
    ) -> Dict[str, Any]:
        """
        media_type="STORIES" publishes an Instagram Story instead (no caption or comment, max 60s).
        Uploads an Instagram Reel via the 3-Step Meta Graph API Resumable Container protocol:
        1. Initialize resumable container on Instagram Business Account
        2. Stream binary video data directly to rupload endpoint
        3. Poll container until status_code == FINISHED
        4. Publish container to Instagram Feed & Reels tab
        """
        if not video_path.exists():
            return {"status": "failed", "platform": "Instagram", "error": f"File not found: {video_path}"}
        is_story = media_type == "STORIES"

        # Check duration constraint (Instagram Graph API supports up to 15 minutes / 900s for Reels containers)
        try:
            from core.asset_manager import asset_manager
            minfo = asset_manager.get_media_info(video_path)
            dur_sec = minfo.get("duration_sec", 0.0)
            max_sec = 60 if is_story else 900
            if dur_sec > max_sec:
                dur_m = int(dur_sec // 60)
                dur_s = int(dur_sec % 60)
                dur_str = f"{dur_m}m {dur_s}s" if dur_m > 0 else f"{dur_s}s"
                return {
                    "status": "failed",
                    "platform": "Instagram",
                    "error": f"Video duration is {dur_str} (exceeds Instagram {'Stories' if is_story else 'Reels'} limit of {max_sec}s)."
                }
        except Exception:
            pass

        target_path, is_temp = self.prepare_compliant_instagram_video(video_path)
        file_size = target_path.stat().st_size
        logging.info(f"[MetaUploader] Initializing Instagram Reel upload for {self.ig_user_id}: ({round(file_size/(1024*1024), 1)} MB)")

        # The caption arrives complete (house format incl. its hashtag line)
        full_caption = (caption or "").strip()

        # Step 1: Initialize Resumable Upload Session
        init_url = f"{self.base_url}/{self.ig_user_id}/media"
        init_params = {
            "media_type": media_type,
            "upload_type": "resumable",
            "access_token": self.page_token
        }
        if not is_story:
            init_params["caption"] = full_caption

        try:
            init_res = requests.post(init_url, data=init_params, timeout=30).json()
            if "id" not in init_res or "uri" not in init_res:
                err_msg = init_res.get("error", {}).get("message", "Could not initialize Instagram Reel upload session")
                if is_temp and target_path.exists():
                    try:
                        target_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                return {"status": "failed", "platform": "Instagram", "error": err_msg, "details": init_res}

            container_id = init_res["id"]
            upload_uri = init_res["uri"]
            logging.info(f"[MetaUploader] Instagram container created: {container_id}. Streaming binary to {upload_uri[:45]}...")

            # Step 2: Upload Video Binary Stream to rupload endpoint (in pieces, see _resumable_upload)
            upload = self._resumable_upload(upload_uri, target_path)
            if not upload["success"]:
                if is_temp and target_path.exists():
                    try:
                        target_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                return {
                    "status": "failed",
                    "platform": "Instagram",
                    "error": f"Upload stream failed: {upload['error']}"
                }

            # Step 3: Poll status until FINISHED (Meta video encoding)
            status_url = f"{self.base_url}/{container_id}"
            status_params = {"fields": "status_code,status", "access_token": self.page_token}

            max_polls = 60
            poll_interval = 4
            status_code = "IN_PROGRESS"

            for poll_idx in range(max_polls):
                time.sleep(poll_interval)
                s_resp = requests.get(status_url, params=status_params, timeout=15).json()
                status_code = s_resp.get("status_code", "UNKNOWN")
                logging.info(f"[MetaUploader] Container {container_id} status poll {poll_idx+1}/{max_polls}: {status_code}")

                if status_code == "FINISHED":
                    break
                elif status_code in ("ERROR", "EXPIRED"):
                    err_detail = s_resp.get("status", "Unknown processing error")
                    if is_temp and target_path.exists():
                        try:
                            target_path.unlink(missing_ok=True)
                        except Exception:
                            pass
                    return {
                        "status": "failed",
                        "platform": "Instagram",
                        "error": f"Meta video processing failed with status {status_code}: {err_detail}",
                        "details": s_resp
                    }

            if status_code != "FINISHED":
                if is_temp and target_path.exists():
                    try:
                        target_path.unlink(missing_ok=True)
                    except Exception:
                        pass
                return {
                    "status": "failed",
                    "platform": "Instagram",
                    "error": f"Video encoding timed out after {max_polls * poll_interval}s. Status is still {status_code}."
                }

            # Step 4: Publish Container
            pub_url = f"{self.base_url}/{self.ig_user_id}/media_publish"
            pub_params = {
                "creation_id": container_id,
                "access_token": self.page_token
            }
            pub_resp = requests.post(pub_url, data=pub_params, timeout=30).json()

            # Clean up temp file
            if is_temp and target_path.exists():
                try:
                    target_path.unlink(missing_ok=True)
                except Exception:
                    pass

            if "id" in pub_resp:
                media_id = pub_resp["id"]
                # Try getting permalink
                try:
                    media_info = requests.get(
                        f"{self.base_url}/{media_id}",
                        params={"fields": "permalink", "access_token": self.page_token},
                        timeout=10
                    ).json()
                    ig_url = media_info.get("permalink") or f"https://www.instagram.com/reel/{media_id}"
                except Exception:
                    ig_url = f"https://www.instagram.com/reel/{media_id}"

                # Links comment right after posting (Stories can't be commented on)
                first_comment_info = None if is_story else self._first_comment(media_id, pinned_comment, None)

                logging.info(f"[MetaUploader] Reel published successfully to Instagram: {ig_url}")
                return {
                    "status": "published",
                    "platform": "Instagram",
                    "id": media_id,
                    "url": ig_url,
                    "first_comment": first_comment_info,
                    "is_story": is_story,
                    "message": f"Published {'Story' if is_story else 'Reel'} to Instagram: {ig_url}"
                }
            else:
                err_msg = pub_resp.get("error", {}).get("message", "Failed to publish Instagram Reel container")
                return {"status": "failed", "platform": "Instagram", "error": err_msg, "details": pub_resp}

        except Exception as e:
            if is_temp and target_path.exists():
                try:
                    target_path.unlink(missing_ok=True)
                except Exception:
                    pass
            logging.error(f"[MetaUploader] Instagram Reel upload exception: {e}")
            return {"status": "failed", "platform": "Instagram", "error": str(e)}

meta_uploader = MetaUploader()
