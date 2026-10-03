"""
Test package. Run from the project root with:

    python -m unittest discover -s tests -t .

Importing this package blocks real HTTP calls, so no test can ever reach a live social account.
Every test module imports it first, before any core module is loaded.
"""

import requests.sessions


def _network_disabled(*args, **kwargs):
    raise RuntimeError("Network access is disabled in tests")


requests.sessions.Session.request = _network_disabled
