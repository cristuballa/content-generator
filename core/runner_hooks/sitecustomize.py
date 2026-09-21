"""
KCT Studio Subprocess Environment Hook
Automatically injected into pipeline subprocesses via PYTHONPATH.
Ensures that all descendant subprocess invocations on Windows suppress console shell popups (CREATE_NO_WINDOW)
so the user never experiences intrusive terminal/cmd windows flashing or popping up over the dashboard.
"""
import sys
import subprocess

if sys.platform == "win32":
    import os
    _orig_popen_init = subprocess.Popen.__init__
    CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)

    def _silent_popen_init(self, *args, **kwargs):
        # 1. Strip DETACHED_PROCESS because on Windows 11 DETACHED_PROCESS overrides
        # CREATE_NO_WINDOW and causes Windows Terminal (OpenConsole) to pop open an empty window!
        if "creationflags" in kwargs:
            kwargs["creationflags"] = (kwargs["creationflags"] & ~DETACHED_PROCESS) | CREATE_NO_WINDOW
        elif len(args) > 13:
            args = list(args)
            args[13] = (args[13] & ~DETACHED_PROCESS) | CREATE_NO_WINDOW
        else:
            kwargs["creationflags"] = CREATE_NO_WINDOW

        # 2. If command is launching python.exe with main.py (ComfyUI), convert to pythonw.exe if it exists
        cmd_args = kwargs.get("args") or (args[0] if len(args) > 0 else None)
        if isinstance(cmd_args, (list, tuple)) and len(cmd_args) > 0:
            exe_str = str(cmd_args[0])
            joined_cmd = " ".join(str(x) for x in cmd_args)
            if exe_str.lower().endswith("python.exe") and "main.py" in joined_cmd:
                pyw_cand = exe_str[:-10] + "pythonw.exe"
                if os.path.exists(pyw_cand):
                    if isinstance(cmd_args, list):
                        cmd_args[0] = pyw_cand
                    elif isinstance(cmd_args, tuple):
                        new_cmd = list(cmd_args)
                        new_cmd[0] = pyw_cand
                        if "args" in kwargs:
                            kwargs["args"] = new_cmd
                        else:
                            args = list(args)
                            args[0] = new_cmd

        return _orig_popen_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _silent_popen_init

    # Fix Windows ProactorEventLoop WinError 10054 on client disconnect
    try:
        import asyncio.proactor_events
        _orig_call_connection_lost = asyncio.proactor_events._ProactorBasePipeTransport._call_connection_lost

        def _silenced_call_connection_lost(self, exc):
            try:
                _orig_call_connection_lost(self, exc)
            except (ConnectionResetError, OSError):
                try:
                    if hasattr(self, "_sock") and self._sock is not None:
                        self._sock.close()
                        self._sock = None
                    if hasattr(self, "_server") and self._server is not None:
                        self._server._detach()
                        self._server = None
                    self._called_connection_lost = True
                except Exception:
                    pass

        asyncio.proactor_events._ProactorBasePipeTransport._call_connection_lost = _silenced_call_connection_lost
    except Exception:
        pass
