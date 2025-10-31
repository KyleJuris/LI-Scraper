import os
import time
import json
import random
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

# Simple header-based auth; leave open if BACKEND_API_KEY is unset (dev)
API_KEY = os.getenv("BACKEND_API_KEY", "")

def require_api_key(x_api_key: Optional[str]):
    if not API_KEY:
        return  # dev mode: no key required
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

# Ensure we can import user's existing scripts from ../scripts
import sys
from pathlib import Path
THIS_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = (THIS_DIR / ".." / "scripts").resolve()
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.append(str(SCRIPTS_DIR))

# ---- Import user-provided modules (do not modify their contents) ----

import connect_and_save as cs
import send_messages as sm
import verify_connections as vc

from playwright.sync_api import sync_playwright

app = FastAPI(title="LinkedIn Automation API", version="1.0.0")

# -------- Request models --------
class PopulateReq(BaseModel):
    search_url: str
    profile_limit: int = 20
    collect_only: bool = False
    send_note: bool = False
    note_text: str = ""
    sender_rotation: str = "round_robin"

class SendReq(BaseModel):
    limit: int = 20                 # total messages to attempt across senders
    default_dm: Optional[str] = None  # optional override per request

class VerifyReq(BaseModel):
    limit: int = 50

# -------- Helpers --------
def _set_env_temp(pairs: dict):
    """Temporarily set os.environ vars for the duration of a call."""
    old = {}
    for k, v in pairs.items():
        old[k] = os.environ.get(k)
        if v is None:
            if k in os.environ:
                del os.environ[k]
        else:
            os.environ[k] = str(v)
    return old

def _restore_env(old: dict):
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

# -------- Endpoints --------
@app.get("/health")
def health():
    return {"ok": True}

@app.post("/lists/populate")
def lists_populate(body: PopulateReq, x_api_key: Optional[str] = Header(None)):
    """
    Builds/updates a prospect list by running the user's connect_and_save pipeline.
    Env variables are set temporarily from the request body.
    """
    require_api_key(x_api_key)

    temp = _set_env_temp({
        "SEARCH_URL": body.search_url,
        "PROFILE_LIMIT": str(body.profile_limit),
        "COLLECT_ONLY": "true" if body.collect_only else "false",
        "SEND_NOTE": "true" if body.send_note else "false",
        "CONNECT_NOTE": body.note_text or os.getenv("CONNECT_NOTE", ""),
        "SENDER_ROTATION": body.sender_rotation or os.getenv("SENDER_ROTATION", "round_robin"),
    })
    try:
        # The user's script should encapsulate its own run flow.
        # Expectation: it will upsert prospects in Supabase and optionally send invites.
        cs.run()
        return {"ok": True}
    finally:
        _restore_env(temp)

@app.post("/campaigns/send")
def campaigns_send(body: SendReq, x_api_key: Optional[str] = Header(None)):
    """
    Sends DMs to connected prospects. Respects an overall 'limit' across senders.
    Reuses the user's send_messages module and its internal helpers.
    """
    require_api_key(x_api_key)

    results = {"attempted": 0, "sent": 0, "errors": 0}
    dm_old = None
    if body.default_dm:
        dm_old = _set_env_temp({"DEFAULT_DM": body.default_dm})

    with sync_playwright() as p:
        senders = sm.load_senders()
        for sender in senders:
            if results["attempted"] >= body.limit:
                break

            sid = sender.get("id")
            state = sender.get("storage_state") or {}
            ua = sender.get("user_agent")

            # Fetch rows this module considers ready to message, honor limit
            remaining = body.limit - results["attempted"]
            rows = sm.fetch_connected_for_sender(sid, limit=remaining)
            if not rows:
                continue

            browser = p.chromium.launch(headless=getattr(sm, "HEADLESS", True))
            ctx = browser.new_context(
                storage_state=state,
                user_agent=ua if ua else None,
                viewport={"width": 1400, "height": 900},
                locale=getattr(sm, "LOCALE", "en-US"),
                timezone_id=getattr(sm, "TIMEZONE_ID", "UTC"),
                extra_http_headers={"Referer": "https://www.linkedin.com/feed/"},
            )

            if not sm._verify_login(ctx):
                ctx.close(); browser.close()
                continue

            for row in rows:
                if results["attempted"] >= body.limit:
                    break
                url = row.get("profile_url")
                first_name = row.get("first_name")
                dm_text = row.get("dm_text")

                # Prefer per-row text; else personalize DEFAULT_DM
                msg = dm_text or sm.personalize(os.getenv("DEFAULT_DM", ""), first_name)

                page = ctx.new_page()
                try:
                    results["attempted"] += 1
                    ok = sm.send_message_to_profile(page, url, msg)
                    if ok:
                        sm.mark_messaged(url, msg)
                        results["sent"] += 1
                    else:
                        results["errors"] += 1
                except Exception:
                    results["errors"] += 1
                finally:
                    page.close()
                    time.sleep(random.uniform(0.8, 1.6))

            ctx.close(); browser.close()

    if dm_old:
        _restore_env(dm_old)

    return {"ok": True, **results}

@app.post("/connections/verify")
def connections_verify(body: VerifyReq, x_api_key: Optional[str] = Header(None)):
    """
    Re-check profiles that were invited but not yet marked 'connected'.
    """
    require_api_key(x_api_key)

    checked = 0
    connected = 0

    with sync_playwright() as p:
        senders = vc.load_senders()
        for sender in senders:
            sid = sender.get("id")
            state = sender.get("storage_state") or {}
            ua = sender.get("user_agent")

            rows = vc.fetch_invited_for_sender(sid, limit=body.limit)
            if not rows:
                continue

            browser = p.chromium.launch(headless=getattr(vc, "HEADLESS", True))
            ctx = browser.new_context(
                storage_state=state,
                user_agent=ua if ua else None,
                viewport={"width": 1400, "height": 900},
                locale=getattr(vc, "LOCALE", "en-US"),
                timezone_id=getattr(vc, "TIMEZONE_ID", "UTC"),
                extra_http_headers={"Referer": "https://www.linkedin.com/feed/"},
            )

            if not vc._verify_login(ctx):
                ctx.close(); browser.close()
                continue

            page = ctx.new_page()
            for r in rows[: body.limit]:
                checked += 1
                try:
                    page.goto(r["profile_url"], wait_until="domcontentloaded", timeout=45000)
                    time.sleep(random.uniform(1.0, 1.6))

                    # Heuristic: if a Message button exists, consider connected.
                    try:
                        btn = page.get_by_role("button", name=getattr(vc, "MESSAGE_BTN_ROLE", "Message"))
                        btn.wait_for(state="visible", timeout=2500)
                        vc.mark_connected(r["profile_url"])
                        connected += 1
                    except Exception:
                        vc.touch_checked(r["profile_url"])
                except Exception:
                    vc.touch_checked(r["profile_url"])

            page.close()
            ctx.close(); browser.close()

    return {"ok": True, "checked": checked, "connected": connected}

