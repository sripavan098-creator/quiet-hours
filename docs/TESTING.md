# Testing: Quiet Hours

## Current suite

Run from the project root:

```bash
python3 -m unittest discover -s tests -v
```

24 tests, standard library only, under one second.

| File | Count | Covers |
|---|---|---|
| `tests/test_analysis.py` | 8 | Simulator scenarios; night stillness; daytime silence; threshold edge; routine check history requirement; future events ignored |
| `tests/test_webhook.py` | 16 | Signature format and verification; adapter mapping and rejection; webhook HTTP responses (401, 400, 200, dedupe); demo through signed path; token refresh |

## Test strategy by layer

| Layer | What it checks | Tool | Status |
|---|---|---|---|
| Unit: rules | R1–R3 against hand-built histories | `unittest` | Done |
| Unit: adapter | Ring payload to internal event; rejection | `unittest` | Done |
| Unit: signature | HMAC format and comparison | `unittest` | Done |
| Unit: client | Token exchange and refresh with a fake transport | `unittest` | Done |
| Integration: HTTP | Real server on an ephemeral port | `unittest` + `urllib` | Done (webhook, demo) |
| Contract: Ring | Real payloads and responses from Ring | Recorded fixtures, then live | Not done |
| End-to-end: UI | Page renders, controls work, alerts appear | Browser automation | Not done |
| Accessibility | Contrast, keyboard, reduced motion | Manual checklist, then axe-core | Not done |
| Performance | Status latency at 10,000 events | Script | Not done |
| Security | Auth on status, demo lockout, body limits | Tests after Gate 1 | Not done |

## Rules for test writing

1. Rules are tested with explicit times. Never call `datetime.now()` inside a rule test.
2. Each rule has a test for its positive case, its negative case, and its boundary.
3. Every security fix adds a test that fails without the fix.
4. Simulated data is used for behaviour tests. Real Ring payloads are added as fixtures only with the owner's permission and with identifiers replaced.
5. Tests do not depend on network access.

## Planned test additions

### Gate 1 (security and correctness)

| Test | Assertion |
|---|---|
| Start without `RING_WEBHOOK_SECRET` outside dev | Process exits non-zero |
| `POST /api/sim/demo` with `QH_ENV` unset | 404 |
| `GET /api/status` without token (after 1.3) | 401 |
| `GET /api/status` with valid token | 200 |
| Event with `+00:00` offset at 23:30 UTC | Treated as 05:00 IST next day |
| Body of 65 KB | 413 |

### Gate 2 (Ring)

| Test | Assertion |
|---|---|
| Recorded real payload (redacted) | Normalises to expected internal event |
| Token exchange fixture | Returns tokens |
| Device list fixture | Returns device IDs for mapping |
| Live: one motion webhook from a staging device | Event appears on `/api/events` within 60 s |

### Gate 4 (UI)

| Test | Assertion |
|---|---|
| Page loads and polls | `/api/status` called every 4 s |
| Ordinary day button | Status shows `ok` |
| Collapse button | Status shows `alert`; kitchen room shows alert colour |
| 360 px width | No horizontal scroll |
| Keyboard only | All buttons reachable and operable |
| Reduced motion | Beam does not animate |

### Gate 5 (hardening)

| Test | Assertion |
|---|---|
| 1,000 concurrent status reads | No errors; p95 under 200 ms |
| 10,000 stored events | Status under 200 ms |

## Known gaps in the current tests

- The analysis tests use Asia/Kolkata times consistently, so the timezone bug (ARCHITECTURE.md) is not yet caught. Gate 1.4 adds the mixed-offset test.
- No test covers the rule that a routine check needs 4 days of history in the whole window, as opposed to 4 days with that event. The current logic counts days with the event, which is the intent; add an explicit case.
- The UI has no automated tests.
- The `PartnerClient` test uses a fake transport. It proves the logic, not Ring's behaviour.

## Manual test script (before each demo recording)

1. Start the server with `cd app && python3 server.py`.
2. Open the page. Confirm the beam sweeps and the rooms draw.
3. Press "Ordinary day". Confirm the state is `ok`, the feed shows events, and there are no alerts.
4. Press "Simulate a collapse". Confirm the state is `alert`, the home alert and front-door alert appear, and the kitchen room is coral.
5. Resize to 360 px. Confirm nothing scrolls sideways.
6. Tab through the controls. Confirm focus is visible.
7. Stop the server.

## Exit criteria for release

- All automated tests pass.
- Manual test script passes.
- Gate 1 tests pass (before any real data).
- No failing test is marked as skipped to make a release.
