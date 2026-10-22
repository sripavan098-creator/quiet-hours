# Quiet Hours: Hackathon Plan and Documentation

Amazon Developer Hackathon 2026, **Ring track** (primary). Mini challenges: none yet (Open Source is possible; see below).

Deadline: **not stated in the brief. Confirm before planning the final days.**

---

## 1. Project summary

Quiet Hours is a caretaker's view of an ordinary home, built on Ring events. It learns each home's daily rhythm (kitchen, bathroom, bedroom movement, the front door, the medicine box). It alerts a remote family member or caregiver only when that rhythm breaks. It never shows live video.

**Problem:** Adult children and caregivers of older or solo-living relatives want reassurance that the person is okay, without watching cameras or calling every hour.

**Who it serves:** family caregivers, and people who live alone and want their routine understood without surveillance.

**Ring priority category:** caretaking, with accessibility as a secondary fit.

---

## 2. Judging criteria: how the project answers each one

| Criterion | What we show | Current status |
|---|---|---|
| **Tech implementation** | Signed webhook intake using Ring's documented `X-Signature` HMAC scheme; adapter for Ring's `{meta, data}` payload; OAuth token exchange and refresh; device discovery; adaptive silence rules | Webhook path and client are built and tested with fakes. **Not yet run against live Ring.** |
| **Design** | Lighthouse-style floor plan: a beam sweeps the home, rooms glow when active, turn coral only when the rhythm breaks. Copy written as a keeper's log | Built and loads. Not yet reviewed on a phone or with a screenshot. |
| **Potential impact** | Specific caregiver need; privacy-first (no video, alerts only); the same logic can serve any home with motion sensors | Credible case; needs a short user statement in the write-up |
| **Quality of the idea** | Turns existing home motion data into a care signal instead of a camera feed; learns each home's own rhythm rather than using fixed rules | Strong story; the demo must show it clearly |

---

## 3. Architecture

```
Ring cloud ──webhook (X-Signature)──► /api/ring/webhook
                                          │ verify HMAC over raw body
                                          │ ring_adapter.normalise()
                                          ▼
                                   event store (dedupe by event id)
                                          │
Browser ◄── /api/status ◄── analysis.assess(events, now)
```

Files:

| File | Purpose |
|---|---|
| `app/server.py` | HTTP server, webhook intake, demo loader |
| `app/ring_adapter.py` | Ring payload ↔ internal event |
| `app/ring_client.py` | Partner API client (token, devices, history pass-through) |
| `app/analysis.py` | Routine rules (pure, no I/O) |
| `app/sim.py` | Ring-shaped household simulator |
| `app/static/index.html` | Single-page UI |
| `tests/` | 24 unit and integration tests |

Ring facts used, from the Ring developer docs:
- Webhook header `X-Signature: sha256=<hex HMAC-SHA256 of raw body>`
- Payload `{meta: {time, account_id}, data: {id, type, attributes: {source}}}`
- Response rules: 2xx delivered; 4xx not retried; 5xx retried; over 5 s counts as 5xx
- Token endpoint `POST https://oauth.ring.com/oauth/token`; devices `GET https://api.amazonvision.com/v1/devices`

---

## 4. Current status

**Done**
- Core analysis rules, with home silence and two routine checks
- Signed webhook path with Ring's payload shape and correct response codes
- Partner API client with refresh-on-401 (fake transport tests)
- Simulator with two scenarios: ordinary day and collapse
- Immersive UI with demo controls
- README, MIT license, `.gitignore`
- 49 passing tests

**Not done**
- Live Ring test: no developer credentials yet
- Medicine box signal: no documented Ring event type for contact sensors (see Risks)
- Event-history query options: not confirmed from the docs
- Room setup screen: device-to-room mapping is an environment variable only
- Git repository and submission repo
- Demo video, product feedback, submission text

---

## 5. Plan to finish

### Phase A: Verify against Ring (highest priority)
1. Register the app in the Ring Developer Portal. Get `client_id`, `client_secret` and the webhook signing key. Keep them out of version control.
2. Use the Developer Playground or a staging user to test: token exchange, `GET /v1/devices`, and one real motion webhook.
3. Confirm `meta.time` and `data.attributes.timestamp` formats against a real payload.
4. Confirm event-history query parameters from the Event History section of the docs, then implement `device_events()` properly.
5. Map real device IDs into `RING_DEVICE_ZONES`.

