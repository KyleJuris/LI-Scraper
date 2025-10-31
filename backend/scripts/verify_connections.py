import os, re, json, time, random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")
PROSPECTS_TABLE = os.getenv("SUPABASE_TABLE", "li_prospects")
SENDERS_TABLE = os.getenv("SUPABASE_SENDERS_TABLE", "li_senders")

HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
SENDER_IDS_ENV = os.getenv("SENDER_IDS", "")
LOCALE = os.getenv("LOCALE", "en-US")
TIMEZONE_ID = os.getenv("TIMEZONE_ID", "Asia/Dubai")

assert SUPABASE_URL and SUPABASE_KEY, "Missing SUPABASE_URL or SUPABASE_ANON_KEY"

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

MESSAGE_BTN_ROLE = re.compile(r"Message", re.I)

def jitter_sleep(a: float, b: float) -> None:
    time.sleep(random.uniform(a, b))

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def sb_url(table: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}"

def load_senders() -> List[Dict[str, Any]]:
    q = f"{sb_url(SENDERS_TABLE)}?enabled=eq.true&select=id,name,user_agent,storage_state"
    if SENDER_IDS_ENV.strip():
        ids = [s.strip() for s in SENDER_IDS_ENV.split(",") if s.strip()]
        id_list = ",".join(ids)
        q = f"{sb_url(SENDERS_TABLE)}?id=in.({id_list})&enabled=eq.true&select=id,name,user_agent,storage_state"

    r = requests.get(q, headers=SB_HEADERS)
    r.raise_for_status()
    arr = r.json()
    for s in arr:
        st = s.get("storage_state")
        if isinstance(st, str):
            try:
                s["storage_state"] = json.loads(st)
            except Exception:
                s["storage_state"] = {}
    if not arr:
        raise RuntimeError("No enabled senders found.")
    return arr

def fetch_invited_for_sender(sender_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    url = f"{sb_url(PROSPECTS_TABLE)}?status=eq.invited&assigned_sender=eq.{sender_id}&select=profile_url&limit={limit}"
    r = requests.get(url, headers=SB_HEADERS)
    r.raise_for_status()
    return r.json()

def mark_connected(profile_url: str) -> None:
    url = f"{sb_url(PROSPECTS_TABLE)}?profile_url=eq.{profile_url}"
    payload = {"status": "connected", "connected_at": now_iso(), "last_checked": now_iso(), "last_error": None}
    r = requests.patch(url, headers=SB_HEADERS, json=payload)
    if r.status_code not in (200, 204):
        print("[DB] mark_connected failed:", r.status_code, r.text)

def touch_checked(profile_url: str) -> None:
    url = f"{sb_url(PROSPECTS_TABLE)}?profile_url=eq.{profile_url}"
    payload = {"last_checked": now_iso()}
    requests.patch(url, headers=SB_HEADERS, json=payload)

def _verify_login(ctx) -> bool:
    p = ctx.new_page()
    p.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded")
    jitter_sleep(1.0, 1.5)
    ok = ("login" not in p.url.lower()) and ("challenge" not in p.url.lower())
    p.close()
    return ok

def run() -> None:
    senders = load_senders()
    with sync_playwright() as p:
        for s in senders:
            sid = s["id"]
            state = s.get("storage_state") or {}
            ua = s.get("user_agent")

            rows = fetch_invited_for_sender(sid, limit=50)
            print(f"\n[Sender: {s.get('name','(no name)')}] Invited rows to verify: {len(rows)}")
            if not rows:
                continue

            browser = p.chromium.launch(headless=HEADLESS)
            ctx = browser.new_context(
                storage_state=state,
                user_agent=ua if ua else None,
                viewport={"width": 1400, "height": 900},
                locale=LOCALE,
                timezone_id=TIMEZONE_ID,
                extra_http_headers={"Referer": "https://www.linkedin.com/feed/"},
            )

            if not _verify_login(ctx):
                print("  [ERROR] Not authenticated (login/challenge). Refresh cookies.")
                ctx.close()
                browser.close()
                continue

            for i, row in enumerate(rows, start=1):
                url = row["profile_url"]
                page = ctx.new_page()
                print(f"  [{i}/{len(rows)}] {url}")
                try:
                    page.goto(url, wait_until="domcontentloaded")
                    jitter_sleep(1.0, 1.8)
                    connected = False

                    try:
                        btn = page.get_by_role("button", name=MESSAGE_BTN_ROLE)
                        btn.wait_for(state="visible", timeout=3000)
                        connected = True
                    except Exception:
                        try:
                            tb = page.locator("button:has-text('Message')").first
                            tb.wait_for(state="visible", timeout=2000)
                            connected = True
                        except Exception:
                            connected = False

                    if connected:
                        mark_connected(url)
                        print("    [✓] Connected → marked")
                    else:
                        touch_checked(url)
                        print("    [·] Still pending")
                    jitter_sleep(1.0, 1.6)
                except Exception as e:
                    print("    [ERROR]", str(e)[:120])
                    touch_checked(url)
                finally:
                    page.close()

            ctx.close()
            browser.close()

    print("\n[Done]")

if __name__ == "__main__":
    run()
