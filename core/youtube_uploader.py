"""
Google YouTube Data API v3 Direct Resumable Uploader.
Uploads 4K long-form documentaries and vertical Shorts directly to YouTube using chunked resumable transfers.
"""

import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

import json
import time
import logging
import ssl
import socket
import http.client
from pathlib import Path
from typing import Dict, Any, Optional, List, Callable
import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow, InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from core.config import config_manager
from core.hashtags import PLATFORM_HASHTAG_LIMITS, append_hashtag, find_hashtags


def iso_to_timestamp(iso: str) -> float:
    """'2026-10-05T19:15:00.000Z' -> UNIX time (0 if unparseable)."""
    import datetime
    try:
        return datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtubepartner",
    "https://www.googleapis.com/auth/youtubepartner-channel-audit"
]

class YouTubeUploader:
    def __init__(self):
        self.root_dir = Path(__file__).resolve().parent.parent
        self.token_file = self.root_dir / "data" / "youtube_token.json"
        self._client_secrets_file: Optional[Path] = None

    def find_client_secrets_file(self) -> Optional[Path]:
        """Locates the Google OAuth client secrets JSON file."""
        if self._client_secrets_file and self._client_secrets_file.exists():
            return self._client_secrets_file

        candidates = [
            self.root_dir / "docs" / "client_secret.json",
            self.root_dir / "data" / "client_secrets.json",
            self.root_dir / "config" / "client_secrets.json"
        ]
        # Also check docs/*.json
        docs_dir = self.root_dir / "docs"
        if docs_dir.exists():
            for p in docs_dir.glob("*secret*.json"):
                candidates.insert(0, p)

        for cand in candidates:
            if cand.exists() and cand.stat().st_size > 50:
                self._client_secrets_file = cand
                return cand
        return None

    def get_credentials(self) -> Optional[Credentials]:
        """Loads and auto-refreshes credentials from data/youtube_token.json."""
        if not self.token_file.exists():
            return None

        try:
            creds = Credentials.from_authorized_user_file(str(self.token_file), SCOPES)
            if creds and creds.expired and creds.refresh_token:
                request = google.auth.transport.requests.Request()
                creds.refresh(request)
                # Persist refreshed token
                self.token_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.token_file, "w", encoding="utf-8") as f:
                    f.write(creds.to_json())
                logging.info("[YouTubeUploader] YouTube OAuth token automatically refreshed.")
            return creds if creds and creds.valid else None
        except Exception as e:
            logging.error(f"[YouTubeUploader] Error loading credentials: {e}")
            return None

    def is_authenticated(self) -> bool:
        """Checks if YouTube OAuth token is present and valid."""
        creds = self.get_credentials()
        return bool(creds and creds.valid)

    def get_channel_info(self) -> Dict[str, Any]:
        """Retrieves authorized YouTube channel details."""
        creds = self.get_credentials()
        if not creds:
            return {"authenticated": False, "error": "Not authenticated with YouTube"}

        try:
            youtube = build("youtube", "v3", credentials=creds)
            resp = youtube.channels().list(part="snippet,statistics", mine=True).execute()
            items = resp.get("items", [])
            if not items:
                return {"authenticated": True, "error": "No YouTube channel associated with this account"}

            ch = items[0]
            snippet = ch.get("snippet", {})
            stats = ch.get("statistics", {})
            return {
                "authenticated": True,
                "channel_id": ch.get("id"),
                "title": snippet.get("title"),
                "custom_url": snippet.get("customUrl"),
                "description": snippet.get("description", "")[:120],
                "subscriber_count": stats.get("subscriberCount", "0"),
                "video_count": stats.get("videoCount", "0"),
                "avatar_url": snippet.get("thumbnails", {}).get("default", {}).get("url")
            }
        except Exception as e:
            return {"authenticated": False, "error": str(e)}

    def generate_auth_url(self, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
        """Generates Google OAuth URL for user to grant YouTube upload permissions."""
        sec_file = self.find_client_secrets_file()
        if not sec_file:
            return {"success": False, "error": "Google client_secrets.json not found in docs/ or data/"}

        try:
            flow = Flow.from_client_secrets_file(str(sec_file), scopes=SCOPES)
            flow.autogenerate_code_verifier = False
            target_uri = redirect_uri or config_manager.get_oauth_redirect_uri()
            flow.redirect_uri = target_uri
            auth_url, state = flow.authorization_url(
                access_type="offline",
                include_granted_scopes="true",
                prompt="consent"
            )
            # Persist state & verifier for exchange step
            state_file = self.root_dir / "data" / "oauth_flow_state.json"
            state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({
                    "state": state,
                    "code_verifier": getattr(flow, "code_verifier", None),
                    "redirect_uri": target_uri
                }, f)

            return {
                "success": True,
                "auth_url": auth_url,
                "redirect_uri": target_uri,
                "client_id": flow.client_config.get("client_id")
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def exchange_code(self, code: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
        """Exchanges authorization code for tokens and saves to data/youtube_token.json."""
        sec_file = self.find_client_secrets_file()
        if not sec_file:
            return {"success": False, "error": "Google client_secrets.json not found"}

        try:
            clean_code = (code or "").strip()
            # If the user pasted the entire redirect URL, extract the code parameter
            if "code=" in clean_code or "http" in clean_code:
                import urllib.parse
                parsed = urllib.parse.urlparse(clean_code)
                qs = urllib.parse.parse_qs(parsed.query or parsed.path)
                if "code" in qs and qs["code"]:
                    clean_code = qs["code"][0]

            flow = Flow.from_client_secrets_file(str(sec_file), scopes=SCOPES)
            flow.autogenerate_code_verifier = False
            target_uri = redirect_uri or config_manager.get_oauth_redirect_uri()
            flow.redirect_uri = target_uri

            # Restore saved verifier if available
            state_file = self.root_dir / "data" / "oauth_flow_state.json"
            if state_file.exists():
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        saved_st = json.load(f)
                    if saved_st.get("code_verifier"):
                        flow.code_verifier = saved_st["code_verifier"]
                    if not redirect_uri and saved_st.get("redirect_uri"):
                        flow.redirect_uri = saved_st["redirect_uri"]
                except Exception:
                    pass

            flow.fetch_token(code=clean_code)
            creds = flow.credentials

            self.token_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.token_file, "w", encoding="utf-8") as f:
                f.write(creds.to_json())

            logging.info("[YouTubeUploader] YouTube credentials successfully saved.")
            ch_info = self.get_channel_info()
            return {"success": True, "channel": ch_info}
        except Exception as e:
            logging.error(f"[YouTubeUploader] Failed to exchange auth code: {e}")
            return {"success": False, "error": str(e)}

    def post_comment(self, video_id: str, text: str, youtube: Any = None) -> Dict[str, Any]:
        """Posts a top-level comment as the channel (the API can't pin it; pin it in YouTube Studio if wanted)."""
        try:
            if youtube is None:
                creds = self.get_credentials()
                if not creds:
                    return {"success": False, "error": "YouTube is not authenticated."}
                youtube = build("youtube", "v3", credentials=creds)
            res = youtube.commentThreads().insert(
                part="snippet",
                body={"snippet": {"videoId": video_id, "topLevelComment": {"snippet": {"textOriginal": text.strip()}}}}
            ).execute()
            logging.info(f"[YouTubeUploader] Comment posted on video {video_id} (ID: {res.get('id')}).")
            return {"success": True, "id": res.get("id")}
        except Exception as e:
            logging.warning(f"[YouTubeUploader] Could not post comment on video {video_id}: {e}")
            return {"success": False, "error": str(e)}

    def upload_video(
        self,
        video_path: Path,
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        privacy_status: str = "public",
        scheduled_publish_iso: Optional[str] = None,
        is_short: bool = False,
        thumbnail_path: Optional[Path] = None,
        pinned_comment: Optional[str] = None,
        progress_callback: Optional[Callable[[float], None]] = None
    ) -> Dict[str, Any]:
        """
        Uploads a video to YouTube using the official resumable chunked protocol.
        - Supports 10MB chunked streams with automatic retry on network drops.
        - Sets custom thumbnail (thumbnail_option_1.jpg) upon completion.
        - Supports native cloud scheduling via `publishAt`.
        - Automatically creates top-level creator comment for links/call-to-actions.
        """
        if not video_path.exists():
            return {"status": "failed", "platform": "YouTube", "error": f"File not found: {video_path}"}

        creds = self.get_credentials()
        if not creds:
            return {
                "status": "failed",
                "platform": "YouTube",
                "error": "YouTube is not authenticated. Please authenticate via Studio Settings."
            }

        file_size = video_path.stat().st_size
        logging.info(f"[YouTubeUploader] Starting YouTube resumable upload for '{title}' ({round(file_size/(1024*1024), 1)} MB)")

        # Prepare description with tags & shorts hashtag if applicable.
        # Copy the tags: the caller's list is shared with the other platforms in the same dispatch.
        clean_desc = description.strip()
        tags_list = list(tags) if tags else ["BibleSecrets", "Christianity", "BibleStudy"]
        if is_short:
            if not any(t.lstrip("#").lower() == "shorts" for t in tags_list):
                tags_list.append("Shorts")
            desc_tags = [t.lower() for t in find_hashtags(clean_desc)]
            # Never push the description past YouTube's hashtag limit (it would ignore all of them)
            if "#shorts" not in desc_tags and len(desc_tags) < PLATFORM_HASHTAG_LIMITS["youtube"]:
                clean_desc = append_hashtag(clean_desc, "#Shorts")

        # YouTube category 27 = Education, 22 = People & Blogs
        body = {
            "snippet": {
                "title": title[:100],
                "description": clean_desc[:5000],
                "tags": [t.replace("#", "") for t in tags_list][:50],
                "categoryId": "27"
            },
            "status": {
                "selfDeclaredMadeForKids": False
            }
        }

        # Native Cloud Scheduling
        if scheduled_publish_iso:
            body["status"]["privacyStatus"] = "private"
            body["status"]["publishAt"] = scheduled_publish_iso
        else:
            body["status"]["privacyStatus"] = privacy_status or "public"

        try:
            youtube = build("youtube", "v3", credentials=creds)

            # 10 MB chunk size for high-speed reliable chunked uploads
            chunk_size = 10 * 1024 * 1024
            media = MediaFileUpload(
                str(video_path),
                mimetype="video/mp4",
                resumable=True,
                chunksize=chunk_size
            )

            insert_request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media
            )

            response = None
            retry_count = 0
            max_retries = 10

            while response is None:
                try:
                    status, response = insert_request.next_chunk()
                    if status and progress_callback:
                        progress_callback(status.progress())
                    if status:
                        pct = round(status.progress() * 100, 1)
                        logging.info(f"[YouTubeUploader] '{title}': {pct}% uploaded ({round(status.resumable_progress/(1024*1024), 1)} MB)")
                except HttpError as ex:
                    if ex.resp.status in [500, 502, 503, 504]:
                        retry_count += 1
                        if retry_count > max_retries:
                            raise
                        sleep_time = 2 ** retry_count
                        logging.warning(f"[YouTubeUploader] Transient HTTP {ex.resp.status}, retrying in {sleep_time}s...")
                        time.sleep(sleep_time)
                    else:
                        raise
                except (ssl.SSLError, socket.error, OSError, http.client.RemoteDisconnected) as net_err:
                    retry_count += 1
                    if retry_count > max_retries:
                        raise
                    sleep_time = 2 ** retry_count
                    logging.warning(f"[YouTubeUploader] Transient network/SSL error ({net_err}), retrying chunk in {sleep_time}s...")
                    time.sleep(sleep_time)

            video_id = response.get("id")
            if not video_id:
                return {
                    "status": "failed",
                    "platform": "YouTube",
                    "error": "Upload completed but no video ID returned",
                    "response": response
                }

            watch_url = f"https://youtu.be/{video_id}"
            logging.info(f"[YouTubeUploader] Video uploaded successfully: {watch_url}")

            # Attach custom thumbnail if present and not vertical Short
            thumb_attached = False
            if thumbnail_path and thumbnail_path.exists():
                try:
                    logging.info(f"[YouTubeUploader] Setting custom thumbnail from {thumbnail_path.name}...")
                    thumb_media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
                    youtube.thumbnails().set(
                        videoId=video_id,
                        media_body=thumb_media
                    ).execute()
                    thumb_attached = True
                    logging.info("[YouTubeUploader] Custom thumbnail set successfully.")
                except Exception as t_err:
                    logging.warning(f"[YouTubeUploader] Could not set custom thumbnail: {t_err}")

            result = {
                "status": "published",
                "platform": "YouTube",
                "id": video_id,
                "url": watch_url,
                "scheduled": bool(scheduled_publish_iso),
                "scheduled_for": scheduled_publish_iso,
                "thumbnail_attached": thumb_attached,
                "comment_posted": False,
                "message": f"{'Scheduled on' if scheduled_publish_iso else 'Published to'} YouTube: {watch_url}"
            }

            # Links comment right after posting. A scheduled video stays private until publishAt, so its comment
            # is queued and posted by the scheduler once the video is live (SocialDispatcher.post_due_comments).
            if pinned_comment and pinned_comment.strip():
                if scheduled_publish_iso:
                    result["pending_comment"] = pinned_comment.strip()
                    result["comment_due_at"] = iso_to_timestamp(scheduled_publish_iso) + 60
                else:
                    comment = self.post_comment(video_id, pinned_comment, youtube)
                    result["comment_posted"] = comment["success"]
                    result["comment_id" if comment["success"] else "comment_error"] = comment.get("id") or comment.get("error")
            return result

        except Exception as e:
            logging.error(f"[YouTubeUploader] YouTube upload error: {e}")
            return {
                "status": "failed",
                "platform": "YouTube",
                "error": str(e)
            }

youtube_uploader = YouTubeUploader()
