"""
Desktop Notification Service for KCT Studio Pipeline
Sends native Windows 10/11 Toast Notifications via winotify with graceful fallback.
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("kct.notifier")

ICON_PATH = Path(__file__).resolve().parent.parent / "static" / "favicon.ico"


def notify_desktop(title: str, message: str, icon_path: Optional[str] = None):
    """
    Sends a native Windows 10/11 desktop toast notification.
    Safe: Never raises unhandled exceptions.
    """
    try:
        from winotify import Notification

        icon = str(icon_path or (ICON_PATH if ICON_PATH.exists() else ""))
        toast = Notification(
            app_id="KCT Studio Pipeline",
            title=title,
            msg=message,
            icon=icon if icon else None
        )
        toast.show()
        logger.info(f"Desktop notification shown: {title} - {message}")
    except Exception as e:
        logger.warning(f"Could not display native desktop notification: {e}")
