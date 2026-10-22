# Product Requirements: Quiet Hours v1.0

Status: Draft for hackathon. Owner: project author. Last updated: 2026-10-22.

## 1. Summary

Quiet Hours is a caretaker's view of a home, built on Ring device events. It learns each home's daily rhythm from motion and door activity, and it tells a remote family member or caregiver when that rhythm breaks. It never shows live video, never records audio, and never asks the monitored person to do anything.

## 2. Problem

Adult children and caregivers of older or solo-living relatives want reassurance that the person is safe and following their routine. Today they either:
- call repeatedly, which is intrusive and unreliable, or
- install cameras in the home, which the monitored person often experiences as surveillance.

Quiet Hours offers a third option: know when the routine breaks, without seeing into the home.

## 3. Goals

| ID | Goal | Measure of success |
|---|---|---|
| G1 | Detect a break in daily routine within a short window | Alert fires within one check cycle (defined in §7) of the silence threshold being crossed |
| G2 | Avoid false alarms | No alert during night hours; thresholds adapt to each home's own pattern |
| G3 | Protect the monitored person's privacy | No video, audio or images are received, stored or shown |
| G4 | Be trustworthy as an integration | Webhooks verified with HMAC-SHA256 and handled per Ring's documented response rules |
| G5 | Be understandable in one glance | A caregiver understands the house state in under five seconds |

## 4. Non-goals (v1.0)

- Live video, recordings or snapshots
- Medical diagnosis, fall detection by sensor fusion, or emergency dispatch
- Control of any Ring device
- Multi-home dashboards for one caregiver
- Persistent storage across restarts (in-memory in v1.0)
- Languages other than English
- Native mobile apps (responsive web only)

## 5. Users

| User | Needs | Notes |
|---|---|---|
| Caregiver (primary) | Calm, specific alerts; a clear picture of today | Opens the page or receives an alert |
| Monitored person (secondary) | To feel respected; to understand what is watched | Must have consented; the UI copy says what is and is not seen |
| Home owner / installer | Maps devices to rooms; supplies the signing key | Usually the monitored person or a family member |

## 6. Rooms and signals

| Room | Ring signal (v1.0) | Counts toward home silence | Routine check |
|---|---|---|---|
| Kitchen | Motion | Yes | No |
| Bathroom | Motion | Yes | No |
| Bedroom | Motion | Yes | No |
| Front door | Motion (door-facing camera) | No | Usual errand before 12:00 |
| Medicine box | None documented by Ring (see §12) | No | Morning check before 10:00 |

## 7. Rules

All rules run only between 07:00 and 22:00 in the home's local time (IST in v1.0). Outside those hours the status is "resting" and no alert is raised.

**R1. Home silence.** Time since the last movement in any interior room. The threshold is the longer of:
- 3 hours, or
- 3 × the median gap between daytime movements over the last 7 days (needs at least 5 gaps; otherwise the 3-hour minimum applies).

Status: `ok` below 75% of the threshold; `watch` between 75% and 100%; `alert` above the threshold.

**R2. Routine checks.** The front door (by 12:00) and the medicine box (by 10:00) alert only when:
- there are at least 4 days of history in the last 7, and
- on at least 4 of those days, the usual event happened before the check hour, and
- today nothing has happened yet, and it is past the check hour.

**R3. Overall state.** `alert` if any alert is active; otherwise `watch` if any room is `watch`; otherwise `ok`.

**R4. Calm copy.** Every alert states the observed fact, the usual pattern, and nothing more. The UI never says a person has fallen or is unwell.

## 8. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| F1 | Accept Ring webhooks at `POST /api/ring/webhook` and verify the `X-Signature` header | Must |
| F2 | Normalise Ring payloads to internal events; drop unmapped devices and unknown types | Must |
| F3 | Compute home status and per-room status for the current time | Must |
| F4 | Show the house status, alerts, key facts and recent signals in one page | Must |
| F5 | Simulate an ordinary day and a collapse scenario through the same signed path | Must (demo) |
| F6 | Map Ring device IDs to rooms through configuration | Must |
| F7 | Connect to Ring via OAuth and list devices | Should |
| F8 | Setup screen to map devices to rooms without editing configuration | Should |
| F9 | Replay of missed webhooks via Ring's replay process | Could |
| F10 | Persist events across restarts | Could |

## 9. Non-functional requirements

- **Latency:** status responses under 200 ms on the development machine with 10,000 stored events.
- **Availability:** best-effort for the hackathon; the webhook must respond within 5 seconds to avoid Ring retries.
- **Privacy:** only motion and door-event metadata is stored; no media is requested or stored.
- **Accessibility:** WCAG 2.1 AA for text contrast and keyboard use; reduced-motion respected; the beam animation is static under reduced motion.
- **Dependencies:** Python 3.9+ standard library only for the server; no third-party runtime packages.

## 10. Success criteria for the hackathon

1. A judge can run the demo locally in under five minutes using the README.
2. The demo shows both an ordinary day and a collapse, and the collapse alert explains itself in plain words.
3. The live Ring path is exercised end to end against a Ring developer account or the Playground, or the demo states clearly that it uses simulated data.
4. All automated tests pass.
5. The submission explains the privacy design in the first minute of the video.

## 11. Assumptions

- Ring webhooks are delivered for motion events from configured zones (per Ring's FAQ).
- The home's local time zone is Asia/Kolkata (IST). Multi-timezone support is out of scope.
- The monitored person has agreed to be monitored, and a caregiver has access to the alerts.

## 12. Open questions and risks

| ID | Question or risk | Impact | Plan |
|---|---|---|---|
| Q1 | Ring has no documented contact-sensor webhook type, so the medicine check cannot run on real devices | Medicine check is simulated only | Confirm with Ring, or replace with motion-based morning check (decision needed) |
| Q2 | Event-history query parameters not confirmed | Historical backfill not possible yet | Confirm from Ring's Event History documentation |
| Q3 | No live Ring credentials yet | Live path untested | Obtain access; test in Playground first |
| Q4 | Deadline not stated | Scope may be cut | Confirm; roadmap has a cut order |
| Q5 | Consent and legal basis for monitoring a third person | Misuse risk; regulatory exposure | Consent flow in the product (R-ROADMAP item) and a clear privacy notice |

## 13. Out of scope items that a reviewer may ask about

- Why not cameras? Because the monitored person's privacy is the core promise. Cameras would make this a surveillance product.
- Why not wearables? The brief's Ring track is the target; a wearable would be a separate integration.
- Why the 3-hour minimum? Shorter thresholds raise false alarms in ordinary homes; the adaptive part handles busier homes.
