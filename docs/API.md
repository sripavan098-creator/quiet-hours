# API: Quiet Hours

Base URL: `http://localhost:8080` in development. All responses are JSON except `/`, which returns HTML. All responses carry `Cache-Control: no-store`.

## Conventions

- Timestamps are ISO 8601 with an offset (IST, `+05:30`, in v1.0).
- Room identifiers: `kitchen`, `bathroom`, `bedroom`, `front_door`, `medicine`.
- Errors return `{"error": "<message>"}`.

## Endpoints

### `GET /`

Returns the single-page UI.

- **200** `text/html`

### `GET /healthz`

Liveness check.

- **200** `{"ok": true}`

### `GET /api/status`

Household status as of now. In demo mode, "now" is the demo clock.

- **200** response:

```json
{
  "now": "2026-10-22T14:30:00+05:30",
  "state": "ok | watch | alert",
  "is_daytime": true,
  "observed_days": 7,
  "home": {
    "last_movement": "2026-10-22T12:19:00+05:30",
    "silence_minutes": 131,
    "threshold_minutes": 180,
    "baseline_gap_minutes": 8
  },
  "zones": [
    {
      "id": "kitchen",
      "name": "Kitchen",
      "interior": true,
      "last_seen": "2026-10-22T12:19:00+05:30",
      "events_today": 5,
      "state": "ok | watch | alert | pending | resting"
    }
  ],
  "alerts": [
    {
      "zone": "home | front_door | medicine",
      "severity": "alert",
      "message": "Plain-language explanation"
    }
  ]
}
```

`baseline_gap_minutes` and `silence_minutes` may be `null` when there is not enough history or the time is outside daytime hours.

### `GET /api/events?limit=n`

Newest-first event feed. `limit` defaults to 30 and is capped at 200.

- **200** `{"events": [ ... ]}`

Each event:

```json
{
  "event_id": "evt_...",
  "device_id": "kitchen",
  "device_name": "Kitchen",
  "ring_device_id": "sim.kitchen",
  "kind": "motion",
  "ring_type": "motion_detected",
  "created_at": "2026-10-22T12:19:00+05:30",
  "source": "simulator | ring"
}
```

### `POST /api/ring/webhook`

Receives one Ring webhook per request.

**Request headers**

| Header | Required | Value |
|---|---|---|
| `Content-Type` | Yes | `application/json` |
| `X-Signature` | Yes | `sha256=<hex HMAC-SHA256 of the raw request body, keyed with RING_WEBHOOK_SECRET>` |

**Request body** (Ring's documented shape):

```json
{
  "meta": { "account_id": "ava1.ring.account.x", "time": "2026-10-22T09:00:00+05:30" },
  "data": {
    "id": "evt-123",
    "type": "motion_detected",
    "attributes": { "source": "ava1.ring.device.x", "sub_type": "human" },
    "relationships": { "devices": { "links": { "self": "/v1/devices/ava1.ring.device.x" } } }
  }
}
```

**Responses**

| Code | Meaning | Ring behaviour |
|---|---|---|
| 200 | Accepted (`accepted` is 1 for new, 0 for duplicate or unmapped) | Delivered; no retry |
| 400 | Malformed body, missing fields, or bad timestamp | Permanent failure; no retry |
| 401 | Missing or incorrect signature | Permanent failure; no retry |
| 5xx | Server error | Retried with backoff by Ring |

Ring retries up to six times with delays of 0 s, 1 s, 5 s, 30 s, 2 min, 10 min and 1 h. Responses slower than 5 seconds count as 5xx.

A 200 response:

```json
{ "accepted": 1, "status": { "...": "same shape as GET /api/status" } }
```

### `POST /api/sim/demo`

Loads a simulated scenario. It clears the event store and replays a week of history plus today through the signed webhook path.

**Request body**

```json
{ "scenario": "normal | collapse" }
```

| Scenario | Expected state at demo time |
|---|---|
| `normal` | `ok` |
| `collapse` | `alert` (home silence and front door) |

- **200** returns the status response.
- **400** `{"error": "unknown scenario: ..."}` for other values.

**Security:** this endpoint clears data and is not authenticated in v1.0. It must be disabled outside development (roadmap Gate 1.2).

## Planned endpoints (not yet implemented)

| Method and path | Purpose | Roadmap |
|---|---|---|
| `POST /api/auth/login` | Caregiver sign-in; returns a session token | Gate 1.3 |
| `GET /api/devices` | Lists Ring devices and room mapping | Gate 4.1 |
| `PUT /api/devices/{ring_device_id}/room` | Assigns a device to a room | Gate 4.1 |
| `GET /api/ring/link` | Starts OAuth account linking | Gate 2.2 |
| `GET /api/ring/callback` | OAuth redirect target | Gate 2.2 |

## Authentication (target state)

Gate 1.3 adds a bearer token for caregiver endpoints (`/api/status`, `/api/events`, `/api/devices`). The webhook uses its HMAC signature instead. The demo endpoint is removed from non-development builds.

## Rate limits (target state)

| Endpoint | Limit |
|---|---|
| `/api/ring/webhook` | Not rate-limited for Ring; body size capped at 64 KB |
| `/api/status`, `/api/events` | 60 requests per minute per caregiver (Gate 5.3) |

## Versioning

v1.0 has no version prefix. Breaking changes after the hackathon will move to `/api/v2`.

## Examples

Signed webhook, using the shell:

```bash
BODY='{"meta":{"time":"2026-10-22T09:00:00+05:30"},"data":{"id":"evt-1","type":"motion_detected","attributes":{"source":"sim.kitchen"}}}'
SIG="sha256=$(printf '%s' "$BODY" | openssl dgst -sha256 -hmac "$RING_WEBHOOK_SECRET" | awk '{print $2}')"
curl -s -X POST http://localhost:8080/api/ring/webhook \
  -H "Content-Type: application/json" -H "X-Signature: $SIG" -d "$BODY"
```

Note: the signature must be computed over the exact bytes sent. Use `printf '%s'` rather than `echo` to avoid adding a newline.
