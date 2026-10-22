import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(ROOT))

import analysis  # noqa: E402
import sim  # noqa: E402


def ist(y, mo, d, h, m=0):
    return datetime(y, mo, d, h, m, tzinfo=sim.IST)


class SimulatorScenarios(unittest.TestCase):
    def test_normal_day_is_ok(self):
        events, now = sim.generate("normal", date(2026, 10, 21))
        status = analysis.assess([(e["device_id"], datetime.fromisoformat(e["created_at"])) for e in events], now)
        self.assertEqual(status["state"], "ok", status["alerts"])

    def test_collapse_raises_alert(self):
        events, now = sim.generate("collapse", date(2026, 10, 21))
        status = analysis.assess([(e["device_id"], datetime.fromisoformat(e["created_at"])) for e in events], now)
        self.assertEqual(status["state"], "alert")
        zones = {a["zone"] for a in status["alerts"]}
        self.assertIn("home", zones)
        self.assertIn("front_door", zones)
        self.assertNotIn("medicine", zones)  # medicine was logged this morning

    def test_simulator_marks_source(self):
        events, _ = sim.generate("normal", date(2026, 10, 21))
        self.assertTrue(all(e["source"] == "simulator" for e in events))
        self.assertTrue(all(e["event_id"].startswith("evt_") for e in events))


class SilenceRules(unittest.TestCase):
    def history(self, days=7):
        # Each past day: a motion cluster every hour from 08:00 to 20:00.
        out = []
        base = date(2026, 10, 14)
        for d in range(days):
            day = base + timedelta(days=d)
            for h in range(8, 21):
                out.append(("kitchen", ist(day.year, day.month, day.day, h, 0)))
        return out

    def test_night_silence_is_never_an_alert(self):
        now = ist(2026, 10, 21, 3, 0)
        status = analysis.assess(self.history(), now)
        self.assertEqual(status["state"], "ok")
        self.assertFalse(status["is_daytime"])

    def test_daytime_silence_over_threshold_alerts(self):
        events = self.history() + [("kitchen", ist(2026, 10, 21, 9, 0))]
        status = analysis.assess(events, ist(2026, 10, 21, 13, 30))
        self.assertEqual(status["state"], "alert")
        self.assertEqual(status["home"]["silence_minutes"], 270)

    def test_silence_just_under_threshold_is_watch_or_ok(self):
        events = self.history() + [("kitchen", ist(2026, 10, 21, 9, 0))]
        status = analysis.assess(events, ist(2026, 10, 21, 11, 30))
        self.assertIn(status["state"], {"ok", "watch"})

    def test_routine_check_needs_history(self):
        # Only two days of history: the errand check must stay silent.
        events = [("front_door", ist(2026, 10, 19, 10, 30)), ("front_door", ist(2026, 10, 20, 10, 30))]
        status = analysis.assess(events, ist(2026, 10, 21, 13, 0))
        self.assertFalse([a for a in status["alerts"] if a["zone"] == "front_door"])

    def test_future_events_are_ignored(self):
        events = self.history() + [("kitchen", ist(2026, 10, 21, 23, 0))]
        status = analysis.assess(events, ist(2026, 10, 21, 13, 30))
        # The 23:00 event is after "now" and must not count as movement;
        # the last real movement is yesterday's 20:00 history event.
        self.assertEqual(status["home"]["last_movement"], ist(2026, 10, 20, 20, 0).isoformat())


if __name__ == "__main__":
    unittest.main()
