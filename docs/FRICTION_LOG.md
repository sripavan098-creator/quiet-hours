# Friction Log: Ring developer experience

Recorded during the Amazon Developer Hackathon (Ring track). Each entry follows the brief's format: task, steps, expected versus actual, severity, workaround, and a suggestion. Entries are factual and dated. Anything not yet tested live is marked **unverified**.

Severity scale: **Critical** blocks the build · **High** costs hours · **Medium** needs a workaround · **Low** cosmetic or minor.

---

## F-001: Contact-sensor webhook type not in the documented list

- **Date:** 2026-10-22
- **Task:** Find the webhook event type for a contact sensor (door or medicine box).
- **Steps:** Read the Ring webhook documentation and the release notes. Searched for contact-sensor event types.
- **Expected:** A documented event type for contact sensors, since the Contact Sensors scope exists in the app creation form.
- **Actual:** The documented webhook types cover motion and button presses, plus device and subscription lifecycle events. No contact-sensor event type appears in the sections I could read.
- **Severity:** High (blocks one of our two routine checks on real hardware)
- **Workaround:** Simulate the event and state that it is simulated. Check the Playground once the Contact Sensors scope is on.
- **Suggestion:** List every webhook event type per scope in one table, with the payload example for each.
- **Status:** Open. To verify in the Playground.

## F-002: Developer documentation pages are very long

- **Date:** 2026-10-22
- **Task:** Read the full API reference, including the notifications and event history sections.
- **Steps:** Fetched the API documentation page with a summary tool.
- **Expected:** Each section reachable on its own, or a clear per-section link.
- **Actual:** The page text is about 122,000 characters. A single fetch returned only the first 100,000, so the webhook verification and event history sections were not readable in one pass. Reading them required several searches.
- **Severity:** Medium
- **Workaround:** Searched for the specific section, and read the notifications page on its own.
- **Suggestion:** Split the reference into one page per topic, with stable anchors. This would also help AI-assisted development.
- **Status:** Open.

## F-003: Webhook signature header is documented in two places with different detail

- **Date:** 2026-10-22
- **Task:** Confirm the webhook signature header name and format.
- **Steps:** Read the API overview, then the notifications page.
- **Expected:** One definitive description of the header, the signed bytes and the encoding.
- **Actual:** The overview names `X-Signature` and says HMAC-SHA256 with hex encoding. The notifications page gives the header format (`sha256=` plus hex) and an example verifier, but the signed bytes are only shown in code. The overview does not mention the `sha256=` prefix.
- **Severity:** Low
- **Workaround:** Followed the example verifier, which signs the raw request body.
- **Suggestion:** State the signed input (raw body) in prose, and show the `sha256=` prefix in the overview too.
- **Status:** Resolved by reading the notifications page. Verify against a real delivery.

## F-004: Event history query parameters not confirmed

- **Date:** 2026-10-22
- **Task:** Confirm the query options for `GET /v1/history/devices/{device_id}/events`.
- **Steps:** Searched the documentation for the Event History section.
- **Expected:** A parameter table with the event types and pagination field.
- **Actual:** The section was beyond the readable part of the page (see F-002). The overview only lists the endpoint and says it returns motion events with `sub_type` and `component_ids`.
- **Severity:** Medium
- **Workaround:** Build the client as a pass-through and mark the call as unverified.
- **Suggestion:** Put the query parameters in the endpoint summary, not only in the full reference.
- **Status:** Open until confirmed in the Playground.

## F-005: Scope bundles video permissions into the cameras group

- **Date:** 2026-10-22
- **Task:** Request motion events for a camera without requesting video access.
- **Steps:** Opened the app creation form and read the Cameras and Doorbells scope.
- **Expected:** Separate scopes for motion events and for livestream or video download.
- **Actual:** The Cameras and Doorbells group covers motion events, doorbell presses, livestream and video download in one switch. Motion-only access is not offered.
- **Severity:** Medium (a privacy-sensitive product has to request more than it uses)
- **Workaround:** Request the group, document that livestream and download are never called, and say so in the submission.
- **Suggestion:** Offer a motion-and-events-only scope, since many products need events without video.
- **Status:** Open. Will be stated in the privacy section of the submission.

