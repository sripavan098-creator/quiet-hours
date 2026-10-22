# Data: Quiet Hours

This replaces the usual database document. v1.0 has no database; it keeps events in memory. This file records what is stored, why, and how it will be stored later.

## v1.0 storage

| Store | Contents | Lifetime | Location |
|---|---|---|---|
| `_events` dict | Internal events, keyed by `event_id` | Until restart or demo reload | Process memory |
| `_demo_now` | Demo clock | Until restart or demo reload | Process memory |
| Environment | Secrets and device map | Process lifetime | Host environment |

Nothing is written to disk by the application.

## Event record

| Field | Type | Required | Example | Notes |
|---|---|---|---|---|
| `event_id` | string | Yes | `evt-123` | Ring `data.id`; deduplication key |
| `device_id` | string | Yes | `kitchen` | Room identifier, from the device map |
| `device_name` | string | Yes | `Kitchen` | Display name |
| `ring_device_id` | string | Yes | `ava1.ring.device.x` | Ring device identifier |
| `kind` | string | Yes | `motion` | Internal kind |
| `ring_type` | string | Yes | `motion_detected` | Ring event type |
| `created_at` | string (ISO 8601) | Yes | `2026-10-22T09:00:00+05:30` | Ring `meta.time` |
| `source` | string | Yes | `ring` or `simulator` | Set by adapter |

Not stored, deliberately: video, audio, images, free-text, sub-type detail beyond what the adapter keeps, account IDs, names of people.

## Identifiers

- `event_id` comes from Ring and is unique per event. Duplicates are ignored, so Ring's retries do not double-count.
- Room identifiers are fixed: `kitchen`, `bathroom`, `bedroom`, `front_door`.
- The device map (`RING_DEVICE_ZONES`) is the only link between a Ring device and a room.

## Retention

| Stage | Rule |
|---|---|
| v1.0 | Held in memory; lost on restart |
| Gate 5.1 (persisted) | Keep 30 days by default; delete on request |
| Backups (Gate 5.1) | 14 days, encrypted; deleted with the events they contain |

Retention periods are a product decision. Shorter is better for privacy; the rules need at most 7 days of history, plus the current day.

## Planned persistence (Gate 5.1)

SQLite, one file, no server.

```sql
CREATE TABLE events (
  event_id      TEXT PRIMARY KEY,
  room          TEXT NOT NULL CHECK (room IN ('kitchen','bathroom','bedroom','front_door')),
  ring_device_id TEXT NOT NULL,
  kind          TEXT NOT NULL,
  ring_type     TEXT NOT NULL,
  created_at    TEXT NOT NULL,   -- ISO 8601 with offset, normalised to IST
  source        TEXT NOT NULL CHECK (source IN ('ring','simulator')),
  inserted_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX idx_events_room_time ON events (room, created_at);
CREATE INDEX idx_events_time      ON events (created_at);

CREATE TABLE device_map (
  ring_device_id TEXT PRIMARY KEY,
  room           TEXT NOT NULL CHECK (room IN ('kitchen','bathroom','bedroom','front_door')),
  updated_at     TEXT NOT NULL
);

CREATE TABLE caregivers (
  id            INTEGER PRIMARY KEY,
  email         TEXT NOT NULL UNIQUE,
  token_hash    TEXT NOT NULL,       -- store a hash of the token, never the token
  created_at    TEXT NOT NULL
);
```

Notes on the schema:
- `created_at` is stored normalised to IST (Gate 1.4), so string ordering matches time ordering for same-offset values.
- Tokens are stored as hashes. A lost token is replaced, never recovered.
- The `caregivers` table is for the auth step (Gate 1.3). It is small and needs no separate service.

## Migrations

Schema changes are numbered SQL files under `app/migrations/` (for example `0001_init.sql`). The application applies any missing migration at start and records it in a `schema_migrations` table. Migrations only add; a destructive change needs a written plan in `DEPLOYMENT.md`.

## Personal data inventory

| Data | Personal? | Who can see it | Where it is kept |
|---|---|---|---|
| Room movement times | Yes (about the monitored person) | Caregivers, after Gate 1.3 | Memory (v1.0), SQLite (Gate 5.1) |
| Ring device IDs | Indirectly | Caregivers and operator | Memory / SQLite |
| Caregiver email (Gate 1.3) | Yes | Operator | SQLite |
| Caregiver token hash | Security-sensitive | Nobody (never displayed) | SQLite |

## Deletion

When a monitored person or caregiver asks for deletion:
1. Delete all events for that household's devices.
2. Delete the device map entries.
3. Delete caregiver records and tokens.
4. Remove that household's events from backups as they expire, and record the date.

Deletion must be possible without touching other households. v1.0 is one household, so this is the process; multi-household support would need a household key on every row.

## Known limitations

- In-memory storage means a restart erases the history the rules depend on. After a restart the routine checks cannot run until four days of events have arrived again. The status page should say so (add to Gate 4.2).
- `created_at` offsets are inconsistent until Gate 1.4 normalises them.


## Storage (Gate 5)

Events are stored in SQLite (Python standard library, no new dependency), in the file named by `QH_DB_PATH` (default `data/quiet_hours.db`).

- One row per event, keyed by `event_id`. A repeated webhook is ignored.
- Retention: events older than 14 days before the newest stored event are deleted. The window is relative to stored data, not the wall clock.
- Unmapped devices keep their rows, with an empty room, so the rules ignore them.
- The file holds home movement data. Keep it on persistent storage that only the server can read, and delete it when a home is no longer monitored.
