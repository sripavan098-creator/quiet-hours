"""Browser check for the Quiet Hours page. Run with: python3 tests/ui_check.py

Needs Playwright and Chromium (pip install playwright; python -m playwright install chromium).
Starts its own dev server on a free port, drives the page, and stops the server.
Screenshots go to SHOTS_DIR. Exit code 0 means every check passed.
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
SHOTS_DIR = Path(os.environ.get("SHOTS_DIR", "/tmp/qh_shots"))
SHOTS_DIR.mkdir(parents=True, exist_ok=True)

failures = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for(url, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except Exception:
            time.sleep(0.2)
    return False


def check_production_sign_in():
    """Production mode: the house is locked until the caregiver code is entered."""
    token = "caregiver-ui-check-token-0123"
    port = free_port()
    env = {k: v for k, v in os.environ.items() if k != "QH_ENV"}
    env.update(PORT=str(port), RING_WEBHOOK_SECRET="ui-check-secret", QH_CAREGIVER_TOKEN=token)
    srv = subprocess.Popen([sys.executable, "server.py"], cwd=APP, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        if not wait_for(base + "/healthz"):
            check("production server started", False)
            return
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            page.goto(base + "/", wait_until="domcontentloaded")
            page.wait_for_selector("#signin:not([hidden])", timeout=5000)
            check("production: sign-in form shown before data", True)
            page.fill("#signin-token", token)
            page.click("#signin button[type=submit]")
            page.wait_for_function("document.getElementById('signin').hidden === true", timeout=5000)
            page.wait_for_timeout(500)
            check("production: correct code unlocks the page", page.locator("#signin").is_hidden())
            browser.close()
    except Exception as exc:  # report, do not hide
        check("production sign-in flow", False, str(exc).splitlines()[0][:200])
    finally:
        srv.terminate()
        srv.wait(timeout=5)


def main():
    port = free_port()
    env = dict(os.environ, QH_ENV="dev", PORT=str(port))
    srv = subprocess.Popen([sys.executable, "server.py"], cwd=APP, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        if not wait_for(base + "/healthz"):
            print("FAIL server did not start")
            return 1

        with sync_playwright() as p:
            browser = p.chromium.launch()
            errors = []

            # ---- phone layout ----
            phone = browser.new_page(viewport={"width": 360, "height": 780}, device_scale_factor=2)
            phone.on("pageerror", lambda e: errors.append(str(e)))
            phone.goto(base + "/", wait_until="domcontentloaded")
            phone.click("#btn-collapse")
            phone.wait_for_function("document.getElementById('headline').textContent === 'Check in now'")
            overflow = phone.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("360px: no horizontal scroll", overflow <= 0, f"overflow {overflow}px")
            phone.screenshot(path=str(SHOTS_DIR / "phone-collapse.png"), full_page=True)

            # Touch targets: every visible button at least 44px tall
            small = phone.evaluate("""
              [...document.querySelectorAll('button')].filter(b => b.offsetParent !== null)
                .map(b => [b.textContent.trim(), b.getBoundingClientRect().height])
                .filter(([, h]) => h < 44)
            """)
            check("360px: buttons at least 44px tall", not small, f"too small: {small}")

            # ---- collapse content ----
            alerts = phone.locator("#alerts .alert-item").count()
            check("collapse shows alerts", alerts >= 1, f"count {alerts}")
            summary = phone.inner_text("#scene-summary")
            check("screen-reader summary updated", "Home needs a check" in summary, summary[:80])

            # ---- rules panel ----
            phone.click("details.rules summary")
            rules_text = phone.inner_text("#rules-body")
            check("rules panel explains the limit", "longer of 3 hours" in rules_text, rules_text[:120])

            # ---- ordinary day ----
            phone.click("#btn-normal")
            phone.wait_for_function("document.getElementById('headline').textContent !== 'Check in now'")
            check("ordinary day clears the alert", phone.locator("#alerts .alert-item").count() == 0)
            phone.screenshot(path=str(SHOTS_DIR / "phone-ordinary.png"), full_page=True)

            # ---- setup view ----
            phone.click("#tab-setup")
            phone.wait_for_selector("#consent")
            fields_disabled = phone.evaluate("document.getElementById('setup-fields').disabled")
            check("setup fields locked until consent", fields_disabled is True)
            phone.check("#consent")
            phone.wait_for_function("!document.getElementById('setup-fields').disabled")
            rows = phone.locator("#device-list .device").count()
            check("setup lists the demo devices", rows == 5, f"rows {rows}")
            phone.locator("#device-list select").first.select_option("bedroom")
            phone.wait_for_function("document.getElementById('setup-status').textContent.includes('now in')")
            check("room change confirmed", True)
            phone.screenshot(path=str(SHOTS_DIR / "phone-setup.png"), full_page=True)

            # ---- desktop ----
            desk = browser.new_page(viewport={"width": 1280, "height": 800})
            desk.on("pageerror", lambda e: errors.append(str(e)))
            desk.goto(base + "/", wait_until="domcontentloaded")
            desk.click("#btn-collapse")
            desk.wait_for_function("document.getElementById('headline').textContent === 'Check in now'")
            desk.screenshot(path=str(SHOTS_DIR / "desktop-collapse.png"))

            check("no uncaught page errors", not errors, "; ".join(errors)[:200])
            browser.close()
    finally:
        srv.terminate()
        srv.wait(timeout=5)

    check_production_sign_in()

    print(f"\nScreenshots: {SHOTS_DIR}")
    if failures:
        print(f"{len(failures)} check(s) failed")
        return 1
    print("All browser checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
