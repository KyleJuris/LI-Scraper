import os, re, json, time, random
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# ------------------------------- ENV -------------------------------
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")
PROSPECTS_TABLE = os.getenv("SUPABASE_TABLE", "li_prospects")
SENDERS_TABLE = os.getenv("SUPABASE_SENDERS_TABLE", "li_senders")

SEARCH_URL = os.getenv("SEARCH_URL", "")
PROFILE_LIMIT = int(os.getenv("PROFILE_LIMIT", "20"))
HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"
SEND_NOTE = os.getenv("SEND_NOTE", "false").lower() == "true"
CONNECT_NOTE = os.getenv("CONNECT_NOTE", "")
SENDER_IDS_ENV = os.getenv("SENDER_IDS", "")
SENDER_ROTATION = os.getenv("SENDER_ROTATION", "round_robin")
COLLECT_ONLY = os.getenv("COLLECT_ONLY", "false").lower() == "true"

LOCALE = os.getenv("LOCALE", "en-US")
TIMEZONE_ID = os.getenv("TIMEZONE_ID", "Asia/Dubai")

assert SUPABASE_URL and SUPABASE_KEY, "Missing SUPABASE_URL or SUPABASE_ANON_KEY"
assert SEARCH_URL, "Missing SEARCH_URL in .env"

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

# ----------------------------- SELECTORS -----------------------------
MORE_BUTTONS = [
    "main button[aria-label='More actions']",
    "main .pv-top-card button[aria-label='More actions']",
    "main .pv-top-card button:has(span:has-text('More'))",
    "main .pv-top-card button:has-text('More')",
    "main .pv-top-card button[data-view-name='profile-overflow-button']",
]

VISIBLE_DROPDOWN = "div.artdeco-dropdown__content[aria-hidden='false'], div[role='menu']:not([aria-hidden='true'])"

DROPDOWN_CONNECT = [
    f"{VISIBLE_DROPDOWN} div[role='button'][aria-label^='Invite ']:has(span:has-text('Connect'))",
    f"{VISIBLE_DROPDOWN} div[role='button']:has(span:has-text('Connect'))",
    "role=menuitem[name=/^Connect$/i]",
]

SEND_WITHOUT_NOTE_BTN = "button[aria-label='Send without a note'], button:has-text('Send without a note')"
ADD_NOTE_BTN = "button[aria-label='Add a note'], button:has-text('Add a note')"
NOTE_TEXTAREA = "textarea#custom-message, textarea[name='message']"
SEND_INVITE_BTN = "button[aria-label='Send invitation'], button:has-text('Send')"
NAME_H1 = "main h1"

# ------------------------------ UTILS ------------------------------
def jitter_sleep(a: float, b: float) -> None:
    time.sleep(random.uniform(a, b))

def normalize_profile_url(url: str) -> str:
    if "/in/" not in url:
        return url
    base = url.split("?")[0].split("#")[0]
    return base.rstrip("/")

def sb_url(table: str) -> str:
    return f"{SUPABASE_URL}/rest/v1/{table}"

def sb_post_upsert(table: str, payload: Dict[str, Any]) -> None:
    headers = dict(SB_HEADERS)
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    r = requests.post(sb_url(table), headers=headers, json=payload)
    if r.status_code not in (200, 201):
        print("[DB] Upsert failed:", r.status_code, r.text)

def sb_patch(table: str, eq_field: str, eq_value: str, payload: Dict[str, Any]) -> None:
    url = f"{sb_url(table)}?{eq_field}=eq.{eq_value}"
    r = requests.patch(url, headers=SB_HEADERS, json=payload)
    if r.status_code not in (200, 204):
        print("[DB] Patch failed:", r.status_code, r.text)

