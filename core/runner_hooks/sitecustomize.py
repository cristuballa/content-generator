"""
KCT Studio Subprocess Environment Hook
Automatically injected into pipeline subprocesses via PYTHONPATH.
Ensures that all descendant subprocess invocations on Windows suppress console shell popups (CREATE_NO_WINDOW)
so the user never experiences intrusive terminal/cmd windows flashing or popping up over the dashboard.
"""
import sys
import subprocess

if sys.platform == "win32":
    _orig_popen_init = subprocess.Popen.__init__
    CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    def _silent_popen_init(self, *args, **kwargs):
        if "creationflags" in kwargs:
            kwargs["creationflags"] |= CREATE_NO_WINDOW
        elif len(args) > 13:
            args = list(args)
            args[13] |= CREATE_NO_WINDOW
        else:
            kwargs["creationflags"] = CREATE_NO_WINDOW
        return _orig_popen_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _silent_popen_init
