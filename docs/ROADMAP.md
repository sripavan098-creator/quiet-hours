# Roadmap: Quiet Hours

Planning is by gate, not by calendar, because the hackathon deadline is not yet confirmed. Each gate has an exit check. Work moves to the next gate only when the current exit check passes. If the deadline arrives early, the cut order in §5 applies.

## Current position

Gate 0 (local build) is complete: 24 tests pass, the code is committed, and the demo runs.

## Gate 0: Local build (complete)

| Item | Status |
|---|---|
| Routine rules (R1–R4) | Done |
| Signed webhook intake (F1, F2) | Done |
| Partner API client: token, refresh, devices | Done, fake transport only |
| Simulator with two scenarios | Done |
| Single-page UI with demo controls | Done |
| README, LICENSE, docs | Done |
| Git commit | Done |

Exit check: `python3 -m unittest discover -s tests` passes; demo runs.

## Gate 1: Fix before any real data (P0, required)

These are security and correctness issues found while writing the security model. They must be fixed before a real Ring account is connected.

| # | Item | Why | Done when |
|---|---|---|---|
| 1.1 | Refuse to start without `RING_WEBHOOK_SECRET` outside development | Default key is public in the source | Server exits with a clear message when the variable is missing and `QH_ENV` is not `dev` |
| 1.2 | Restrict `/api/sim/demo` to development | Anyone can clear and replace the event store | Route returns 404 unless `QH_ENV=dev` |
| 1.3 | Authenticate the status and events endpoints | Home activity is readable by anyone who knows the URL | Caregiver login (token) required; tests cover 401 |
| 1.4 | Normalise all timestamps to IST before rule checks | Events carry their own offsets; the day and hour checks use each event's own hour | Test with a mixed-offset event proves the same result |
| 1.5 | Limit request body size on the webhook | Unbounded read of `Content-Length` | Bodies over 64 KB are rejected with 413 |

Exit check: all five items closed, tests added for each, and `SECURITY.md` updated to say so.

## Gate 2: Live Ring path (P0 for a real demo)

| # | Item | Done when |
|---|---|---|
| 2.1 | Obtain Ring developer access (portal app, Playground or staging user) | Credentials stored outside the repo |
| 2.2 | OAuth account linking end to end | **Not done.** Linking routes not built; token refresh not run against Ring. Playground token shows the API works |
| 2.3 | List devices with `GET /v1/devices` | **Done.** Playground device listed (DoorbellPro, motion capable, online). Room mapping still to do |
| 2.4 | Receive one real motion webhook | **Not done.** No physical Ring device on the account. Signature verification is covered by tests; a live delivery is still needed |
| 2.5 | Confirm webhook timestamp field | **Done.** `meta.time` and `reported_at` are UTC with a `Z` suffix, confirmed from Playground API responses. Re-check on the first real webhook (2.4) |
| 2.6 | Confirm event-history query options | **Partly done.** Path confirmed live: `GET /v1/history/devices/{id}/events` returns events with no query parameters. Filters and pagination still untested. Response uses epoch-millisecond timestamps and `on_demand` event types, not motion |

Exit check: one real event flows from a Ring device to the page, with the signature verified.

Fallback: if credentials are not available in time, the demo uses the simulator and states that clearly in the video. The submission must not imply live data that was not used.

## Gate 3: Medicine box decision (P1)

| # | Item | Done when |
|---|---|---|
| 3.1 | Ask Ring whether a contact-sensor event type exists | Answer recorded in `docs/HACKATHON_PLAN.md` |
| 3.2 | If yes: add the event type to the adapter and test it | Medicine check works on a real device |
| 3.3 | If no: replace medicine check with a motion-based morning check | Rule R2 covers the kitchen; medicine claims removed from UI and video |

Decision owner: project author. Recommendation: 3.3 if the answer to 3.1 is not received within one working day.

## Gate 4: Product polish for judges (P1)

| # | Item | Done when |
|---|---|---|
| 4.1 | Room setup screen: list devices, assign rooms | Mapping saved without editing environment variables |
| 4.2 | Rules panel: show why an alert fired and the threshold used | Visible on the page for any alert |
| 4.3 | Phone-width layout check | No horizontal scroll at 360 px; controls reachable by keyboard |
| 4.4 | Accessibility pass against WCAG 2.1 AA | Contrast checked; focus visible; reduced motion respected |
| 4.5 | Consent and notice text | Shown before monitoring starts; wording reviewed |

Exit check: a first-time user can connect a device, assign rooms, and understand an alert without help.

## Gate 5: Hardening (P2)

| # | Item | Done when |
|---|---|---|
| 5.1 | Persist events to SQLite | Events survive a restart; retention limit applied |
| 5.2 | Structured logging without personal data | Logs contain event IDs and status codes only |
| 5.3 | Rate limiting on the webhook and status endpoints | Limits tested |
| 5.4 | Replay handling for missed webhooks | Duplicate events ignored (already true by event ID); gaps reported |
| 5.5 | Health and readiness endpoints | `/healthz` plus a readiness check for the secret and zone map |

## Gate 6: Submission package (required)

| # | Item | Done when |
|---|---|---|
| 6.1 | Demo video under 3 minutes, public, English, no copyrighted music | Uploaded; link recorded |
| 6.2 | Repo: public with MIT licence, or private with reviewers added | Visibility decided; reviewers added if private |
| 6.3 | Text description | Covers what it does, how it works, what is simulated and what is live |
| 6.4 | Product feedback on Ring | Covers onboarding, docs, simulator/Playground, feature requests |
| 6.5 | Track and mini-challenge entries | Ring track; Open Source only if chosen |
| 6.6 | Final check: tests pass, README quick start works on a clean machine | Verified by running it fresh |

## Cut order if time runs short

Cut in this order, keeping the items above it:
1. Gate 5 (hardening): keep 5.5 only.
2. Gate 4.1 (setup screen): keep the environment variable mapping and say so.
3. Gate 4.2 (rules panel): keep the alert text, which already explains the threshold.
4. Gate 2.6 (event history): drop; the demo does not need history backfill.
5. Never cut: Gate 1, Gate 2.4 or the simulated fallback statement, Gate 6.

## Milestones and dependencies

```
Gate 0 ──► Gate 1 ──► Gate 2 ──► Gate 6 (demo)
                 │          │
                 └──► Gate 3 ──► Gate 4 ──► Gate 5
```

Gate 1 does not depend on Ring access and can start now.

## Decisions needed from the author

1. Confirm the deadline.
2. Confirm the medicine-box approach (Gate 3).
3. Confirm repo visibility (Gate 6.2).
4. Confirm whether to enter the Open Source mini challenge.
