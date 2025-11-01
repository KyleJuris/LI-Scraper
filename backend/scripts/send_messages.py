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
SETTINGS_TABLE = os.getenv("SUPABASE_SETTINGS_TABLE", "li_settings")

HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
SENDER_IDS_ENV = os.getenv("SENDER_IDS", "")

assert SUPABASE_URL and SUPABASE_KEY, "Missing SUPABASE_URL or SUPABASE_ANON_KEY"

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# --------------------------- LOAD SETTINGS FROM DB ---------------------------
def load_setting(key: str, default: str = "") -> str:
    """Load a setting from the database, fallback to default if not found."""
    url = f"{SUPABASE_URL}/rest/v1/{SETTINGS_TABLE}?key=eq.{key}&select=value"
    try:
        r = requests.get(url, headers=SB_HEADERS, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                return data[0].get("value", default)
    except Exception as e:
        print(f"[WARN] Failed to load setting '{key}' from DB: {e}")
    return default

# Load settings from database
LOCALE = load_setting("LOCALE", "en-US")
TIMEZONE_ID = load_setting("TIMEZONE_ID", "Asia/Dubai")
DEFAULT_DM = load_setting("DEFAULT_DM", "Hi {{first_name}} — thanks for connecting!")

MESSAGE_BTN_ROLE = re.compile(r"Message", re.I)
CONTENTEDITABLE_SELECTOR = "div[contenteditable='true']"
CONTENTEDITABLE_FALLBACK = "div.msg-form__contenteditable"

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

def fetch_connected_for_sender(sender_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    url = f"{sb_url(PROSPECTS_TABLE)}?status=eq.connected&assigned_sender=eq.{sender_id}&select=profile_url,first_name,dm_text&limit={limit}"
    r = requests.get(url, headers=SB_HEADERS)
    r.raise_for_status()
    return r.json()

def personalize(template: Optional[str], first_name: Optional[str]) -> str:
    t = (template or DEFAULT_DM) or "Hi — thanks for connecting!"
    if first_name:
        t = t.replace("{{first_name}}", first_name)
    return t

def mark_messaged(profile_url: str, dm_text: str) -> None:
    url = f"{sb_url(PROSPECTS_TABLE)}?profile_url=eq.{profile_url}"
    payload = {
        "status": "messaged",
        "dm_text": dm_text,
        "message_sent_at": now_iso(),
        "last_checked": now_iso(),
        "last_error": None,
    }
    r = requests.patch(url, headers=SB_HEADERS, json=payload)
    if r.status_code not in (200, 204):
        print("[DB] mark_messaged failed:", r.status_code, r.text)

def send_message_to_profile(page, profile_url: str, msg_text: str) -> bool:
    try:
        page.goto(profile_url, wait_until="domcontentloaded")
    except Exception as e:
        print("  [ERROR] load:", str(e)[:100])
        return False

    jitter_sleep(1.0, 1.8)

    try:
        message_btn = page.get_by_role("button", name=MESSAGE_BTN_ROLE)
        message_btn.wait_for(state="visible", timeout=5000)
        message_btn.click()
    except Exception:
        try:
            message_btn = page.locator("button:has-text('Message')").first
            message_btn.wait_for(state="visible", timeout=5000)
            message_btn.click()
        except Exception:
            print("  [!] Message button not found")
            return False

    jitter_sleep(0.8, 1.4)

    try:
        editor = page.locator(CONTENTEDITABLE_SELECTOR).first
        editor.wait_for(state="visible", timeout=5000)
    except Exception:
        try:
            editor = page.locator(CONTENTEDITABLE_FALLBACK).first
            editor.wait_for(state="visible", timeout=5000)
        except Exception:
            print("  [!] Message editor not found")
            return False

    try:
        editor.click()
        jitter_sleep(0.3, 0.7)
        page.keyboard.type(msg_text)
        jitter_sleep(0.8, 1.2)
        editor.press("Enter")
        jitter_sleep(0.8, 1.3)
        print("  [✓] Message sent")
        return True
    except Exception as e:
        print("  [ERROR] send:", str(e)[:120])
        return False

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

            rows = fetch_connected_for_sender(sid, limit=50)
            print(f"\n[Sender: {s.get('name','(no name)')}] Connected rows to message: {len(rows)}")
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
                first_name = row.get("first_name")
                dm_text = personalize(row.get("dm_text"), first_name)

                page = ctx.new_page()
                print(f"  [{i}/{len(rows)}] DM → {url}")
                ok = send_message_to_profile(page, url, dm_text)
                if ok:
                    mark_messaged(url, dm_text)
                jitter_sleep(1.0, 1.6)
                page.close()

            ctx.close()
            browser.close()

    print("\n[Done]")

if __name__ == "__main__":
    run()
