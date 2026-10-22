# Coding Standards: Quiet Hours

These standards apply to all code in this repository, including code written with AI assistance.

## 1. Language and runtime

- Python 3.9 or later. Use `from __future__ import annotations` for modern type hints.
- Standard library only in `app/`. A new dependency needs a written reason in `ARCHITECTURE.md` and a review.
- No `eval`, `exec`, `pickle` on untrusted input, or `shell=True` in subprocess calls.

## 2. Structure

- `analysis.py` contains pure logic. It reads no clock, no environment and no files.
- `server.py` handles HTTP and state. It must not contain rule logic.
- `ring_adapter.py` handles payload shape only. It must not decide alerts.
- `sim.py` produces data only. It must not write to the store directly; it goes through the webhook path.
- Static assets live under `app/static/`. No build step.

## 3. Naming

| Kind | Style | Example |
|---|---|---|
| Module | `snake_case` | `ring_adapter.py` |
| Function | `snake_case`, verb first | `verify_signature`, `load_demo` |
| Constant | `UPPER_SNAKE` | `MIN_SILENCE`, `SIGNATURE_HEADER` |
| Class | `PascalCase` | `RingClient`, `PayloadError` |
| Room and event identifiers | lower `snake_case` strings | `front_door`, `motion_detected` |

Names describe what the thing means for the household, not how it is stored. Prefer `silence` over `delta`.

## 4. Error handling

- Raise specific exceptions (`PayloadError`, `RingAPIError`). Do not raise bare `Exception`.
- At the HTTP boundary, convert exceptions to status codes with a body of `{"error": ...}`.
- Never expose stack traces or internal paths to clients.
- Do not swallow exceptions silently. If an exception is intentionally ignored, say why in a comment.

## 5. Security

- Compare secrets with `hmac.compare_digest`. Never with `==`.
- Read secrets only from the environment.
- Validate all external input at the boundary: webhook bodies, query strings, path segments.
- URL-encode path segments built from external values (see `ring_client.device_events`).
- Do not log raw request bodies, signatures, tokens or secrets.
- Any new endpoint must state its authentication requirement in `API.md`.

## 6. Time

- Store and compare timestamps as timezone-aware datetimes.
- Convert to the home's local time (IST) before reading an hour or a date. Gate 1.4 implements this in the adapter.
- Never call `datetime.now()` without a timezone.
- Rules take `now` as an argument. Only the server supplies the current time.

## 7. Testing

- Every rule has a positive, negative and boundary test.
- Every bug fix includes a test that fails without the fix.
- Tests use explicit times and do not touch the network.
- A test that is skipped to pass a release is a failing test. See `TESTING.md`.

## 8. Comments and documentation

- Explain why, not what. The code states what.
- Module docstrings describe the module's job and its constraints (for example, "pure logic, no I/O").
- Any change to an endpoint, environment variable or rule updates `API.md`, `PRD.md` or `DEPLOYMENT.md` in the same commit.
- Do not write comments that reference the task or ticket that prompted them.

## 9. Frontend

- One HTML file, inline CSS and JavaScript. No framework and no build step.
- All text inserted from data uses `textContent`, never `innerHTML`.
- Honour `prefers-reduced-motion`.
- Controls have accessible names and visible focus.
- Colours come from the defined palette only: ink, beam, lit, watch, alarm.
- Alert colour is reserved for alerts. Do not use it for decoration.

## 10. Commits and review

- One logical change per commit. Message: a short summary line, then the reason.
- Commit trailers follow the team's attribution rule (Co-Authored-By and Claude-Session when an AI assistant contributed).
- Run the full test suite before committing.
- No secrets, no `.env` files, no generated `__pycache__`.
- Review checklist for a change:
  - [ ] Tests added or updated
  - [ ] No new dependency without a reason
  - [ ] Input validated at the boundary
  - [ ] Docs updated for any endpoint, variable or rule change
  - [ ] No personal data in logs or fixtures
