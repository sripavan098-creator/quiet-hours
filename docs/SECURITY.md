# Security: Quiet Hours

Status: v1.0 is a hackathon build. It is **not safe for real households yet**. The issues in §4 must close before any real Ring account is connected.

## 1. What we protect

| Asset | Sensitivity | Why |
|---|---|---|
| Household movement pattern | High | Reveals when a person is awake, eating, or away |
| Ring webhook signing key | High | Anyone holding it can forge webhooks |
| Ring OAuth client secret and tokens | High | Grants access to the household's devices |
| Room-to-device mapping | Medium | Reveals which rooms the person uses |
| Source code and configuration | Low | Public by design (MIT) |

Quiet Hours does not receive, store or display video, audio or images. Keeping it that way is the main privacy control.

## 2. Threat model

| Threat | Likelihood | Impact | Current control | Gap |
|---|---|---|---|---|
| Forged webhook | Medium | Fake alerts, or hidden silence | HMAC-SHA256 with constant-time compare | Default key is public (4.1) |
| Anonymous reading of home status | High if URL shared | Privacy breach | None | No authentication (4.3) |
| Anonymous wipe via demo endpoint | Medium | Data loss; false state | None | Endpoint open (4.2) |
| Replayed valid webhook | Low | Duplicate event | Event-ID dedupe | Dedupe is in memory only |
| Oversized request | Low | Memory exhaustion | None | No body limit (4.5) |
| Secret in logs or repo | Medium | Forgery | Secrets read from environment | Must add secret scanning |
| Surveillance misuse by a household member | Medium | Harm to monitored person | Alerts only, no video | Consent flow (roadmap 4.5) |
| Ring token theft | Low | Device access | Tokens held in memory only | Encrypted storage when persisted (5.1) |

## 3. Controls in place

- **Webhook authenticity:** `X-Signature` is checked over the raw body with `hmac.compare_digest`. Ring's documented format (`sha256=` plus hex) is required; a bare hex value is rejected (covered by a test).
- **Input validation:** the adapter rejects payloads missing `meta` or `data`, and rejects unparseable timestamps. Unknown devices and event types are dropped.
- **Data minimisation:** the store keeps event ID, room, device ID, event type, and timestamp. Nothing else.
- **Response codes:** 401 and 400 tell Ring not to retry, so bad traffic does not amplify.
- **No outbound calls from user input:** the Ring client's URLs are fixed, apart from the device ID path segment, which is URL-encoded.
- **Standard library only:** no third-party server code in the runtime path.

## 4. Required fixes before real data

| # | Issue | Fix | Test |
|---|---|---|---|
| 4.1 | Default signing key `dev-only-change-me` is in the source | Refuse to start without `RING_WEBHOOK_SECRET` unless `QH_ENV=dev` | Starting without the variable exits non-zero |
| 4.2 | `/api/sim/demo` can wipe and replace all data, unauthenticated | Return 404 unless `QH_ENV=dev` | Request in production mode returns 404 |
| 4.3 | `/api/status` and `/api/events` reveal home activity to anyone | Caregiver bearer token required | Request without token returns 401 |
| 4.4 | Timestamps keep their own offsets, so the day and hour checks can be wrong for events from another timezone | Normalise to IST at adapter | Mixed-offset test |
| 4.5 | No request body size limit | Reject bodies over 64 KB with 413 | Oversized body test |

## 5. Secrets management

| Secret | Where it lives | Rotation |
|---|---|---|
| `RING_WEBHOOK_SECRET` | Environment variable on the host | When compromised, or at least yearly; update in the Ring Developer Portal first |
| `RING_CLIENT_SECRET` | Environment variable on the host | Per Ring's guidance |
| OAuth refresh tokens | In memory; encrypted at rest once persisted (Gate 5.1) | On each refresh |

Rules:
- Never commit a secret. `.gitignore` excludes `.env`.
- Use `.env.example` for names only, with no values.
- Do not print secrets in logs or error messages. The current `RingAPIError` includes up to 200 bytes of response body; review this before logging is added.

## 6. Privacy and consent

Quiet Hours monitors a person who may not have chosen to be monitored. Therefore:

- **Consent before setup.** The monitored person (or their legal guardian) agrees before linking devices. The setup screen (Gate 4.5) must show what is watched and what is not.
- **Visible to the monitored person.** A notice in the home or on a shared page says that movement is monitored and by whom.
- **No covert monitoring.** The product does not hide its existence from the monitored person.
- **Purpose limitation.** Data is used only for the routine alerts described in the PRD.
- **Retention.** v1.0 keeps events in memory only. Once persisted, retain events for no more than 30 days by default, and provide deletion.
- **India (DPDP Act 2023).** Treat the household as a data principal. Provide notice and consent, and honour deletion requests. This is an engineering summary, not legal advice; get a legal review before launch.

## 7. Health-adjacent data

Movement patterns can reveal health changes. The product:
- does not diagnose,
- does not use medical terms in alerts,
- does not share data with third parties,
- says in its copy that alerts are not medical advice and that emergency services come first.

Medicine-box data (if added) is health-adjacent and needs the same treatment as movement data, plus a clearer consent step.

## 8. Logging and monitoring

Current state: the server logs nothing (`log_message` is suppressed). This is safe but leaves no audit trail.

Target state (Gate 5.2):
- log event IDs, status codes and rule outcomes;
- never log room-level activity together with a caregiver identity;
- never log signatures, tokens or raw bodies.

## 9. Dependency and supply chain

- Runtime: Python standard library only.
- Test-time: standard `unittest` only.
- Frontend: Google Fonts (`fonts.googleapis.com`, `fonts.gstatic.com`). No other external scripts.
- Review: check Google Fonts' privacy implications (font requests reveal the viewer's IP to Google). Consider self-hosting the two fonts before launch.

## 10. Incident response

| Event | First action |
|---|---|
| Suspected webhook key leak | Rotate `RING_WEBHOOK_SECRET` in the Ring Developer Portal and on the host; restart; review recent events |
| Unexpected data wipe | Check whether `QH_ENV` was set to `dev` on a public host; restore from backup if persisted |
| Ring token exposure | Revoke via Ring; re-link the account |
| Privacy complaint from monitored person | Stop monitoring for that home; delete stored events; respond in writing |

## 11. Known limits

- The page cannot tell a human caregiver from anyone else with the URL until Gate 1.3 is done.
- Movement patterns are inferred from sensors and are not always accurate. A quiet morning can be an ordinary day.
- The product cannot detect a fall, a medical emergency, or a person who is still and well.
