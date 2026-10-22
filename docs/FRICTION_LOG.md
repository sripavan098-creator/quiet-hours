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
