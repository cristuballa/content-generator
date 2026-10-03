"""
OAuth Callback Bridge Server.
Intercepts the Google / Threads OAuth callback on http://localhost:<oauth_callback_port>/rest/oauth2-credential/callback
(port 5678 by default, see server.oauth_callback_port in config.json) and completes authentication.
If another program (e.g. n8n) already owns the port, the bridge does not start and reports who holds it,
so sign-in falls back to pasting the redirect URL into the Studio auth dialog.
"""

import os
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

import sys
import socket
import threading
import urllib.parse
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Dict, Optional

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from core.config import config_manager
from core.youtube_uploader import YouTubeUploader
from core.threads_uploader import threads_uploader

_server_instance = None
_server_thread = None
_last_error: Optional[str] = None


class _ExclusiveHTTPServer(HTTPServer):
    """HTTPServer that refuses to share its port. The stock HTTPServer sets SO_REUSEADDR, which on
    Windows lets it bind a port another program (e.g. n8n) is already listening on."""
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

class OAuth5678Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/rest/oauth2-credential/callback", "/api/social/threads/callback"):
            qs = urllib.parse.parse_qs(parsed.query)
            code = qs.get("code", [None])[0]
            error = qs.get("error", [None])[0]
            state = qs.get("state", [None])[0]

            if error:
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"<h3>OAuth Authorization Error</h3><p>{error}</p>".encode("utf-8"))
                return

            if code:
                # Differentiate between Google OAuth code (typically starts with '4/' or '4/0A') vs Threads code
                is_threads = state == "threads" or "threads" in parsed.path or (not code.startswith("4/"))
                if is_threads:
                    redirect_uri = f"http://localhost:{self.server.server_port}{parsed.path}"
                    res = threads_uploader.exchange_code(code, redirect_uri)
                    if res.get("success"):
                        u_name = res.get("username", "Threads User")
                        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Threads Connected</title>
    <meta charset="utf-8">
</head>
<body style="background:#080b11;color:#fff;font-family:system-ui,-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
    <div style="background:#101522;padding:48px 40px;border-radius:24px;border:1px solid #232d42;text-align:center;max-width:440px;box-shadow:0 25px 60px rgba(0,0,0,0.7);">
        <div style="width:68px;height:68px;border-radius:50%;background:rgba(168,85,247,0.15);color:#a855f7;display:flex;align-items:center;justify-content:center;margin:0 auto 20px auto;font-size:36px;font-weight:bold;border:1px solid rgba(168,85,247,0.3);">@</div>
        <h2 style="color:#ffffff;margin:0 0 10px 0;font-size:24px;font-weight:800;">Threads Connected!</h2>
        <p style="color:#94a3b8;font-size:14px;line-height:1.6;margin:0 0 24px 0;">
            Successfully connected to <b style="color:#fff;">@{u_name}</b> via your Instagram account.<br>
            Direct Reel & video posting is now active in KCT Studio.
        </p>
        <button onclick="window.close()" style="background:#a855f7;color:#fff;border:none;padding:12px 32px;border-radius:12px;font-weight:800;cursor:pointer;font-size:14px;box-shadow:0 4px 15px rgba(168,85,247,0.3);">Close Window</button>
    </div>
    <script>
        setTimeout(function() {{
            try {{ window.close(); }} catch(e) {{}}
        }}, 3500);
    </script>
</body>
</html>"""
                        self.send_response(200)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(html.encode("utf-8"))
                        logging.info(f"[OAuth Bridge] Successfully connected Threads: @{u_name}")
                        return
                    else:
                        # Fallback: maybe it's YouTube after all
                        if not state:
                            uploader = YouTubeUploader()
                            yt_res = uploader.exchange_code(code, config_manager.get_oauth_redirect_uri())
                            if yt_res.get("success"):
                                ch = yt_res.get("channel", {})
                                ch_title = ch.get("title", "YouTube Channel")
                                ch_subs = ch.get("subscriber_count", "0")
                                html = f"""<!DOCTYPE html>
<html>
<head><title>YouTube Connected</title><meta charset="utf-8"></head>
<body style="background:#080b11;color:#fff;font-family:system-ui,-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
    <div style="background:#101522;padding:48px 40px;border-radius:24px;border:1px solid #232d42;text-align:center;max-width:440px;box-shadow:0 25px 60px rgba(0,0,0,0.7);">
        <div style="width:68px;height:68px;border-radius:50%;background:rgba(34,197,94,0.15);color:#22c55e;display:flex;align-items:center;justify-content:center;margin:0 auto 20px auto;font-size:36px;font-weight:bold;border:1px solid rgba(34,197,94,0.3);">✓</div>
        <h2 style="color:#ffffff;margin:0 0 10px 0;font-size:24px;font-weight:800;">YouTube Connected!</h2>
        <p style="color:#94a3b8;font-size:14px;line-height:1.6;margin:0 0 24px 0;">Successfully connected to <b style="color:#fff;">{ch_title}</b> ({ch_subs} subscribers).</p>
        <button onclick="window.close()" style="background:#FFE614;color:#000;border:none;padding:12px 32px;border-radius:12px;font-weight:800;cursor:pointer;font-size:14px;">Close Window</button>
    </div>
