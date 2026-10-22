# Instructions for AI agents working on Quiet Hours

Read this file before changing code. Then read `docs/PRD.md` for what the product must do and `docs/RULES.md` for how code is written.

## What this project is

Quiet Hours is a caretaker's home-watch built on Ring device events. It alerts a caregiver when a home's daily rhythm breaks. It never shows video. It is written in Python standard library plus one static HTML file.

## Absolute rules

1. **Never add video, audio or image handling.** Privacy is the product's core promise. If a request asks for it, decline and explain why.
2. **Never weaken the webhook signature check.** Ring's `X-Signature` format (`sha256=` plus hex HMAC of the raw body) must be enforced with `hmac.compare_digest`.
3. **Never commit secrets.** No keys, tokens, client secrets or `.env` files. Use environment variable names only.
4. **Never make the rules depend on the current time.** Rules take `now` as an argument.
5. **Never mark a test skipped to pass.** A failing test is reported, not hidden.
6. **Never expose the demo endpoint or unauthenticated home data in production.** See `docs/SECURITY.md` §4.
7. **Never add a runtime dependency without a written reason** in `docs/ARCHITECTURE.md`.
8. **Never claim live Ring data was used** unless it was. Say "simulated" when the simulator produced the data.
9. **Never invent Ring API details.** Use only the documented endpoints and fields. If a detail is unknown, say so and mark it as unverified, as `ring_client.device_events` does.
10. **Never alter the alert wording to sound more certain than the data allows.** Alerts describe observed patterns, not conditions.

## Before you change code

1. Run the tests: `python3 -m unittest discover -s tests`. Note the count.
2. Read the module you are changing and its tests.
3. Identify which doc describes the behaviour you are changing: `API.md` for endpoints, `PRD.md` for rules, `DEPLOYMENT.md` for configuration.

## While you change code

- Keep `analysis.py` pure. No I/O, no clock reads.
- Keep `server.py` free of rule logic.
- Validate external input at the boundary.
- Add a test that fails without your change.
- Use `textContent` for any data shown in the page.

## After you change code

1. Run the full test suite. All tests must pass.
2. Update the matching document in `docs/` in the same change.
3. Update `docs/ROADMAP.md` if a gate item is completed.
4. Confirm `git status` shows only intended files.
5. Commit with a summary line and a reason. Include the attribution trailers required by the repository's rules.

## Project map

| Path | Purpose |
|---|---|
| `app/server.py` | HTTP server, webhook, demo loader |
| `app/analysis.py` | Rules R1–R3 (pure) |
| `app/ring_adapter.py` | Ring payload ↔ internal event |
| `app/ring_client.py` | Ring Partner API client |
| `app/sim.py` | Simulator |
| `app/store.py` | SQLite event store (stdlib) |
| `app/static/index.html` | UI |
| `tests/` | Unit and integration tests |
| `docs/` | PRD, roadmap, architecture, API, security, deployment, testing, rules, data |

## Known issues to be aware of

- Gate 1 (IST times, dev-only demo route, caregiver token, body limit) is done and tested.
- The medicine-box check was removed (Gate 3.3). The morning check uses kitchen motion.

## When unsure

Ask the project author. Do not guess at Ring's behaviour, privacy trade-offs, or the deadline.