## F-006: Sample app and notifications docs disagree on webhook authentication

- **Date:** 2026-10-22
- **Task:** Confirm how a Ring webhook is authenticated, using the official sample app and the notifications documentation.
- **Steps:** Read the README of `AmazonAppDev/ring-api-helloworld`, then the notifications page of the API documentation.
- **Expected:** The sample app and the reference describe the same scheme.
- **Actual:** The notifications page describes `X-Signature` (HMAC-SHA256 with a `sha256=` prefix). The sample app describes `RING_WEBHOOK_SECRET` as a "Bearer token for webhook auth" and does not name the header. Its README also doesn't describe a signature scheme, the token exchange request, or a public HTTPS setup.
- **Severity:** High (a wrong guess would make every real webhook fail with 401)
- **Workaround:** Followed the notifications page. Will check against a real delivery in the Playground.
- **Suggestion:** Make the sample app verify the signature the same way the reference documents it, and show the full verification code.
- **Status:** Open. Unverified until a real webhook arrives.

## F-007: Event-history timestamps are epoch milliseconds

- **Date:** 2026-10-22
- **Task:** Read event timestamps from `GET /v1/history/devices/{id}/events` and compare them with webhook timestamps.
- **Steps:** Called the endpoint in the Developer Playground with the device ID in the path, and no query parameters.
- **Expected:** One timestamp format across the API, as ISO 8601, the same as `meta.time` in webhooks and `reported_at` in device status.
- **Actual:** `start` and `end` are epoch milliseconds (for example `1792663221791`). Webhook `meta.time` and device status `reported_at` are ISO 8601 with a `Z` suffix.
- **Severity:** Medium (every consumer needs a special case).
- **Workaround:** Convert the values in the client. Not yet written.
- **Suggestion:** Use one timestamp format everywhere, or state the unit in the field name, such as `start_ms`.
- **Status:** Open.

## F-008: Event history on the test device contains only on-demand sessions

- **Date:** 2026-10-22
- **Task:** Find motion events for the Playground device in event history.
- **Steps:** Called the event-history endpoint for the device in the Playground.
- **Expected:** Motion events listed for a device whose capabilities include motion detection.
- **Actual:** Two events, both with `event_type: "on_demand"`, empty `cv_detections`, and `is_third_party_reviewed: true`. No motion events.
- **Severity:** Medium (history cannot be used to confirm motion).
- **Workaround:** Motion is taken only from webhooks. The rules ignore `on_demand` events.
- **Suggestion:** Document every `event_type` value and what each one covers, with one example per type.
- **Status:** Open.

## F-009: No way to send a test webhook without a physical device

- **Date:** 2026-10-22
- **Task:** Trigger a signed webhook delivery to our endpoint from the Playground, without a physical device.
- **Steps:** Opened the Playground's "Simulate live view event" options (Package, Vehicle, Motion).
- **Expected:** A test-delivery option that sends a signed webhook to a configured URL.
- **Actual:** The simulate options start a live-view session. They do not call our webhook URL, and no test-delivery option was found.
- **Severity:** High (blocks end-to-end verification of the webhook path without hardware).
- **Workaround:** Simulated events sent through the same signed path, and labelled as simulated.
- **Suggestion:** Add a "send test webhook" action that signs the body with the app's signing key.
- **Status:** Open.

---

## Template for new entries

```markdown
## F-00X: Short title

- **Date:**
- **Task:**
- **Steps:**
- **Expected:**
- **Actual:**
- **Severity:** Critical / High / Medium / Low
- **Workaround:**
- **Suggestion:**
- **Status:** Open / Resolved / Unverified
```