</body></html>"""
                                self.send_response(200)
                                self.send_header("Content-Type", "text/html; charset=utf-8")
                                self.end_headers()
                                self.wfile.write(html.encode("utf-8"))
                                return

                        self.send_response(500)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(f"<h3>Token Exchange Failed</h3><p>{res.get('error')}</p>".encode("utf-8"))
                        return

                # Standard YouTube Handler
                uploader = YouTubeUploader()
                res = uploader.exchange_code(code, config_manager.get_oauth_redirect_uri())
                if res.get("success"):
                    ch = res.get("channel", {})
                    ch_title = ch.get("title", "YouTube Channel")
                    ch_subs = ch.get("subscriber_count", "0")
                    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>YouTube Connected</title>
    <meta charset="utf-8">
</head>
<body style="background:#080b11;color:#fff;font-family:system-ui,-apple-system,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
    <div style="background:#101522;padding:48px 40px;border-radius:24px;border:1px solid #232d42;text-align:center;max-width:440px;box-shadow:0 25px 60px rgba(0,0,0,0.7);">
        <div style="width:68px;height:68px;border-radius:50%;background:rgba(34,197,94,0.15);color:#22c55e;display:flex;align-items:center;justify-content:center;margin:0 auto 20px auto;font-size:36px;font-weight:bold;border:1px solid rgba(34,197,94,0.3);">✓</div>
        <h2 style="color:#ffffff;margin:0 0 10px 0;font-size:24px;font-weight:800;">YouTube Connected!</h2>
        <p style="color:#94a3b8;font-size:14px;line-height:1.6;margin:0 0 24px 0;">
            Successfully connected to <b style="color:#fff;">{ch_title}</b> ({ch_subs} subscribers).<br>
            Direct video and shorts upload is now active in KCT Studio.
        </p>
        <button onclick="window.close()" style="background:#FFE614;color:#000;border:none;padding:12px 32px;border-radius:12px;font-weight:800;cursor:pointer;font-size:14px;box-shadow:0 4px 15px rgba(255,230,20,0.3);">Close Window</button>
    </div>
    <script>
        setTimeout(function() {{
            try {{ window.close(); }} catch(e) {{}}
        }}, 3500);
    </script>
</body>
</html>"""
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(html.encode("utf-8"))
                    logging.info(f"[OAuth Bridge] Successfully connected YouTube: {ch_title}")
                    return
                else:
                    self.send_response(500)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(f"<h3>Token Exchange Failed</h3><p>{res.get('error')}</p>".encode("utf-8"))
                    return

            self.send_response(400)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<h3>Invalid Request</h3><p>No authorization code found.</p>")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        # Suppress noisy standard library logging
        pass

def _port_accepts_connections(port: int) -> bool:
    """True if something already listens on localhost:<port> (IPv4 or IPv6, since browsers try both)."""
    for host in ("127.0.0.1", "::1"):
        try:
            with socket.create_connection((host, port), timeout=0.3):
                return True
        except OSError:
            continue
    return False


def _describe_port_owner(port: int) -> str:
    """Best-effort 'name.exe (PID n)' of the process listening on port."""
    try:
        import psutil
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN and conn.pid:
                return f"{psutil.Process(conn.pid).name()} (PID {conn.pid})"
    except Exception:
        pass
    return "another program"


def start_oauth_bridge(port: Optional[int] = None) -> bool:
    global _server_instance, _server_thread, _last_error
    if _server_instance is not None:
        return True
    port = port or config_manager.get_oauth_callback_port()
    if _port_accepts_connections(port):
        _last_error = (
            f"Port {port} is already used by {_describe_port_owner(port)} (n8n?), so sign-in can't finish automatically. "
            f"Stop that program, or after clicking Allow copy the full URL from the browser's address bar into the code box."
        )
        logging.warning(f"[OAuth Bridge] {_last_error}")
        return False
    try:
        _server_instance = _ExclusiveHTTPServer(("127.0.0.1", port), OAuth5678Handler)
        _server_thread = threading.Thread(target=_server_instance.serve_forever, daemon=True)
        _server_thread.start()
        _last_error = None
        logging.info(f"[OAuth Bridge] Server listening on http://127.0.0.1:{port}/rest/oauth2-credential/callback")
        print(f"[OAuth Bridge] Server listening on http://127.0.0.1:{port}/rest/oauth2-credential/callback", flush=True)
        return True
    except Exception as e:
        _server_instance = None
        _last_error = f"Could not bind OAuth callback port {port}: {e}"
        logging.warning(f"[OAuth Bridge] {_last_error}")
        return False


def get_oauth_bridge_status() -> Dict[str, Any]:
    return {
        "running": _server_instance is not None,
        "port": _server_instance.server_port if _server_instance else config_manager.get_oauth_callback_port(),
        "redirect_uri": config_manager.get_oauth_redirect_uri(),
        "error": None if _server_instance else _last_error
    }


def ensure_oauth_bridge() -> Dict[str, Any]:
    """Starts the bridge if it isn't running (e.g. n8n has since been stopped) and returns its status."""
    start_oauth_bridge()
    return get_oauth_bridge_status()


def stop_oauth_bridge():
    global _server_instance, _server_thread
    if _server_instance:
        try:
            _server_instance.shutdown()
            _server_instance.server_close()
        except Exception:
            pass
        _server_instance = None
        _server_thread = None

if __name__ == "__main__":
    start_oauth_bridge()
    import time
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_oauth_bridge()
