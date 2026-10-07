"""Who writes a long-form episode's scene prompts after its narration is recorded (generate_video.py reads the choice
from generator_settings.json in the project): Claude Code and/or Gemini CLI, headless, or "manual" (the render pauses).
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

SETTINGS_FILE = "generator_settings.json"
DEFAULT_WRITER = "claude,gemini"
WRITER_OPTIONS = ["claude,gemini", "gemini,claude", "claude", "gemini", "manual"]


def find_claude_cli() -> Optional[str]:
    """`claude` on PATH, else the native install (~/.local/bin, which may not be on PATH), else the newest copy
    bundled with the Claude desktop app (same rule as generate_video.py)."""
    found = shutil.which("claude")
    if found:
        return found
    native = Path.home() / ".local" / "bin" / "claude.exe"
    if native.exists():
        return str(native)
    pattern = os.path.join(os.environ.get("APPDATA", ""), "Claude", "claude-code", "*", "*", "claude.exe")
    found_all = sorted(glob.glob(pattern), key=lambda p: tuple(int(x) for x in re.findall(r"\d+", Path(p).parent.parent.name)))
    return found_all[-1] if found_all else None


def find_gemini_cli() -> Optional[str]:
    found = shutil.which("gemini")
    if found:
        return found
    cmd = os.path.join(os.environ.get("APPDATA", ""), "npm", "gemini.cmd")
    return cmd if os.path.exists(cmd) else None


def claude_signed_in(exe: str) -> Optional[bool]:
    """`claude auth status` (local, no request). None when it can't tell."""
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY"):
        return True
    cf = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if sys.platform == "win32" else 0
    try:
        r = subprocess.run([exe, "auth", "status"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30, stdin=subprocess.DEVNULL, creationflags=cf)
        return bool(json.loads(r.stdout).get("loggedIn"))
    except Exception:
        return None


def get_setting(project_path: str) -> str:
    try:
        value = json.loads((Path(project_path) / SETTINGS_FILE).read_text(encoding="utf-8")).get("scene_prompt_writer")
    except Exception:
        value = None
    return value if value in WRITER_OPTIONS else DEFAULT_WRITER


def set_setting(project_path: str, value: str) -> str:
    if value not in WRITER_OPTIONS:
        raise ValueError(f"Unknown prompt writer '{value}'")
    settings_p = Path(project_path) / SETTINGS_FILE
    try:
        data = json.loads(settings_p.read_text(encoding="utf-8")) if settings_p.exists() else {}
    except Exception:
        data = {}
    data["scene_prompt_writer"] = value
    settings_p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return value


def status(project_path: str) -> Dict[str, Any]:
    claude = find_claude_cli()
    gemini = find_gemini_cli()
    return {
        "setting": get_setting(project_path),
        "options": WRITER_OPTIONS,
        # Gemini's sign-in can only be checked by asking it something, so the render checks it when it is used
        "claude": {"installed": bool(claude), "signed_in": claude_signed_in(claude) if claude else False},
        "gemini": {"installed": bool(gemini), "signed_in": None},
    }
