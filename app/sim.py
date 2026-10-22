"""Ring-shaped household simulator.

Produces events in the same shape the Ring simulator and webhooks use
(snake_case keys, ISO 8601 created_at, device_id, event_id) so the backend
never needs a fork for simulated versus real data. Every record carries
"source": "simulator" so simulated events cannot be mistaken for real ones.
"""
from __future__ import annotations

import random
import uuid
from datetime import date, datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

DEVICE_NAMES = {
    "kitchen": "Kitchen",
    "bathroom": "Bathroom",
    "bedroom": "Bedroom",
    "front_door": "Front door",
}

DEMO_NOW_TIME = (14, 30)
COLLAPSE_SILENCE_FROM = (9, 40)


def _event(zone: str, kind: str, when: datetime) -> dict:
    return {
        "event_id": f"evt_{uuid.uuid4().hex[:12]}",
        "device_id": zone,
        "device_name": DEVICE_NAMES[zone],
        "kind": kind,
        "created_at": when.isoformat(),
        "source": "simulator",
    }


def _at(day: date, h: int, m: int, rng: random.Random, spread: int = 0) -> datetime:
    base = datetime(day.year, day.month, day.day, h, m, tzinfo=IST)
    if spread:
        base += timedelta(minutes=rng.uniform(-spread, spread))
    return base.replace(microsecond=0)


def routine_day(day: date, rng: random.Random) -> list[dict]:
    """One ordinary day: morning, midday and evening movement, and the errand."""
    evts = []
    for k in range(3):
        evts.append(_event("kitchen", "motion", _at(day, 7, 10 + k * 8, rng)))
    evts.append(_event("bathroom", "motion", _at(day, 7, 25, rng)))
    evts.append(_event("bedroom", "motion", _at(day, 6, 55, rng)))
    for k in range(2):
        evts.append(_event("kitchen", "motion", _at(day, 12, 10 + k * 9, rng)))
    for k in range(3):
        evts.append(_event("kitchen", "motion", _at(day, 18, 30 + k * 7, rng)))
    evts.append(_event("bathroom", "motion", _at(day, 21, 30, rng)))
    evts.append(_event("bathroom", "motion", _at(day, 21, 41, rng)))
    evts.append(_event("bedroom", "motion", _at(day, 22, 20, rng)))
    evts.append(_event("front_door", "motion", _at(day, 10, 30, rng, spread=15)))
    return evts


def generate(scenario: str, today: date, seed: int = 7) -> tuple[list[dict], datetime]:
    """Build a week of history plus today up to the demo "now".

    scenario:
      "normal"   - ordinary day, everything usual; expect state "ok".
      "collapse" - movement stops at 09:40 today (no interior motion, no
                   errand). Expect state "alert" by 14:30.
    Returns (events, now) with `now` as an aware IST datetime.
    """
    if scenario not in {"normal", "collapse"}:
        raise ValueError(f"unknown scenario: {scenario}")
    rng = random.Random(seed)
    events: list[dict] = []

    for back in range(7, 0, -1):
        events.extend(routine_day(today - timedelta(days=back), rng))

    now = _at(today, *DEMO_NOW_TIME, rng)
    silence_from = None
    if scenario == "collapse":
        silence_from = _at(today, *COLLAPSE_SILENCE_FROM, rng)

    for ev in routine_day(today, rng):
        when = datetime.fromisoformat(ev["created_at"])
        if when > now:
            continue
        if silence_from and when >= silence_from:
            continue
        events.append(ev)

    return events, now
