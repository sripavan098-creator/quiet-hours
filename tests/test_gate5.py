"""Gate 5 checks: persistence, retention, readiness, feed health, rate limits, logging."""
import contextlib
import http.client
import io
import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(ROOT))

import analysis  # noqa: E402
import server  # noqa: E402
from store import RETENTION, EventStore  # noqa: E402

TOKEN = "caregiver-gate5-token-0123456789"


def ist(h, m=0, day=22):
    return datetime(2026, 10, day, h, m, tzinfo=analysis.IST)


def event(event_id, device, when, kind="motion"):
    return {
        "event_id": event_id,
        "device_id": device,
        "ring_device_id": None,
        "kind": kind,
        "created_at": when.isoformat(),
        "source": "simulator",
    }


class Persistence(unittest.TestCase):
    def test_events_survive_reopening_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "qh.db")
            first = EventStore(path)
            self.assertEqual(first.add([event("e1", "kitchen", ist(10, 0))]), 1)
            second = EventStore(path)  # simulates a restart
            self.assertEqual([e["event_id"] for e in second.all()], ["e1"])

    def test_duplicate_event_ids_are_ignored(self):
        store = EventStore(":memory:")
        self.assertEqual(store.add([event("e1", "kitchen", ist(10, 0))]), 1)
        self.assertEqual(store.add([event("e1", "kitchen", ist(10, 0))]), 0)
        self.assertEqual(len(store.all()), 1)

    def test_retention_removes_events_older_than_window(self):
        store = EventStore(":memory:")
        old = ist(10, 0, day=1)
        store.add([event("old", "kitchen", old)])
        store.add([event("new", "kitchen", old + RETENTION + timedelta(hours=1))])
        self.assertEqual([e["event_id"] for e in store.all()], ["new"])

    def test_remap_and_clear(self):
        store = EventStore(":memory:")
        ev = dict(event("e1", "kitchen", ist(10, 0)), ring_device_id="ava1.ring.device.x")
        store.add([ev])
        store.remap("ava1.ring.device.x", "bedroom")
        self.assertEqual(store.all()[0]["device_id"], "bedroom")
        store.clear()
        self.assertEqual(store.all(), [])


class FeedHealth(unittest.TestCase):
    def setUp(self):
        self.saved = server.STORE
        server.STORE = EventStore(":memory:")

    def tearDown(self):
        server.STORE = self.saved

    def test_no_events_at_all_is_a_gap(self):
        self.assertTrue(server.current_status(ist(14, 0))["feed"]["gap_warning"])

    def test_recent_events_are_not_a_gap(self):
        server.STORE.add([event("e1", "kitchen", ist(6, 0))])
        self.assertFalse(server.current_status(ist(14, 0))["feed"]["gap_warning"])

    def test_twelve_hours_of_daytime_silence_is_a_gap(self):
        server.STORE.add([event("e1", "kitchen", ist(6, 0))])
        self.assertTrue(server.current_status(ist(19, 0))["feed"]["gap_warning"])

    def test_night_silence_is_not_a_gap(self):
        server.STORE.add([event("e1", "kitchen", ist(20, 0))])
        self.assertFalse(server.current_status(ist(6, 30, day=23))["feed"]["gap_warning"])


class Readiness(unittest.TestCase):
    def test_ready_in_dev(self):
        ok, checks = server.readiness({"QH_ENV": "dev"})
        self.assertTrue(ok)
        self.assertEqual(checks["config"], "ok")

    def test_not_ready_without_secret(self):
        ok, checks = server.readiness({"QH_CAREGIVER_TOKEN": TOKEN})
        self.assertFalse(ok)
        self.assertEqual(checks["config"], "missing settings")

    def test_ready_with_settings_and_store(self):
        ok, _ = server.readiness({"RING_WEBHOOK_SECRET": "s", "QH_CAREGIVER_TOKEN": TOKEN})
        self.assertTrue(ok)


class RateLimit(unittest.TestCase):
    def test_limit_then_refuse_per_key(self):
        limiter = server.RateLimiter(limit=2, window_s=60)
        self.assertTrue(limiter.allow("a", now=0))
        self.assertTrue(limiter.allow("a", now=1))
        self.assertFalse(limiter.allow("a", now=2))
        self.assertTrue(limiter.allow("b", now=2))  # another client is unaffected

    def test_window_resets(self):
        limiter = server.RateLimiter(limit=1, window_s=60)
        self.assertTrue(limiter.allow("a", now=0))
        self.assertFalse(limiter.allow("a", now=30))
        self.assertTrue(limiter.allow("a", now=61))

    def test_forwarded_address_is_used_behind_a_proxy(self):
        self.assertEqual(server.client_key({"X-Forwarded-For": "203.0.113.5, 10.0.0.1"}, "10.9.9.9"), "203.0.113.5")
        self.assertEqual(server.client_key({}, "127.0.0.1"), "127.0.0.1")


class HttpBehaviour(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved = (server.DEV_MODE, server.CAREGIVER_TOKEN, server.STORE,
                     server.READ_LIMITER, server.WEBHOOK_LIMITER)
        server.DEV_MODE = False
        server.CAREGIVER_TOKEN = TOKEN
        server.STORE = EventStore(":memory:")
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        server.DEV_MODE, server.CAREGIVER_TOKEN, server.STORE, server.READ_LIMITER, server.WEBHOOK_LIMITER = cls.saved

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        return resp.status, data

    def test_status_is_rate_limited_with_429(self):
        server.READ_LIMITER = server.RateLimiter(limit=2)
        auth = {"Authorization": f"Bearer {TOKEN}"}
        codes = [self.request("GET", "/api/status", headers=auth)[0] for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])

    def test_events_limit_must_be_a_number(self):
        server.READ_LIMITER = server.RateLimiter(limit=100)
        code, _ = self.request("GET", "/api/events?limit=abc", headers={"Authorization": f"Bearer {TOKEN}"})
        self.assertEqual(code, 400)

    def test_webhook_logs_status_without_room_or_device_names(self):
        server.WEBHOOK_LIMITER = server.RateLimiter(limit=100)
        body = json.dumps({
            "meta": {"time": "2026-10-22T09:00:00+05:30"},
            "data": {"id": "evt_log_1", "type": "motion_detected",
                     "attributes": {"source": "sim.kitchen"}},
        }).encode()
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            code, _ = self.request("POST", "/api/ring/webhook", body=body,
                                   headers={"X-Signature": server.sign(body)})
        self.assertEqual(code, 200)
        lines = [json.loads(line) for line in buf.getvalue().splitlines() if line.startswith("{")]
        webhook_lines = [l for l in lines if l["event"] == "webhook"]
        self.assertEqual(webhook_lines[-1]["status"], 200)
        self.assertNotIn("kitchen", buf.getvalue())
        self.assertNotIn("sim.", buf.getvalue())
        self.assertNotIn("evt_log_1", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
