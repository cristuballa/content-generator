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
