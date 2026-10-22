# Quiet Hours

A caretaker's view of an ordinary home, built on Ring-style device events.

Quiet Hours watches the rhythm of a home (kitchen, bathroom and bedroom movement, the front door) and tells a remote family member or caregiver when that rhythm breaks. It never shows live video. It learns what "normal" looks like for each home and raises a calm alert only when a day falls out of step, for example:

- No movement in the home for longer than this household usually goes during the day.
- The usual morning errand or kitchen activity has not happened by the hour it normally does.

Night-time stillness is never treated as an alarm.

Built for the Amazon Developer Hackathon, Ring track (caretaking and accessibility).

## Quick start

Requires Python 3.9+. No third-party packages.

```bash
cd quiet-hours
python3 -m unittest discover -s tests -v   # 66 tests
cd app && python3 server.py                # http://localhost:8080
```

Open the page and press **Ordinary day** or **Simulate a collapse**. The simulated collapse stops movement at 09:40 and shows the alert by 14:30.

For a real Ring account, set the webhook key and map each Ring device to a room:

```bash
export RING_WEBHOOK_SECRET="the-signing-key-from-the-developer-portal"
export RING_DEVICE_ZONES='{"ava1.ring.device.<id>": "kitchen", "ava1.ring.device.<id2>": "front_door"}'
```

Valid rooms are `kitchen`, `bathroom`, `bedroom` and `front_door`.

## How it works

```
Ring webhook  ──► POST /api/ring/webhook  ──► HMAC-SHA256 check ──► event store
                                                                       │
browser ◄── GET /api/status ◄── analysis.assess(events, now) ◄─────────┘
```

- `app/analysis.py` is pure logic with no I/O. It takes events and a clock and returns a status, so every rule is unit-tested and the demo is deterministic.
  - **Home silence:** the threshold is the longer of 3 hours or 3× the median daytime gap between movements in the last 7 days. A home that normally moves every ten minutes gets a tighter threshold than one that moves hourly, but never less than 3 hours.
  - **Routine checks:** the front door (by 12:00) and the kitchen (by 10:00) only alert when the home has at least 4 days of history showing that rhythm.
  - Only 07:00–22:00 local time is judged.
- `app/sim.py` generates Ring-shaped events (`event_id`, `device_id`, `created_at`, `kind`). Every record is tagged `"source": "simulator"`.
- `app/server.py` is a standard-library HTTP server. Demo data goes through the same signed webhook path as real events, so the verification code is exercised end to end.
- `app/static/index.html` is one file with no build step. A beam sweeps a floor plan of the home: rooms glow when they are active, and a room turns coral only when its rhythm breaks.

## What is real and what is not

| Part | Status |
|---|---|
| Event store, routine analysis, alert rules | Working, tested (66 tests) |
| Webhook intake | Working against the documented shape: `X-Signature: sha256=<hex HMAC of the raw body>`, payload `{meta, data}`, event type in `data.type`, device in `data.attributes.source`, time in `meta.time`. Responses follow Ring's rules: 401 bad signature, 400 malformed, both not retried. |
| Device-to-room mapping | `RING_DEVICE_ZONES` (env). Setup UI for it is not built. |
| Partner API client | Token exchange, refresh-on-401, and `GET /v1/devices` are implemented and unit-tested with a fake transport. **Not run against live Ring.** |
| Event history | `device_events()` passes query options through. The query parameters were not readable in the docs fetched, so the call is unverified. |
| Medicine box | Ring's documented webhook types have no contact-sensor event. The simulator sends a `contact_open` event, but real devices are not accepted for it. This signal needs confirmation, or a different approach, before the medicine check works on a real home. |
| Real Ring device or Playground test | **Not yet run.** The demo uses the built-in simulator. |

Ring's documented webhook retry behaviour: 2xx is delivered, 4xx is not retried, 5xx is retried with backoff, and responses slower than 5 seconds count as 5xx.

Quiet Hours does not replace emergency services. The UI says so.

## Project layout

```
app/
  analysis.py      routine baseline and alert rules (pure)
  ring_adapter.py  Ring webhook payload <-> internal event shape
  ring_client.py   Partner API client: OAuth token exchange, devices, history
  sim.py           Ring-shaped household simulator
  server.py        HTTP server, signed webhook intake, demo loader
  static/index.html
tests/
  test_analysis.py
  test_webhook.py
```

## Licence

MIT. See `LICENSE`.