def load_senders() -> List[Dict[str, Any]]:
    q = f"{sb_url(SENDERS_TABLE)}?enabled=eq.true&select=id,name,user_agent,storage_state"
    if SENDER_IDS_ENV.strip():
        ids = [s.strip() for s in SENDER_IDS_ENV.split(",") if s.strip()]
        id_list = ",".join(ids)
        q = f"{sb_url(SENDERS_TABLE)}?id=in.({id_list})&enabled=eq.true&select=id,name,user_agent,storage_state"
    r = requests.get(q, headers=SB_HEADERS); r.raise_for_status()
    senders = r.json()
    if not senders:
        raise RuntimeError("No enabled senders found in Supabase.")
    for s in senders:
        st = s.get("storage_state")
        if isinstance(st, str):
            try: s["storage_state"] = json.loads(st)
            except Exception: s["storage_state"] = None
        elif st is None:
            s["storage_state"] = None
    return senders

def assign_sender(idx: int, senders: List[Dict[str, Any]]) -> Dict[str, Any]:
    if SENDER_ROTATION == "one_sender": return senders[0]
    return senders[idx % len(senders)]

def first_text(el) -> Optional[str]:
    if not el: return None
    try:
        t = el.inner_text().strip()
        return t if t else None
    except Exception:
        return None

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _verify_login(ctx) -> bool:
    p = ctx.new_page()
    p.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
    jitter_sleep(1.5, 2.5)
    ok = all(s not in p.url.lower() for s in ("login","challenge","uas/login"))
    p.close(); return ok

# ---------------------------- INVITE FLOW (WITH DELAYS) ----------------------------
def invite_flow(page, full_name: Optional[str]) -> Tuple[bool, bool]:
    def _click_any(selectors: List[str], visible_timeout: int = 4000) -> bool:
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() == 0:
                    continue
                try: loc.scroll_into_view_if_needed(timeout=1000)
                except Exception: pass
                loc.wait_for(state="visible", timeout=visible_timeout)
                loc.click()
                return True
            except Exception:
                try:
                    page.evaluate("(el)=>el.click()", page.locator(sel).first)
                    return True
                except Exception:
                    continue
        return False

    # 1) Click the More/… button
    clicked_more = _click_any(MORE_BUTTONS, 5000)
    if not clicked_more:
        return (False, False)
    jitter_sleep(0.8, 1.4)

    try:
        page.locator(VISIBLE_DROPDOWN).first.wait_for(state="visible", timeout=4000)
    except Exception:
        _click_any(MORE_BUTTONS, 2500)
        try:
            page.locator(VISIBLE_DROPDOWN).first.wait_for(state="visible", timeout=3000)
        except Exception:
            return (False, False)
    jitter_sleep(0.6, 1.2)

    # 2) Click Connect
    clicked_connect = _click_any(DROPDOWN_CONNECT, 4000)
    if not clicked_connect:
        return (False, False)
    jitter_sleep(0.8, 1.5)

    # 3) Note or no-note
    note_used = False
    if not SEND_NOTE:
        jitter_sleep(0.6, 1.1)
        if not _click_any([SEND_WITHOUT_NOTE_BTN], 3500):
            _click_any([SEND_INVITE_BTN], 3500)
        jitter_sleep(0.8, 1.3)
        return (True, False)

    if not _click_any([ADD_NOTE_BTN], 3500):
        pass
    jitter_sleep(0.6, 1.2)

    ta = page.locator(NOTE_TEXTAREA).first
    try:
        ta.wait_for(state="visible", timeout=3500)
        note_text = CONNECT_NOTE or ""
        if full_name and "{{first_name}}" in note_text:
            note_text = note_text.replace("{{first_name}}", full_name.split()[0])
        ta.fill(note_text)
        note_used = True
        jitter_sleep(0.8, 1.4)
    except Exception:
        note_used = True

    try:
        page.wait_for_timeout(300)
        btn = page.locator(SEND_INVITE_BTN).first
        if btn.count() > 0:
            try:
                btn.wait_for(state="visible", timeout=2500)
            except Exception:
                pass
            try:
                btn.click()
            except Exception:
                page.evaluate("(el)=>el.click()", btn)
        else:
            _click_any([SEND_INVITE_BTN], 2500)
    except Exception:
        pass
    jitter_sleep(1.0, 1.8)

    return (True, note_used)