### Phase B: Close the medicine gap
Options, in order of preference:
1. Ask Ring which sensor types send webhooks (via the Developer FAQ or the partner contact). If a contact event exists, adapt the adapter.
2. Replace the medicine check with a "morning movement in the kitchen before 10:00" check, which uses only motion events. Drop the medicine-box claim from the demo.
3. Keep the medicine check simulated only, and say so in the video and write-up.

Option 2 is the safer plan if the Ring answer is slow.

### Phase C: Product polish for judges
- Room setup screen: list discovered devices and let the user assign rooms. Keeps the mapping in the product, not in env vars.
- Check the UI on a phone-sized viewport and fix any layout issues.
- Add a short "how the rules work" panel so judges can see why an alert fired.
- Confirm the alert copy is calm and specific, and avoids alarming phrasing without grounds.

### Phase D: Submission package
- Demo video under 3 minutes: public YouTube or Vimeo, English, no copyrighted music.
- Repo: either public with the MIT licence (already included), or private and shared with the Amazon reviewers.
- Text description: what it does, how it works, what is simulated and what is live.
- Product feedback on Ring: onboarding, webhook docs, simulator/Playground, what worked and what needs work.
- Track and mini-challenge entry.
- If the project pre-dates the window: a clear statement of what was built during the window. This project is new.

---

## 6. Demo script (under 3 minutes)

Judges may stop watching at 3 minutes, so the strongest material goes first.

| Time | Scene | What to show |
|---|---|---|
| 0:00–0:20 | Hook | "Your mum lives alone. You want to know she's okay, without watching her through a camera." |
| 0:20–0:50 | The house | Open the page. Beam sweeps the floor plan, rooms glow. Caption: "It learns this home's rhythm." |
| 0:50–1:30 | Collapse | Press "Simulate a collapse". Room turns coral, "Check in now" with the reason in plain words. |
| 1:30–2:10 | Why it's calm | Show the ordinary day. "Night stillness is expected." Show the rules panel. |
| 2:10–2:40 | Under the hood | Show the signed webhook, the 401 for a bad signature, Ring's payload being normalised. |
| 2:40–3:00 | Close | Impact statement, and what's next (live Ring device, room setup). |

If the live Ring path is not working by submission, the demo must say the data is simulated, and show the Ring-shaped payload.

---

## 7. Product feedback draft (Ring)

Fill in from real experience during the build. Points to cover:

- **Onboarding:** how long from registration to the first webhook? Note any friction.
- **Webhook docs:** signature scheme and payload shape were clear. The notifications section was long, and the header name was only confirmed on the separate notifications page.
- **Event types:** the documented webhook list has no contact-sensor type. Request this, since caretaking depends on it.
- **Event history:** query parameters were not readable from the fetched docs. Ask for an example.
- **Simulator/Playground:** note whether it sends webhooks (earlier notes say it does not).
- **Would you build with it again:** answer honestly after the live test.

---

## 8. Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Medicine box has no Ring event type | Medicine check can't run on real devices | Option 2 in Phase B; say so in the demo |
| No live Ring access before deadline | Judges see only simulation | Use the Playground; record the simulator; be explicit about what is simulated |
| Motion zones only fire inside configured zones | Quiet rooms may look quiet by design | Document zone setup; choose rooms with clear coverage |
| Judges treat this as surveillance | Undermines the pitch | Lead with "no video", show consent and alerts-only design |
| Deadline unknown | Plan may overrun | Confirm the date first; cut Phase C if needed |

---

## 9. Optional extras

- **Open Source mini challenge:** the repo already has an MIT licence. It would qualify if a new open-source project or a contribution is submitted with a URL and a short description. Note that this project is new, and the brief asks for a clear account of what was built during the window.
- **AWS Builder mini challenge:** not in scope. Adding it would mean a real AWS service, such as Bedrock for the wording of alerts, documented in code.

---

## 10. Open questions for you

1. What is the **submission deadline**?
2. Do you have **Ring developer access** (portal account, or Playground)?
3. Do you want the repo **public** (MIT already included) or **private** with the reviewers added?
4. Are you entering the **Open Source** mini challenge?
