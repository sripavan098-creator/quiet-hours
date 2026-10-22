import json
import sys
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(ROOT))

import ring_adapter  # noqa: E402
import server  # noqa: E402
from ring_client import RingClient, Tokens  # noqa: E402


def ring_payload(event_id="evt_1", device="ava1.ring.device.kitchen-cam", t="2026-10-21T09:00:00+05:30", type_="motion_detected"):
    return {
        "meta": {"account_id": "ava1.ring.account.TEST", "time": t},
        "data": {
            "id": event_id,
            "type": type_,
            "attributes": {"source": device, "sub_type": "human"},
            "relationships": {"devices": {"links": {"self": f"/v1/devices/{device}"}}},
        },
    }


class SignatureFormat(unittest.TestCase):
    def test_header_format_is_sha256_prefixed_hex(self):
        sig = server.sign(b"{}", b"k")
        self.assertTrue(sig.startswith("sha256="))
        self.assertEqual(len(sig), len("sha256=") + 64)

    def test_valid_signature_accepted(self):
        body = b'{"meta":{}}'
        self.assertTrue(server.verify_signature(body, server.sign(body)))

    def test_bare_hex_without_prefix_rejected(self):
        body = b"{}"
        bare = server.sign(body).removeprefix("sha256=")
        self.assertFalse(server.verify_signature(body, bare))

    def test_tampered_body_rejected(self):
        body = b'{"a":1}'
        self.assertFalse(server.verify_signature(b'{"a":2}', server.sign(body)))

    def test_missing_header_rejected(self):
        self.assertFalse(server.verify_signature(b"{}", None))


class AdapterShape(unittest.TestCase):
    zones = {"ava1.ring.device.kitchen-cam": "kitchen"}

    def test_maps_ring_payload_to_internal_event(self):
        [ev] = ring_adapter.normalise(ring_payload(), self.zones)
        self.assertEqual(ev["device_id"], "kitchen")
        self.assertEqual(ev["kind"], "motion")
        self.assertEqual(ev["created_at"], "2026-10-21T09:00:00+05:30")
        self.assertEqual(ev["source"], "ring")

    def test_unmapped_device_is_skipped(self):
        self.assertEqual(ring_adapter.normalise(ring_payload(device="ava1.ring.device.unknown"), self.zones), [])

    def test_unknown_type_from_real_device_is_skipped(self):
        self.assertEqual(ring_adapter.normalise(ring_payload(type_="contact_open"), self.zones), [])

    def test_missing_fields_raise(self):
        with self.assertRaises(ring_adapter.PayloadError):
            ring_adapter.normalise({"meta": {}, "data": {}}, self.zones)

    def test_bad_timestamp_raises(self):
        with self.assertRaises(ring_adapter.PayloadError):
            ring_adapter.normalise(ring_payload(t="not-a-time"), self.zones)

    def test_zone_map_parses_json(self):
        self.assertEqual(ring_adapter.load_zone_map('{"a": "kitchen"}'), {"a": "kitchen"})
        with self.assertRaises(ring_adapter.PayloadError):
            ring_adapter.load_zone_map("[1,2]")


class WebhookEndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved_dev = server.DEV_MODE
        server.DEV_MODE = True  # the demo endpoint exists only in development
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        # Map the test device for this run only.
        server.ZONE_MAP["ava1.ring.device.kitchen-cam"] = "kitchen"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        server.ZONE_MAP.pop("ava1.ring.device.kitchen-cam", None)
        server.DEV_MODE = cls.saved_dev

    def post(self, path, body: bytes, headers=None):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=body, method="POST")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read() or b"{}")

    def test_unsigned_is_401(self):
        code, _ = self.post("/api/ring/webhook", json.dumps(ring_payload("evt_u")).encode())
        self.assertEqual(code, 401)

    def test_malformed_signed_payload_is_400(self):
        body = b'{"meta": {}, "data": {}}'
        code, _ = self.post("/api/ring/webhook", body, {"X-Signature": server.sign(body)})
        self.assertEqual(code, 400)

    def test_signed_payload_accepted_and_deduplicated(self):
        body = json.dumps(ring_payload("evt_dedupe_1")).encode()
        headers = {"X-Signature": server.sign(body)}
        code, first = self.post("/api/ring/webhook", body, headers)
        self.assertEqual(code, 200)
        self.assertEqual(first["accepted"], 1)
        _, second = self.post("/api/ring/webhook", body, headers)
        self.assertEqual(second["accepted"], 0)

    def test_demo_collapse_loads_through_signed_path(self):
        code, status = self.post("/api/sim/demo", b'{"scenario": "collapse"}')
        self.assertEqual(code, 200)
        self.assertEqual(status["state"], "alert")


class PartnerClient(unittest.TestCase):
    def test_refresh_on_401_then_retries(self):
        calls = []

        def transport(req):
            calls.append((req.full_url, req.get_method()))
            if "oauth" in req.full_url:
                return 200, json.dumps({"access_token": "new", "refresh_token": "r2"}).encode()
            if req.get_header("Authorization") == "Bearer old":
                return 401, b"{}"
            return 200, json.dumps({"data": []}).encode()

        client = RingClient("cid", "sec", Tokens("old", "r1"), transport=transport)
        self.assertEqual(client.devices(), {"data": []})
        self.assertEqual(client.tokens.access_token, "new")
        self.assertTrue(any("oauth" in url for url, _ in calls))


if __name__ == "__main__":
    unittest.main()