# ------------------------------ HANDLE -----------------------------
def handle_profile(page, profile_url: str, acting_sender: Dict[str, Any]) -> None:
    try:
        page.goto(profile_url, wait_until="domcontentloaded")
    except PWTimeout:
        print("  [WARN] Timeout loading profile, skipping."); return
    jitter_sleep(1.2, 2.0)

    full_name = first_text(page.query_selector(NAME_H1))
    if full_name: print(f"  Name: {full_name}")

    if COLLECT_ONLY:
        payload = {
            "profile_url": profile_url,
            "full_name": full_name,
            "first_name": (full_name or "").split()[0] if full_name else None,
            "status": "new",
            "assigned_sender": acting_sender["id"],
            "assigned_at": now_iso(),
            "last_checked": now_iso(),
        }
        sb_post_upsert(PROSPECTS_TABLE, payload)
        print("  [OK] Saved (collect-only)."); return

    invite_attempted = False; note_used = False
    try:
        invite_attempted, note_used = invite_flow(page, full_name)
    except Exception as e:
        print("  [ERROR] invite_flow:", str(e)[:120])

    status = "new"
    if invite_attempted:
        status = "invited"
    else:
        try:
            rb = page.get_by_role("button", name=re.compile(r"Message", re.I))
            rb.wait_for(state="visible", timeout=1500)
            status = "connected"
        except Exception:
            if page.locator("text=Pending").count() > 0: status = "invited"

    payload = {
        "profile_url": profile_url,
        "full_name": full_name,
        "first_name": (full_name or "").split()[0] if full_name else None,
        "status": status,
        "note_sent": note_used,
        "note_text": CONNECT_NOTE if note_used else None,
        "assigned_sender": acting_sender["id"],
        "assigned_at": now_iso(),
        "invited_at": now_iso() if status in ("invited","connected") else None,
        "last_checked": now_iso(),
    }
    sb_post_upsert(PROSPECTS_TABLE, payload)
    print(f"  [OK] Saved as {status}{' (note)' if note_used else ''}.")

# ------------------------------- RUN -------------------------------
def run() -> None:
    senders = load_senders()
    first = senders[0]; st = first.get("storage_state"); ua = first.get("user_agent")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        base = browser.new_context(
            storage_state=st if isinstance(st, dict) else None,
            user_agent=ua if ua else None,
            viewport={"width": 1400, "height": 900},
            locale=LOCALE, timezone_id=TIMEZONE_ID,
            extra_http_headers={"Referer": "https://www.linkedin.com/feed/"},
        )

        if not _verify_login(base):
            print("[ERROR] First sender not authenticated. Update storage_state.")
            base.close(); browser.close(); return

        collector = base.new_page()
        links = []
        try:
            collector.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=60000)
            jitter_sleep(2.0, 3.0)
            for a in collector.query_selector_all("a[data-test-app-aware-link][href*='/in/']"):
                href = a.get_attribute("href")
                if href and "/in/" in href:
                    links.append(normalize_profile_url(href))
            links = links[:PROFILE_LIMIT]
        except Exception as e:
            print("[ERROR] collect_profile_links:", str(e))
        collector.close(); base.close()

        if not links:
            print("[INFO] No links found; nothing to do."); browser.close(); return

        for idx, link in enumerate(links):
            acting = senders[idx % len(senders)]
            st2 = acting.get("storage_state"); ua2 = acting.get("user_agent")
            ctx = browser.new_context(
                storage_state=st2 if isinstance(st2, dict) else None,
                user_agent=ua2 if ua2 else None,
                viewport={"width": 1400, "height": 900},
                locale=LOCALE, timezone_id=TIMEZONE_ID,
                extra_http_headers={"Referer": "https://www.linkedin.com/feed/"},
            )
            page = ctx.new_page()
            print(f"\n[{idx+1}/{len(links)}] {link} — sender: {acting.get('name','(no name)')}")
            try:
                handle_profile(page, link, acting)
                jitter_sleep(1.2, 2.0)
            except Exception as e:
                print("  [ERROR]", str(e)[:150])
                sb_patch(PROSPECTS_TABLE, "profile_url", link, {"last_error": str(e)[:500], "last_checked": now_iso()})
            finally:
                page.close(); ctx.close()

        browser.close(); print("\n[Done]")

if __name__ == "__main__":
    run()
