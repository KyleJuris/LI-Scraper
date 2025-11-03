# export_cookies.py
"""
Attach Playwright to your already-running Chrome via CDP and export storage_state.

Minimal behavior:
- Does NOT launch Chrome.
- Does NOT open any URL.
- Does NOT create a new context/page (so no new tab).
- Attaches to your existing Chrome (started with --remote-debugging-port=9222),
  grabs the FIRST existing browser context, and exports its storage_state.
"""

import os
import json
import time
from urllib.request import urlopen
from urllib.error import URLError, HTTPError

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, Error as PlaywrightError

load_dotenv()

CDP_PORT = int(os.getenv("CDP_PORT", "9222"))
CDP_ENDPOINT = os.getenv("CDP_ENDPOINT", f"http://127.0.0.1:{CDP_PORT}")
OUTPUT_JSON = os.getenv("OUTPUT_JSON", "storage_state.json")
CTX_LOCALE = os.getenv("LOCALE", "en-US")
CTX_TIMEZONE = os.getenv("TIMEZONE_ID", "Asia/Dubai")
CTX_USER_AGENT = os.getenv("USER_AGENT", "")  # not applied when reusing existing context

CDP_WAIT_SECONDS = int(os.getenv("CDP_WAIT_SECONDS", "30"))

def cdp_ready(endpoint: str) -> bool:
    try:
        urlopen(endpoint.rstrip("/") + "/json/version", timeout=1)
        return True
    except (URLError, HTTPError, TimeoutError):
        return False
    except Exception:
        return False

def ensure_chrome_running(endpoint: str, wait_seconds: int = 30) -> None:
    if cdp_ready(endpoint):
        return
    print("\n[NOTICE] Chrome with remote debugging not found at:", endpoint)
    print("Start your Chrome manually with (example):")
    print(r'  "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\chrome-debug"')
    input("After starting Chrome, press ENTER here to continue...")
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if cdp_ready(endpoint):
            return
        time.sleep(0.5)
    raise RuntimeError(f"Chrome CDP endpoint not ready after {wait_seconds}s at {endpoint}")

def save_json(path: str, data: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    ensure_chrome_running(endpoint=CDP_ENDPOINT, wait_seconds=CDP_WAIT_SECONDS)

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp(CDP_ENDPOINT)

            # IMPORTANT: reuse an existing context so no new tab opens
            contexts = browser.contexts
            if not contexts:
                print("\n[INFO] No existing browser context found.")
                print("Open any tab in your Chrome window (e.g., LinkedIn) and make sure you're logged in.")
                input("When ready, press ENTER to refresh and continue...")
                contexts = browser.contexts
                if not contexts:
                    raise RuntimeError("Still no browser context found. Make sure a tab is open in your Chrome.")

            ctx = contexts[0]  # reuse the first existing context (no new tab created)

            print("\n[INFO] Attached to your existing Chrome context.")
            print("[INFO] Navigate and log in manually in your Chrome window if you haven't already.")
            input("When you're ready to capture cookies, press ENTER here...")

            storage_state = ctx.storage_state()
            save_json(OUTPUT_JSON, storage_state)
            print(f"[OK] storage_state saved to: {OUTPUT_JSON}")

        except PlaywrightError as e:
            print(f"[ERROR] Playwright error: {e}")
            raise
        finally:
            try:
                browser.close()
            except Exception:
                pass

if __name__ == "__main__":
    main()
