"""Quiet Hours backend (standard library only).

Routes
------
GET  /                       single-page UI (open)
GET  /healthz                liveness (open)
GET  /api/status             household status (caregiver token)
GET  /api/events?limit=n     newest-first event feed (caregiver token)
GET  /api/devices            mapped devices, dev mode only (caregiver token)
PUT  /api/devices/{id}/room  map a device to a room, dev mode only (caregiver token)
POST /api/ring/webhook       Ring webhook intake, X-Signature (HMAC-SHA256 of the raw body)
POST /api/sim/demo           simulated scenario, dev mode only

Response codes follow Ring's delivery rules: 2xx = delivered, 4xx = permanent
failure (no retry), 5xx = retry. A bad signature is 401 and a malformed
payload is 400, so Ring does not retry either. Bodies over 64 KB get 413.

Environment
-----------
QH_ENV                 "dev" enables demo and device endpoints and allows defaults
RING_WEBHOOK_SECRET    HMAC key from the Ring Developer Portal (required outside dev)
QH_CAREGIVER_TOKEN     bearer token for caregiver endpoints (required outside dev, 16+ chars)
RING_DEVICE_ZONES      JSON map {ring_device_id: zone}
PORT                   listen port (default 8080)
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Mapping
from urllib.parse import parse_qs, unquote, urlparse

import analysis
import ring_adapter
import sim

STATIC_DIR = Path(__file__).parent / "static"
SIGNATURE_HEADER = "X-Signature"
MAX_BODY_BYTES = 64 * 1024
MIN_TOKEN_LEN = 16
DEV_DEFAULT_SECRET = b"dev-only-change-me"

DEV_MODE = os.environ.get("QH_ENV") == "dev"
WEBHOOK_SECRET = os.environ.get("RING_WEBHOOK_SECRET", DEV_DEFAULT_SECRET.decode()).encode()
CAREGIVER_TOKEN = os.environ.get("QH_CAREGIVER_TOKEN", "")
DEVICE_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,120}$")

# Simulated devices use ids like "sim.kitchen"; real ones come from RING_DEVICE_ZONES.
ZONE_MAP = {f"sim.{z}": z for z in analysis.ZONE_IDS}
ZONE_MAP.update(ring_adapter.load_zone_map())

_lock = threading.Lock()
_events: dict[str, dict] = {}      # event_id -> internal event (dedupe on id)
_demo_now: datetime | None = None  # set when a demo scenario is loaded


def config_problems(env: Mapping[str, str]) -> list[str]:
    """Reasons the server must not start. Empty list means safe to start."""
    if env.get("QH_ENV") == "dev":
        return []
    problems = []
    if not env.get("RING_WEBHOOK_SECRET"):
        problems.append("RING_WEBHOOK_SECRET is required outside QH_ENV=dev")
    token = env.get("QH_CAREGIVER_TOKEN", "")
    if len(token) < MIN_TOKEN_LEN:
        problems.append(f"QH_CAREGIVER_TOKEN is required outside QH_ENV=dev and must be at least {MIN_TOKEN_LEN} characters")
    return problems


def sign(body: bytes, secret: bytes = WEBHOOK_SECRET) -> str:
    """Header value Ring sends: 'sha256=' + hex HMAC-SHA256 of the raw body."""
    return "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()


def verify_signature(body: bytes, header_value: str | None) -> bool:
    if not header_value:
        return False
    return hmac.compare_digest(header_value.strip(), sign(body))


def caregiver_authorised(header_value: str | None) -> bool:
    """Bearer check. With no token configured, only dev mode is open."""
    if not CAREGIVER_TOKEN:
        return DEV_MODE
    if not header_value or not header_value.startswith("Bearer "):
        return False
    return hmac.compare_digest(header_value[len("Bearer "):].strip(), CAREGIVER_TOKEN)


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
        now = _demo_now or datetime.now(analysis.IST)
    return analysis.assess(_event_tuples(), now)


def recent_events(limit: int = 30) -> list[dict]:
    with _lock:
        items = sorted(_events.values(), key=lambda e: e["created_at"], reverse=True)
    return items[:limit]


def list_devices() -> dict:
    """Mapped devices and the room options. Ring discovery arrives with Gate 2.3."""
    with _lock:
        mapping = dict(ZONE_MAP)
    devices = []
    for ring_id, room in sorted(mapping.items()):
        is_sim = ring_id.startswith("sim.")
        devices.append({
            "id": ring_id,
            "room": room,
            "name": sim.DEVICE_NAMES.get(room, room) if is_sim else f"Ring device {ring_id[-6:]}",
            "source": "simulator" if is_sim else "ring",
        })
    return {"rooms": sorted(analysis.ZONE_IDS), "devices": devices}


def set_device_room(ring_id: str, room: str) -> None:
    """Map a device to a room (or unmap with ""). Re-labels stored events for that device.

    Unmapped events keep their record but get an empty room, so the rules ignore them.
    """
    with _lock:
        if room:
            ZONE_MAP[ring_id] = room
        else:
            ZONE_MAP.pop(ring_id, None)
        for ev in _events.values():
            if ev.get("ring_device_id") == ring_id:
                ev["device_id"] = room


def load_demo(scenario: str) -> dict:
    global _demo_now
    today = datetime.now(analysis.IST).date()
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
    server_version = "QuietHours/0.3"

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

    def _declared_length(self) -> int:
        try:
            return int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return -1

    def _too_large(self) -> bool:
        """Refuse oversized bodies before reading them. Returns True if refused."""
        if self._declared_length() > MAX_BODY_BYTES:
            self.close_connection = True
            self._send(413, {"error": f"body exceeds {MAX_BODY_BYTES} bytes"})
            return True
        return False

    def _body(self) -> bytes:
        length = max(self._declared_length(), 0)
        return self.rfile.read(length) if length else b""

    def _guard(self) -> bool:
        """Send 401 and return False unless the caregiver token is valid."""
        if caregiver_authorised(self.headers.get("Authorization")):
            return True
        self._send(401, {"error": "caregiver sign-in required"})
        return False

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/":
            return self._send(200, (STATIC_DIR / "index.html").read_bytes(), "text/html; charset=utf-8")
        if url.path == "/healthz":
            return self._send(200, {"ok": True})
        if url.path == "/api/status":
            if not self._guard():
                return
            return self._send(200, current_status())
        if url.path == "/api/events":
            if not self._guard():
                return
            limit = min(int(parse_qs(url.query).get("limit", ["30"])[0]), 200)
            return self._send(200, {"events": recent_events(limit)})
        if url.path == "/api/devices":
            if not DEV_MODE:
                return self._send(404, {"error": "not found"})
            if not self._guard():
                return
            return self._send(200, list_devices())
        return self._send(404, {"error": "not found"})

    def do_PUT(self):
        if self._too_large():
            return
        parts = urlparse(self.path).path.split("/")  # ['', 'api', 'devices', <id>, 'room']
        if not DEV_MODE or len(parts) != 5 or parts[1:3] != ["api", "devices"] or parts[4] != "room":
            return self._send(404, {"error": "not found"})
        if not self._guard():
            return
        ring_id = unquote(parts[3])
        if not DEVICE_ID_RE.match(ring_id):
            return self._send(400, {"error": "invalid device id"})
        try:
            body = json.loads(self._body() or b"{}")
        except json.JSONDecodeError:
            return self._send(400, {"error": "invalid json"})
        room = body.get("room") if isinstance(body, dict) else None
        if not isinstance(room, str) or (room and room not in analysis.ZONE_IDS):
            return self._send(400, {"error": f"room must be one of {sorted(analysis.ZONE_IDS)} or empty"})
        set_device_room(ring_id, room)
        return self._send(200, list_devices())

    def do_POST(self):
        if self._too_large():
            return
        url = urlparse(self.path)
        if url.path == "/api/ring/webhook":
            code, res = handle_webhook(self._body(), self.headers.get(SIGNATURE_HEADER))
            return self._send(code, res)
        if url.path == "/api/sim/demo":
            if not DEV_MODE:
                return self._send(404, {"error": "not found"})
            try:
                scenario = json.loads(self._body() or b"{}").get("scenario", "normal")
                status = load_demo(scenario)
            except (ValueError, RuntimeError) as exc:
                return self._send(400, {"error": str(exc)})
            return self._send(200, status)
        return self._send(404, {"error": "not found"})


def main():
    problems = config_problems(os.environ)
    if problems:
        for p in problems:
            print(f"Refusing to start: {p}", file=sys.stderr)
        sys.exit(2)
    if DEV_MODE:
        print("Running in development mode: demo and device endpoints are enabled.")
    port = int(os.environ.get("PORT", "8080"))
    print(f"Quiet Hours listening on http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
