# Architecture: Quiet Hours

## Overview

Quiet Hours is one Python process with a standard-library HTTP server, an in-memory event store, pure rule logic, and a single static page. It has no third-party runtime dependencies.

```
                   ┌──────────────────────────────────────────┐
Ring cloud ──────► │ POST /api/ring/webhook                    │
  (signed POST)    │   verify X-Signature (HMAC-SHA256)        │
                   │   ring_adapter.normalise()                 │
                   │   event store (dict, keyed by event id)    │
                   │                                            │
Caregiver ◄──────  │ GET /api/status ── analysis.assess()       │
  browser          │ GET /api/events                            │
                   │ GET / ── static/index.html                 │
                   │                                            │
Developer ───────► │ POST /api/sim/demo ── sim.generate()       │
                   └──────────────────────────────────────────┘
                                   │
                                   ▼ (outbound, in ring_client.py)
                        oauth.ring.com  ·  api.amazonvision.com
```

## Components

| Module | Responsibility | Depends on |
|---|---|---|
| `server.py` | HTTP routing, webhook handling, demo loader, store | `analysis`, `ring_adapter`, `sim` |
| `ring_adapter.py` | Converts Ring payloads to internal events; enforces the documented payload shape | none |
| `analysis.py` | Rules R1–R3; no I/O, no clock reads | none |
| `sim.py` | Generates Ring-shaped household events for two scenarios | none |
| `ring_client.py` | OAuth token exchange and refresh; device list; history pass-through | `urllib` |
| `static/index.html` | Renders the house, alerts and signals; polls `/api/status` | browser APIs |

`analysis.py` takes events and a clock as arguments. This is why every rule is testable and the demo is repeatable.

## Data flow: webhook

1. Ring sends `POST /api/ring/webhook` with a JSON body and `X-Signature: sha256=<hex>`.
2. The server computes HMAC-SHA256 over the raw body with `RING_WEBHOOK_SECRET` and compares it in constant time.
   - Mismatch or missing header: **401**, not retried by Ring.
3. The body is parsed and normalised. Malformed payloads: **400**, not retried.
4. Unmapped devices and unknown types are dropped and return **200** with `accepted: 0`. Ring marks these as delivered.
5. New events are stored by `event_id`. A repeated event is ignored, so Ring's retries are safe.
6. The response includes the current status. Responses should complete in well under 5 seconds, since slower responses count as failures and are retried.

## Data flow: status

1. The browser polls `GET /api/status` every 4 seconds.
2. The server calls `analysis.assess(events, now)`.
3. `now` is the demo clock if a demo is loaded, otherwise the current IST time.
4. The response carries home status, per-room status, alerts and key facts.

## Rule engine

| Input | Rule | Output |
|---|---|---|
| Interior events (kitchen, bathroom, bedroom) | Silence since last movement vs threshold | Home status |
| Front door events | Usual before 12:00, missing today | Alert |
| Kitchen activity | Usual before 10:00, missing today | Alert |

Rules only run between 07:00 and 22:00 local time. The threshold is `max(3 h, 3 × median daytime gap over 7 days)`, falling back to 3 h with fewer than 5 gaps.

## Data model

Events are held as internal dictionaries:

| Field | Type | Source |
|---|---|---|
| `event_id` | string | Ring `data.id` |
| `device_id` | room id | Mapped from Ring `data.attributes.source` |
| `ring_device_id` | string | Ring `data.attributes.source` |
| `kind` | string | Mapped from Ring `data.type` (or simulator type) |
| `ring_type` | string | Ring `data.type` |
| `created_at` | ISO 8601 with offset | Ring `meta.time` |
| `source` | `ring` or `simulator` | Set by adapter |

See `DATA.md` for the storage plan.

## Timezone handling (known issue)

Events keep the offset they arrived with. The day boundary and the "hour of event" checks currently read the hour in each event's own offset. Ring's times may come with a different offset than IST. Gate 1.4 in the roadmap converts everything to IST at normalisation. Until then, the rules are correct only for events already in IST, which is the simulator's behaviour.

## Concurrency

- The store is guarded by one lock. Webhook writes and status reads are short, so contention is negligible at home scale.
- `ThreadingHTTPServer` handles requests concurrently.
- `_demo_now` is a module global, written only by the demo loader under the same lock.

## Failure modes

| Failure | Behaviour |
|---|---|
| Missing or wrong signature | 401; no state change |
| Malformed payload | 400; no state change |
| Ring API token expired | `ring_client` refreshes once on 401, then raises |
| Process restart | Store is empty; events are lost (v1.0, see Gate 5.1) |
| Browser cannot reach server | Page shows "cannot reach the house right now" and retries |

## Scaling and limits

Designed for one home per process. Memory grows with events; at one motion event every minute that is roughly 1,500 events a day, which the in-memory store handles easily. Multi-home support would need persistence, per-home keys and a separate caregiver identity model. Those are out of scope for v1.0.

## Deployment shape

Single process on a small host behind HTTPS. See `DEPLOYMENT.md`.

## Decisions

| Decision | Reason | Alternative considered |
|---|---|---|
| Standard library only | Easy to review and run; no supply-chain surface | Flask or FastAPI (more features, more dependencies) |
| In-memory store | Hackathon scope; simple to test | SQLite (planned in Gate 5.1) |
| Pure rules module | Testable; deterministic demo | Rules inside the server (harder to test) |
| Simulator uses the webhook path | Exercises real verification and normalisation | Direct store writes (faster, but skips the path judges care about) |
| Polling, not push | Simple; adequate for a status page | WebSocket or server-sent events (later) |


## Storage and operations (Gate 5)

- `app/store.py` holds the SQLite event store. It uses the standard library `sqlite3` module, so no runtime dependency is added.
- Logging writes one JSON line per webhook outcome and per refused request, to stderr. It records status codes and counts only: no room names, device IDs, addresses or event contents.
- Rate limits are in memory per process. With more than one process, each process counts separately, so run one process on the free tier.
