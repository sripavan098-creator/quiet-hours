"""SQLite event store (Python standard library).

Events are stored once per event_id, so a repeated webhook is ignored (Ring
retries are safe). Data survives a restart when the database file is on
persistent storage. Use ":memory:" for tests and the demo.

Retention is relative to the newest stored event, not the wall clock, so
the store behaves the same no matter when it runs.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta

RETENTION = timedelta(days=14)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id      TEXT PRIMARY KEY,
    device_id     TEXT NOT NULL,
    ring_device_id TEXT,
    kind          TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    source        TEXT NOT NULL,
    data          TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS events_created ON events (created_at);
"""


class EventStore:
    def __init__(self, path: str = ":memory:"):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(_SCHEMA)
        self._db.commit()

    def __del__(self):
        try:
            self._db.close()
        except Exception:  # best effort on interpreter shutdown
            pass

    def add(self, events: list[dict]) -> int:
        """Store events, ignoring ids already present. Returns the number added."""
        added = 0
        with self._lock:
            for ev in events:
                cur = self._db.execute(
                    "INSERT OR IGNORE INTO events "
                    "(event_id, device_id, ring_device_id, kind, created_at, source, data) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        ev["event_id"],
                        ev["device_id"] or "",
                        ev.get("ring_device_id"),
                        ev["kind"],
                        ev["created_at"],
                        ev["source"],
                        json.dumps(ev),
                    ),
                )
                added += cur.rowcount
            self._db.commit()
        self._prune()
        return added

    def _prune(self) -> None:
        with self._lock:
            row = self._db.execute("SELECT MAX(created_at) FROM events").fetchone()
            if not row or row[0] is None:
                return
            newest = datetime.fromisoformat(row[0])
            cutoff = (newest - RETENTION).isoformat()
            self._db.execute("DELETE FROM events WHERE created_at < ?", (cutoff,))
            self._db.commit()

    def all(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT data FROM events").fetchall()
        return [json.loads(r[0]) for r in rows]

    def recent(self, limit: int) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT data FROM events ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def newest_created_at(self) -> datetime | None:
        with self._lock:
            row = self._db.execute("SELECT MAX(created_at) FROM events").fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None

    def remap(self, ring_id: str, room: str) -> None:
        """Re-label stored events for one Ring device. An empty room unmaps them."""
        with self._lock:
            rows = self._db.execute(
                "SELECT event_id, data FROM events WHERE ring_device_id = ?", (ring_id,)
            ).fetchall()
            for event_id, raw in rows:
                ev = json.loads(raw)
                ev["device_id"] = room
                self._db.execute(
                    "UPDATE events SET device_id = ?, data = ? WHERE event_id = ?",
                    (room, json.dumps(ev), event_id),
                )
            self._db.commit()

    def clear(self) -> None:
        with self._lock:
            self._db.execute("DELETE FROM events")
            self._db.commit()

    def ping(self) -> bool:
        """Readiness check: can the database answer a query?"""
        try:
            with self._lock:
                self._db.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False
