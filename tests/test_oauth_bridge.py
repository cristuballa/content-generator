import socket
import unittest

import tests  # noqa: F401  (blocks network before core modules load)
from core import oauth_bridge_5678 as bridge


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class OAuthBridgeTests(unittest.TestCase):
    def tearDown(self):
        bridge.stop_oauth_bridge()

    def test_refuses_a_port_another_program_listens_on(self):
        with socket.socket() as other:
            other.bind(("127.0.0.1", 0))
            other.listen(1)
            port = other.getsockname()[1]
            self.assertFalse(bridge.start_oauth_bridge(port))
            status = bridge.get_oauth_bridge_status()
            self.assertFalse(status["running"])
            self.assertIn(str(port), status["error"])

    def test_holds_its_port_exclusively(self):
        port = free_port()
        self.assertTrue(bridge.start_oauth_bridge(port))
        self.assertTrue(bridge.get_oauth_bridge_status()["running"])
        with self.assertRaises(OSError):
            bridge._ExclusiveHTTPServer(("127.0.0.1", port), bridge.OAuth5678Handler)


if __name__ == "__main__":
    unittest.main()
