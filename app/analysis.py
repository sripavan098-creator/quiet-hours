"""Routine baseline and alert logic for Quiet Hours.

Pure functions only: no I/O, no clocks. Callers pass in events and "now",
which keeps every rule testable and the demo deterministic.

Signals
-------
* Home silence: time since the last interior motion (kitchen, bathroom,
  bedroom). The threshold adapts to each home: at least MIN_SILENCE, or
  SILENCE_FACTOR times the median daytime gap between movements, whichever is
  longer. A quiet morning is only worrying relative to that home's own rhythm.
* Missed routine: the front door (errand) or the medicine box is usually
  touched before a check hour, but today nothing has happened by then.

Only daytime (DAY_START_H..DAY_END_H local hours) is judged, so night-time
stillness is never treated as an emergency.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median

# zone_id, display name, is_interior (counts toward home silence)
ZONES = [
    ("kitchen", "Kitchen", True),
    ("bathroom", "Bathroom", True),
    ("bedroom", "Bedroom", True),
    ("front_door", "Front door", False),
    ("medicine", "Medicine box", False),
]
ZONE_IDS = {z for z, _, _ in ZONES}
INTERIOR = {z for z, _, i in ZONES if i}

DAY_START_H = 7
DAY_END_H = 22
MIN_SILENCE = timedelta(hours=3)
SILENCE_FACTOR = 3.0
MIN_GAP_SAMPLES = 5
LOOKBACK_DAYS = 7
MIN_HISTORY_DAYS = 4

# (zone, check hour, plain-language label). If the usual touch has not
# happened by this hour, the routine check fires.
ROUTINE_CHECKS = [
    ("front_door", 12, "Usual morning errand has not happened"),
    ("medicine", 10, "Morning medicine check not logged"),
]


def is_daytime(dt: datetime) -> bool:
    return DAY_START_H <= dt.hour < DAY_END_H


def _day_start(dt: datetime) -> datetime:
    return dt.replace(hour=DAY_START_H, minute=0, second=0, microsecond=0)


def _fmt_duration(td: timedelta) -> str:
    minutes = int(td.total_seconds() // 60)
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}h {m:02d}m"
    if h:
        return f"{h}h"
    return f"{m}m"


def _daytime_gaps(times: list[datetime]) -> list[timedelta]:
    day = [t for t in times if is_daytime(t)]
    return [b - a for a, b in zip(day, day[1:]) if a.date() == b.date()]


def assess(
    events: list[tuple[str, datetime]],
    now: datetime,
    lookback_days: int = LOOKBACK_DAYS,
) -> dict:
    """Return the household status as of `now`.

    `events` is an iterable of (zone_id, created_at). Events after `now` are
    ignored so the same history can be replayed at any moment.
    """
    by_zone: dict[str, list[datetime]] = {z: [] for z, _, _ in ZONES}
    for zone, ts in events:
        if zone in by_zone and ts <= now:
            by_zone[zone].append(ts)
    for times in by_zone.values():
        times.sort()

    window_start = now - timedelta(days=lookback_days)
    history_days = {
        ts.date()
        for times in by_zone.values()
        for ts in times
        if window_start <= ts and ts.date() < now.date()
    }
    observed_days = len(history_days)
    alerts: list[dict] = []
    watch = False

    # ---- Home silence (interior stream combined) -------------------------
    interior_times = sorted(
        ts for z in INTERIOR for ts in by_zone[z]
    )
    interior_history = [t for t in interior_times if window_start <= t and t.date() < now.date()]
    gaps = _daytime_gaps(interior_history)
    baseline = median(gaps) if len(gaps) >= MIN_GAP_SAMPLES else None
    threshold = MIN_SILENCE
    if baseline is not None:
        threshold = max(MIN_SILENCE, baseline * SILENCE_FACTOR)

    last_interior = interior_times[-1] if interior_times else None
    silence = None
    home_status = "resting"
    if is_daytime(now):
        anchor = max(last_interior, _day_start(now)) if last_interior else _day_start(now)
        silence = now - anchor
        if silence > threshold:
            home_status = "alert"
            alerts.append({
                "zone": "home",
                "severity": "alert",
                "message": (
                    f"No movement in the home for {_fmt_duration(silence)}. "
                    f"This home usually goes no longer than {_fmt_duration(threshold)} "
                    "during the day."
                ),
            })
        elif silence > threshold * 0.75:
            home_status = "watch"
            watch = True
        else:
            home_status = "ok"

    # ---- Routine checks (errand, medicine) ------------------------------
    routine_status: dict[str, str] = {}
    for zone, check_h, label in ROUTINE_CHECKS:
        times = by_zone[zone]
        today = [t for t in times if t.date() == now.date()]
        usual_days = {
            t.date()
            for t in times
            if window_start <= t and t.date() < now.date() and t.hour < check_h
        }
        usual = observed_days >= MIN_HISTORY_DAYS and len(usual_days) >= MIN_HISTORY_DAYS
        if usual and now.hour >= check_h and not today:
            routine_status[zone] = "alert"
            alerts.append({
                "zone": zone,
                "severity": "alert",
                "message": f"{label}. It usually happens before {check_h:02d}:00, "
                           f"on {len(usual_days)} of the last {observed_days} days.",
            })
        else:
            routine_status[zone] = "ok" if (not usual or today) else "pending"

    # ---- Per-zone view for the UI --------------------------------------
    zones_out = []
    for zone, name, interior in ZONES:
        times = by_zone[zone]
        last = times[-1] if times else None
        state = home_status if interior else routine_status.get(zone, "ok")
        zones_out.append({
            "id": zone,
            "name": name,
            "interior": interior,
            "last_seen": last.isoformat() if last else None,
            "events_today": sum(1 for t in times if t.date() == now.date()),
            "state": state,
        })

    if alerts:
        overall = "alert"
    elif watch:
        overall = "watch"
    else:
        overall = "ok"

    return {
        "now": now.isoformat(),
        "state": overall,
        "is_daytime": is_daytime(now),
        "observed_days": observed_days,
        "home": {
            "last_movement": last_interior.isoformat() if last_interior else None,
            "silence_minutes": int(silence.total_seconds() // 60) if silence is not None else None,
            "threshold_minutes": int(threshold.total_seconds() // 60),
            "baseline_gap_minutes": int(baseline.total_seconds() // 60) if baseline is not None else None,
        },
        "zones": zones_out,
        "alerts": alerts,
    }
