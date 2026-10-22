import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(ROOT))

import analysis  # noqa: E402
import server  # noqa: E402


def _payload(event_id, device):
    return {
        "meta": {"account_id": "ava1.ring.account.TEST", "time": "2026-10-21T09:00:00+05:30"},
        "data": {"id": event_id, "type": "motion_detected", "attributes": {"source": device}},
    }


class DeviceEndpoints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_dev = server.DEV_MODE
        server.DEV_MODE = True
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        server.DEV_MODE = cls.saved_dev

    def setUp(self):
        self.saved_map = dict(server.ZONE_MAP)
        self.saved_events = dict(server._events)

    def tearDown(self):
        server.ZONE_MAP.clear()
        server.ZONE_MAP.update(self.saved_map)
        with server._lock:
            server._events.clear()
            server._events.update(self.saved_events)

    def call(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method)
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read() or b"{}")

    def test_disabled_outside_dev(self):
        server.DEV_MODE = False
        try:
            self.assertEqual(self.call("GET", "/api/devices")[0], 404)
            self.assertEqual(self.call("PUT", "/api/devices/sim.kitchen/room", {"room": "bathroom"})[0], 404)
        finally:
            server.DEV_MODE = True

    def test_lists_mapped_devices_and_rooms(self):
        code, body = self.call("GET", "/api/devices")
        self.assertEqual(code, 200)
        self.assertEqual(body["rooms"], sorted(analysis.ZONE_IDS))
        ids = {d["id"] for d in body["devices"]}
        self.assertIn("sim.kitchen", ids)
        self.assertTrue(all(d["source"] in {"simulator", "ring"} for d in body["devices"]))

    def test_valid_room_saved(self):
        code, body = self.call("PUT", "/api/devices/sim.kitchen/room", {"room": "bathroom"})
        self.assertEqual(code, 200)
        room = next(d["room"] for d in body["devices"] if d["id"] == "sim.kitchen")
        self.assertEqual(room, "bathroom")

    def test_invalid_room_rejected(self):
        code, _ = self.call("PUT", "/api/devices/sim.kitchen/room", {"room": "garage"})
        self.assertEqual(code, 400)
        code, _ = self.call("PUT", "/api/devices/sim.kitchen/room", {"room": 7})
        self.assertEqual(code, 400)

    def test_invalid_device_id_rejected(self):
        code, _ = self.call("PUT", "/api/devices/bad%20id/room", {"room": "kitchen"})
        self.assertEqual(code, 400)

    def test_remap_relabels_stored_events(self):
        raw = json.dumps(_payload("evt_r1", "ava1.ring.device.remap")).encode()
        server.ZONE_MAP["ava1.ring.device.remap"] = "kitchen"
        self.assertEqual(server.handle_webhook(raw, server.sign(raw))[0], 200)
        self.call("PUT", "/api/devices/ava1.ring.device.remap/room", {"room": "bedroom"})
        with server._lock:
            self.assertEqual(server._events["evt_r1"]["device_id"], "bedroom")

    def test_unmap_blanks_stored_events_so_rules_ignore_them(self):
        raw = json.dumps(_payload("evt_u1", "ava1.ring.device.unmap")).encode()
        server.ZONE_MAP["ava1.ring.device.unmap"] = "kitchen"
        server.handle_webhook(raw, server.sign(raw))
        self.call("PUT", "/api/devices/ava1.ring.device.unmap/room", {"room": ""})
        with server._lock:
            self.assertEqual(server._events["evt_u1"]["device_id"], "")
        self.assertNotIn("ava1.ring.device.unmap", server.ZONE_MAP)


if __name__ == "__main__":
    unittest.main()
