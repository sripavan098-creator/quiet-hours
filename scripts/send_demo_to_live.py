#!/usr/bin/env python3
"""Send simulated, Ring-shaped events to a running Quiet Hours server.

Every event goes through the signed webhook, exactly as a real Ring event would.
The data is SIMULATED. Say so in any demo or write-up.

Usage (the secret stays in your shell, never in the chat or the repo):
    export RING_WEBHOOK_SECRET='...same value as on Render...'
    python3 scripts/send_demo_to_live.py https://quiet-hours-q0or.onrender.com collapse

Scenario is "normal" or "collapse". Run ONE scenario per fresh server: the live
store is in memory, so redeploy on Render to clear it before switching.

Times are shifted so the simulated day ends at the current real time, so the
rules see a realistic recent rhythm instead of a stale one.
"""
import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import analysis  # noqa: E402
import ring_adapter  # noqa: E402
import sim  # noqa: E402

USAGE = "usage: send_demo_to_live.py <base-url> normal|collapse"


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[2] not in ("normal", "collapse"):
        print(USAGE)
        return 2
    base = sys.argv[1].rstrip("/")
    scenario = sys.argv[2]
    secret = os.environ.get("RING_WEBHOOK_SECRET", "").encode()
    if not secret:
        print("Set RING_WEBHOOK_SECRET in this shell first (same value as on Render).")
        return 2

    now_real = datetime.now(analysis.IST).replace(microsecond=0)
    events, demo_now = sim.generate(scenario, now_real.date())
    shift = now_real - demo_now

    sent = accepted = 0
    for internal in events:
        when = datetime.fromisoformat(internal["created_at"]) + shift
        if when > now_real:
            continue
        # Stable id from the UNshifted simulated time, so a rerun on the same day
        # is de-duplicated by the server instead of doubling the history.
        digest = hashlib.sha256(f"{internal['device_id']}|{internal['created_at']}".encode()).hexdigest()
        event = dict(internal, created_at=when.isoformat(), event_id="evt_sim_" + digest[:16])

        body = json.dumps(ring_adapter.to_ring_payload(event)).encode()
        signature = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
        req = urllib.request.Request(
            base + "/api/ring/webhook",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "X-Signature": signature},
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                result = json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as err:
            print(f"rejected with HTTP {err.code}: {err.read()[:200]!r}")
            print("A 401 means the secret here does not match the server's RING_WEBHOOK_SECRET.")
            return 1
        sent += 1
        accepted += int(result.get("accepted", 0))

    print(f"scenario '{scenario}': sent {sent} simulated events, newly accepted {accepted}")
    print("Open the page and sign in with your caregiver code to see the result.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
