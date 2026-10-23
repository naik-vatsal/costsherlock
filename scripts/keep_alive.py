"""Wake the Streamlit Community Cloud app and confirm it is serving.

Run by .github/workflows/keep-alive.yml. Opens the app in a real browser (a plain
HTTP ping does not count as activity), clicks the "get this app back up" button
if the app was hibernating, then waits for the Streamlit UI to render.
"""
from __future__ import annotations

import os
import sys

from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "https://costsherlock.streamlit.app")
WAKE_BUTTON = "button:has-text('Yes, get this app back up')"


def main() -> int:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1280, "height": 800})
        page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        try:
            page.wait_for_selector(WAKE_BUTTON, timeout=15_000)
            page.click(WAKE_BUTTON)
            print("App was asleep - wake button clicked")
        except PWTimeout:
            print("App already awake")
        try:
            # The app renders inside an iframe on Streamlit Cloud.
            frame = page.frame_locator("iframe[title='streamlitApp']")
            frame.locator("[data-testid='stApp']").first.wait_for(timeout=180_000)
            print("App is up")
            return 0
        except PWTimeout:
            page.screenshot(path="keep-alive-failure.png")
            print("App did not come up in time", file=sys.stderr)
            return 1
        finally:
            browser.close()


if __name__ == "__main__":
    sys.exit(main())
