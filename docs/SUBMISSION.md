# Submission Checklist: Quiet Hours (Ring track)

Source: the Amazon Developer Hackathon brief. Status is as of this commit. "Blocked" means it needs something only the author can provide.

## Required to submit

| # | Requirement | Status | Notes |
|---|---|---|---|
| S1 | Track and mini-challenge entered | Partly | Ring track chosen. Mini challenge: none yet (Open Source possible, see S10) |
| S2 | Text description: what it does and how it works | Ready to draft | Use PRD §1–3 and ARCHITECTURE overview |
| S3 | GitHub repo with all source, assets and run instructions | Ready | Local git repo with commits. No remote yet (see S4) |
| S4 | Repo public with open-source licence, or private and shared with testing@devpost.com and the Amazon reviewers | Blocked | Needs the author's choice of visibility and GitHub account |
| S5 | Reviewers added as collaborators (private repo only) | Blocked | Add at submission time: knmeiss, giolaq, anishamalde, mosesroth, emersonsklar. Invitations expire after 7 days |
| S6 | Demo video under 3 minutes, public YouTube or Vimeo, English | Not started | Script in HACKATHON_PLAN.md §6. Needs the live Ring path or a clear "simulated" statement |
| S7 | Product feedback on every Ring tool, API or SDK used | Draft outline | HACKATHON_PLAN.md §7. Needs real onboarding experience |
| S8 | Explanation of anything built before the window | Ready | Project started during the window; state this plainly |
| S9 | Repo calls the Ring technology in code (import, entry point or config) | Ready | `ring_client.py` (Partner API) and `ring_adapter.py` (webhook shape) are used by `server.py` |
| S10 | Open Source mini challenge (optional) | Decision needed | Requires a licence (MIT present) and a URL, plus a description of what was built during the window |
| S11 | Feature requests (optional) | Ready | Room setup by discovery; contact-sensor webhook type; Playground webhook delivery |
| S12 | Friction log (optional, up to 10% judging bonus) | Not started | Log real friction hit during live testing |

## Track-specific rule: Ring

- Repo must call Ring in code, not only mention it. **Met:** `ring_client.py` and `ring_adapter.py` are imported and used.
- Demo must show a simulator or device. **Met (simulator):** the demo runs on the built-in Ring-shaped simulator. Say so in the video.

## What blocks a full submission

1. **Live Ring test (Phase 2 in ROADMAP).** No Ring developer credentials yet. Without them, the demo is simulated. That is acceptable if the video and text say so, but a judge scoring "Tech implementation" will value a real webhook.
2. **Repo visibility and GitHub account (S4, S5).**
3. **Deadline.** Not in the brief. Needed to schedule the video and feedback.
4. **Medicine-box decision: resolved.** The medicine check was replaced with a motion-based kitchen morning check (Gate 3.3).

## Judging criteria self-assessment

Scored as a judge would, out of 10, against the brief. Scores assume the simulator demo, with the live path untested.

| Criterion | Score now | What lifts it to 9+ |
|---|---|---|
| Tech implementation | 7 | Live Ring webhook and device list; real payload fixtures in tests; token refresh proven against Ring |
| Design | 8 | Phone and desktop checked (done); reviewed copy; accessible focus and contrast (done) |
| Potential impact | 7 | A named caregiver user story in the video; consent flow visible; a clear note on who is not served |
| Quality of the idea | 8 | Clear contrast with camera products; the "rhythm, not video" argument in the first minute of the video |

## Next actions, in order

1. Author decisions: repo visibility, GitHub account, deadline, Open Source entry.
2. Ring developer access, then Phase 2 (live path).
3. Demo video (script ready) and product feedback (outline ready).
4. Submission text from PRD §1–3.
