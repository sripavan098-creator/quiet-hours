"""Quiet Hours backend (standard library only).

Routes
------
GET  /                     single-page UI
GET  /healthz              liveness
GET  /api/status           household status as of now (or the demo clock)
GET  /api/events?limit=n   newest-first event feed
POST /api/ring/webhook     Ring webhook intake: X-Signature (HMAC-SHA256 of the raw body)
POST /api/sim/demo         load a simulated scenario as signed Ring-shaped webhooks

Response codes follow Ring's delivery rules: 2xx = delivered, 4xx = permanent
failure (no retry), 5xx = retry. A bad signature is 401 and a malformed
payload is 400, so Ring does not retry either.

Environment
-----------
RING_WEBHOOK_SECRET   HMAC key from the Ring Developer Portal (default: dev-only value)
RING_DEVICE_ZONES     JSON map {ring_device_id: zone}, e.g. {"ava1.ring.device.abc": "kitchen"}
PORT                  listen port (default 8080)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import analysis
import ring_adapter
import sim

STATIC_DIR = Path(__file__).parent / "static"
SIGNATURE_HEADER = "X-Signature"
WEBHOOK_SECRET = os.environ.get("RING_WEBHOOK_SECRET", "dev-only-change-me").encode()

# Simulated devices use ids like "sim.kitchen"; real ones come from RING_DEVICE_ZONES.
ZONE_MAP = {f"sim.{z}": z for z in analysis.ZONE_IDS}
ZONE_MAP.update(ring_adapter.load_zone_map())

_lock = threading.Lock()
_events: dict[str, dict] = {}      # event_id -> internal event (dedupe on id)
_demo_now: datetime | None = None  # set when a demo scenario is loaded


def sign(body: bytes, secret: bytes = WEBHOOK_SECRET) -> str:
    """Header value Ring sends: 'sha256=' + hex HMAC-SHA256 of the raw body."""
    return "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()


def verify_signature(body: bytes, header_value: str | None) -> bool:
    if not header_value:
        return False
    return hmac.compare_digest(header_value.strip(), sign(body))


def handle_webhook(raw: bytes, signature_header: str | None) -> tuple[int, dict]:
    """The one webhook path: verify, normalise, store. Used by HTTP and the demo."""
    if not verify_signature(raw, signature_header):
        return 401, {"error": "bad signature"}
    try:
        payload = json.loads(raw or b"{}")
        events = ring_adapter.normalise(payload, ZONE_MAP)
    except (json.JSONDecodeError, ring_adapter.PayloadError) as exc:
        return 400, {"error": str(exc)}
    added = ingest(events)
    return 200, {"accepted": added, "status": current_status()}


def ingest(events: list[dict]) -> int:
    added = 0
    with _lock:
        for ev in events:
            if ev["event_id"] in _events:
                continue
            _events[ev["event_id"]] = ev
            added += 1
    return added


def _event_tuples() -> list[tuple[str, datetime]]:
    with _lock:
        return [(ev["device_id"], datetime.fromisoformat(ev["created_at"])) for ev in _events.values()]


def current_status(now: datetime | None = None) -> dict:
    if now is None:
        now = _demo_now or datetime.now(sim.IST)
    return analysis.assess(_event_tuples(), now)


def recent_events(limit: int = 30) -> list[dict]:
    with _lock:
        items = sorted(_events.values(), key=lambda e: e["created_at"], reverse=True)
    return items[:limit]


def load_demo(scenario: str) -> dict:
    global _demo_now
    today = datetime.now(sim.IST).date()
    events, now = sim.generate(scenario, today)
    with _lock:
        _events.clear()
        _demo_now = now
    for internal in events:
        body = json.dumps(ring_adapter.to_ring_payload(internal)).encode()
        code, res = handle_webhook(body, sign(body))
        if code != 200:
            raise RuntimeError(f"demo webhook rejected: {res}")
    return current_status()


class Handler(BaseHTTPRequestHandler):
    server_version = "QuietHours/0.2"

    def log_message(self, fmt, *args):
        pass

    def _send(self, code: int, payload, content_type="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(length) if length else b""

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            return self._send(200, (STATIC_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
        if url.path == "/healthz":
            return self._send(200, {"ok": True})
        if url.path == "/api/status":
            return self._send(200, current_status())
        if url.path == "/api/events":
            limit = min(int(parse_qs(url.query).get("limit", ["30"])[0]), 200)
            return self._send(200, {"events": recent_events(limit)})
        return self._send(404, {"error": "not found"})

    def do_POST(self):
        url = urlparse(self.path)
        if url.path == "/api/ring/webhook":
            code, res = handle_webhook(self._body(), self.headers.get(SIGNATURE_HEADER))
            return self._send(code, res)
        if url.path == "/api/sim/demo":
            try:
                scenario = json.loads(self._body() or b"{}").get("scenario", "normal")
                status = load_demo(scenario)
            except (ValueError, RuntimeError) as exc:
                return self._send(400, {"error": str(exc)})
            return self._send(200, status)
        return self._send(404, {"error": "not found"})


def main():
    port = int(os.environ.get("PORT", "8080"))
    print(f"Quiet Hours listening on http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
