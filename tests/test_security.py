"""Gate 1 checks: startup refusal, dev-only routes, caregiver token, body limit, home time."""
import http.client
import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(ROOT))
import _isolate  # noqa: E402,F401  (clears deployment env before server loads)

import analysis  # noqa: E402
import server  # noqa: E402

TOKEN = "caregiver-test-token-0123456789"


class StartupRules(unittest.TestCase):
    def test_dev_mode_needs_nothing(self):
        self.assertEqual(server.config_problems({"QH_ENV": "dev"}), [])

    def test_production_needs_webhook_secret(self):
        problems = server.config_problems({"QH_CAREGIVER_TOKEN": TOKEN})
        self.assertTrue(any("RING_WEBHOOK_SECRET" in p for p in problems))

    def test_production_needs_token_of_useful_length(self):
        problems = server.config_problems({"RING_WEBHOOK_SECRET": "s", "QH_CAREGIVER_TOKEN": "short"})
        self.assertTrue(any("QH_CAREGIVER_TOKEN" in p for p in problems))

    def test_production_with_both_starts(self):
        self.assertEqual(server.config_problems({"RING_WEBHOOK_SECRET": "s", "QH_CAREGIVER_TOKEN": TOKEN}), [])


class HomeTime(unittest.TestCase):
    def test_last_movement_reported_in_home_time(self):
        # 23:30 UTC on 21 Oct is 05:00 IST on 22 Oct.
        utc_event = ("kitchen", datetime(2026, 10, 21, 23, 30, tzinfo=timezone.utc))
        now = datetime(2026, 10, 22, 6, 0, tzinfo=analysis.IST)
        status = analysis.assess([utc_event], now)
        self.assertEqual(status["home"]["last_movement"], "2026-10-22T05:00:00+05:30")

    def test_naive_timestamps_rejected(self):
        with self.assertRaises(ValueError):
            analysis.to_home_time(datetime(2026, 10, 22, 6, 0))

    def test_same_instant_same_result_regardless_of_offset(self):
        a = ("kitchen", datetime(2026, 10, 22, 9, 0, tzinfo=analysis.IST))
        b = ("kitchen", datetime(2026, 10, 22, 3, 30, tzinfo=timezone.utc))
        now = datetime(2026, 10, 22, 12, 0, tzinfo=analysis.IST)
        self.assertEqual(analysis.assess([a], now)["home"], analysis.assess([b], now)["home"])


class Gate1Routes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved = (server.DEV_MODE, server.CAREGIVER_TOKEN)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        server.DEV_MODE, server.CAREGIVER_TOKEN = cls.saved

    def setUp(self):
        server.DEV_MODE = False
        server.CAREGIVER_TOKEN = TOKEN

    def tearDown(self):
        server.DEV_MODE, server.CAREGIVER_TOKEN = self.saved

    def call(self, method, path, body=None, headers=None):
        data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}", data=data, method=method)
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req) as resp:
                return resp.status, json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read() or b"{}")

    def test_demo_endpoint_absent_outside_dev(self):
        self.assertEqual(self.call("POST", "/api/sim/demo", {"scenario": "normal"})[0], 404)

    def test_status_requires_caregiver_token(self):
        self.assertEqual(self.call("GET", "/api/status")[0], 401)
        self.assertEqual(self.call("GET", "/api/status", headers={"Authorization": "Bearer wrong-token-0000000"})[0], 401)
        self.assertEqual(self.call("GET", "/api/status", headers={"Authorization": f"Bearer {TOKEN}"})[0], 200)

    def test_events_require_caregiver_token(self):
        self.assertEqual(self.call("GET", "/api/events")[0], 401)
        self.assertEqual(self.call("GET", "/api/events", headers={"Authorization": f"Bearer {TOKEN}"})[0], 200)

    def test_devices_hidden_outside_dev_even_with_token(self):
        self.assertEqual(self.call("GET", "/api/devices", headers={"Authorization": f"Bearer {TOKEN}"})[0], 404)

    def test_open_in_dev_without_token(self):
        server.DEV_MODE = True
        server.CAREGIVER_TOKEN = ""
        self.assertEqual(self.call("GET", "/api/status")[0], 200)

    def test_webhook_still_uses_signature_not_token(self):
        raw = json.dumps({"meta": {"time": "2026-10-22T09:00:00+05:30"},
                          "data": {"id": "evt_gate1", "type": "motion_detected",
                                   "attributes": {"source": "sim.kitchen"}}}).encode()
        code, _ = self.call("POST", "/api/ring/webhook", raw, {"X-Signature": server.sign(raw)})
        self.assertEqual(code, 200)

    def test_oversized_body_refused_with_413(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest("POST", "/api/ring/webhook")
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(64 * 1024 + 1))
        conn.endheaders()
        resp = conn.getresponse()
        self.assertEqual(resp.status, 413)
        conn.close()


if __name__ == "__main__":
    unittest.main()
