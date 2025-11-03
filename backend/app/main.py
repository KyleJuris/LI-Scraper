import os
import time
import json
import random
import importlib
import logging
import traceback
import uuid
from typing import Optional, Dict, List
from datetime import datetime, timezone
from threading import Thread
import subprocess
import sys
from pathlib import Path
import requests
from dotenv import load_dotenv

from fastapi import FastAPI, Header, HTTPException, Request, BackgroundTasks
from starlette.requests import Request as StarletteRequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Simple header-based auth; leave open if BACKEND_API_KEY is unset (dev)
API_KEY = os.getenv("BACKEND_API_KEY", "")

def require_api_key(x_api_key: Optional[str]):
    if not API_KEY:
        return  # dev mode: no key required
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

# Database settings helpers
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SETTINGS_TABLE = os.getenv("SUPABASE_SETTINGS_TABLE", "li_settings")
LISTS_TABLE = os.getenv("SUPABASE_LISTS_TABLE", "li_lists")
PROSPECTS_TABLE = os.getenv("SUPABASE_TABLE", "li_prospects")
SENDERS_TABLE = os.getenv("SUPABASE_SENDERS_TABLE", "li_senders")

# Validate required environment variables
if not SUPABASE_URL:
    logger.error("SUPABASE_URL is not set in environment variables!")
    raise ValueError("SUPABASE_URL environment variable is required")
if not SUPABASE_KEY:
    logger.error("SUPABASE_ANON_KEY is not set in environment variables!")
    raise ValueError("SUPABASE_ANON_KEY environment variable is required")

SB_HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

def _update_db_setting(key: str, value: str) -> Optional[str]:
    """Update a setting in the database and return the old value."""
    # Get old value
    url = f"{SUPABASE_URL}/rest/v1/{SETTINGS_TABLE}?key=eq.{key}&select=value"
    old_value = None
    try:
        r = requests.get(url, headers={**SB_HEADERS, "Prefer": "return=representation"}, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                old_value = data[0].get("value")
    except Exception:
        pass
    
    # Update setting
    url = f"{SUPABASE_URL}/rest/v1/{SETTINGS_TABLE}"
    payload = {"key": key, "value": value}
    headers = {**SB_HEADERS, "Prefer": "resolution=merge-duplicates"}
    try:
        requests.post(url, headers=headers, json=payload, timeout=5)
    except Exception:
        pass
    
    return old_value

def _set_db_settings_temp(pairs: Dict[str, str]) -> Dict[str, Optional[str]]:
    """Temporarily update database settings and return old values."""
    old = {}
    for k, v in pairs.items():
        old[k] = _update_db_setting(k, str(v))
    return old

def _restore_db_settings(old: Dict[str, Optional[str]]):
    """Restore database settings to old values."""
    for k, v in old.items():
        if v is not None:
            _update_db_setting(k, v)

def _load_db_setting(key: str, default: str = "") -> str:
    """Load a setting from the database."""
    url = f"{SUPABASE_URL}/rest/v1/{SETTINGS_TABLE}?key=eq.{key}&select=value"
    try:
        r = requests.get(url, headers=SB_HEADERS, timeout=5)
        if r.status_code == 200:
            data = r.json()
            if data and len(data) > 0:
                return data[0].get("value", default)
    except Exception:
        pass
    return default

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

# Add middleware to log all requests
@app.middleware("http")
async def log_requests(request: StarletteRequest, call_next):
    import json
    logger.info("=" * 80)
    logger.info(f"→ INCOMING REQUEST: {request.method} {request.url.path}")
    logger.info(f"  Full URL: {request.url}")
    logger.info(f"  Client: {request.client}")
    logger.info(f"  Headers: {dict(request.headers)}")
    
    if request.method == "POST":
        # Read body
        body_bytes = await request.body()
        logger.info(f"  Body length: {len(body_bytes)} bytes")
        
        if body_bytes:
            try:
                body_str = body_bytes.decode('utf-8')
                logger.info(f"  Body content: {body_str}")
                # Try to parse as JSON
                try:
                    body_json = json.loads(body_str)
                    logger.info(f"  Parsed JSON: {json.dumps(body_json, indent=2)}")
                except:
                    logger.info(f"  Body is not valid JSON")
            except Exception as e:
                logger.error(f"  Error decoding body: {e}")
        
        # CRITICAL: Restore body stream for FastAPI to read
        async def receive():
            return {"type": "http.request", "body": body_bytes}
        request._receive = receive
    
    logger.info("  Calling next middleware/endpoint...")
    response = await call_next(request)
    logger.info(f"← RESPONSE: {response.status_code} for {request.method} {request.url.path}")
    logger.info("=" * 80)
    return response

# CORS middleware for frontend - MUST be added before routes
# Build allowed origins list from environment variables
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
]

# Add production frontend URL(s) from environment variable
# Can be a single URL or comma-separated list
frontend_url = os.getenv("FRONTEND_URL", "").strip()
if frontend_url:
    # Split by comma and strip whitespace for multiple URLs
    production_urls = [url.strip() for url in frontend_url.split(",") if url.strip()]
    allowed_origins.extend(production_urls)
    logger.info(f"CORS: Added production frontend URL(s): {production_urls}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)


# -------- Request models --------
class PopulateReq(BaseModel):
    search_url: str
    profile_limit: int = 20
    collect_only: bool = False
    send_note: bool = False
    note_text: str = ""

class SendReq(BaseModel):
    limit: int = 20                 # total messages to attempt across senders
    default_dm: Optional[str] = None  # optional override per request
    list_ids: Optional[List[str]] = None  # optional list IDs to filter prospects
    sender_id: Optional[str] = None  # optional sender ID to use for sending

class VerifyReq(BaseModel):
    limit: int = 50

class UpdateListReq(BaseModel):
    name: str

# -------- Helpers --------

# -------- Endpoints --------
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/senders")
def get_senders(x_api_key: Optional[str] = Header(None, alias="X-API-KEY")):
    """
    Get all senders from the database.
    """
    try:
        require_api_key(x_api_key)
        
        # Fetch all senders (both enabled and disabled)
        url = f"{SUPABASE_URL}/rest/v1/{SENDERS_TABLE}?select=id,name,enabled,updated_at,storage_state&order=created_at.desc"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        senders_data = response.json()
        
        # Ensure storage_state is returned as string if it exists, and always include the field
        for sender in senders_data:
            # Ensure storage_state field is always present in the response
            if "storage_state" not in sender:
                sender["storage_state"] = None
            
            # Handle storage_state - convert dict to JSON string, keep string as-is, keep null as null
            if sender["storage_state"] is not None:
                if isinstance(sender["storage_state"], dict):
                    sender["storage_state"] = json.dumps(sender["storage_state"])
                # If it's already a string, keep it as-is
            # If it's None, it stays None
        
        return JSONResponse(status_code=200, content=senders_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching senders: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"ok": False, "detail": f"Error fetching senders: {str(e)}"}
        )

@app.patch("/senders/{sender_id}/toggle")
def toggle_sender(sender_id: str, x_api_key: Optional[str] = Header(None, alias="X-API-KEY")):
    """
    Toggle the enabled status of a sender.
    """
    try:
        require_api_key(x_api_key)
        
        # Get current sender status
        get_url = f"{SUPABASE_URL}/rest/v1/{SENDERS_TABLE}?id=eq.{sender_id}&select=enabled"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        
        get_response = requests.get(get_url, headers=headers, timeout=10)
        get_response.raise_for_status()
        sender_data = get_response.json()
        
        if not sender_data:
            return JSONResponse(status_code=404, content={"detail": "Sender not found"})
        
        current_enabled = sender_data[0].get("enabled", False)
        new_enabled = not current_enabled
        
        # Update sender status
        update_url = f"{SUPABASE_URL}/rest/v1/{SENDERS_TABLE}?id=eq.{sender_id}"
        update_data = {
            "enabled": new_enabled,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        update_response = requests.patch(update_url, headers=headers, json=update_data, timeout=10)
        update_response.raise_for_status()
        
        logger.info(f"Toggled sender {sender_id} enabled status to {new_enabled}")
        
        return JSONResponse(status_code=200, content={"id": sender_id, "enabled": new_enabled})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling sender: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"ok": False, "detail": f"Error toggling sender: {str(e)}"}
        )

class UpdateSenderReq(BaseModel):
    name: str
    storage_state: Optional[str] = None

class CreateSenderReq(BaseModel):
    name: str
    storage_state: Optional[str] = None

@app.patch("/senders/{sender_id}")
def update_sender(
    sender_id: str,
    body: UpdateSenderReq,
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY")
):
    """
    Update a sender (e.g., rename).
    """
    try:
        require_api_key(x_api_key)
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        
        # Prepare update data
        update_data = {
            "name": body.name,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        # Add storage_state if provided
        if body.storage_state is not None:
            if body.storage_state.strip() == "":
                # Empty string means clear/remove storage_state
                update_data["storage_state"] = None
            else:
                # Validate JSON if provided
                try:
                    json.loads(body.storage_state)
                    update_data["storage_state"] = body.storage_state
                except json.JSONDecodeError:
                    return JSONResponse(
                        status_code=400,
                        content={"ok": False, "detail": "storage_state must be valid JSON"}
                    )
        
        # Update sender
        update_url = f"{SUPABASE_URL}/rest/v1/{SENDERS_TABLE}?id=eq.{sender_id}"
        update_response = requests.patch(update_url, headers=headers, json=update_data, timeout=10)
        update_response.raise_for_status()
        
        logger.info(f"Updated sender {sender_id}")
        
        return JSONResponse(status_code=200, content={"id": sender_id, "ok": True})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating sender: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"ok": False, "detail": f"Error updating sender: {str(e)}"}
        )

@app.post("/senders")
def create_sender(
    body: CreateSenderReq,
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY")
):
    """
    Create a new sender. ID will be auto-generated by Supabase.
    """
    try:
        require_api_key(x_api_key)
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        sender_data = {
            "name": body.name,
            "enabled": True,  # All new accounts are enabled by default
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        if body.storage_state:
            # Validate JSON if provided
            try:
                json.loads(body.storage_state)
                sender_data["storage_state"] = body.storage_state
            except json.JSONDecodeError:
                return JSONResponse(
                    status_code=400,
                    content={"ok": False, "detail": "storage_state must be valid JSON"}
                )
        
        create_url = f"{SUPABASE_URL}/rest/v1/{SENDERS_TABLE}"
        create_response = requests.post(create_url, headers=headers, json=sender_data, timeout=10)
        
        if create_response.status_code in (200, 201):
            created_sender = create_response.json()
            sender_id = created_sender[0]["id"] if isinstance(created_sender, list) else created_sender.get("id")
            logger.info(f"Created sender {sender_id}")
            return JSONResponse(status_code=200, content={"id": sender_id, "ok": True})
        else:
            logger.error(f"Failed to create sender: {create_response.status_code} - {create_response.text}")
            return JSONResponse(
                status_code=create_response.status_code,
                content={"ok": False, "detail": f"Failed to create sender: {create_response.text}"}
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating sender: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"ok": False, "detail": f"Error creating sender: {str(e)}"}
        )

@app.get("/lists")
def get_lists(x_api_key: Optional[str] = Header(None, alias="X-API-KEY")):
    """
    Get all lists from the database with their prospect counts.
    """
    try:
        require_api_key(x_api_key)
        
        # Fetch all lists
        url = f"{SUPABASE_URL}/rest/v1/{LISTS_TABLE}?select=*&order=created_at.desc"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        lists_data = response.json()
        
        # For each list, get the prospect count from li_prospects
        for list_item in lists_data:
            list_id = list_item.get("id")
            if list_id:
                # Count prospects for this list
                prospects_url = f"{SUPABASE_URL}/rest/v1/{PROSPECTS_TABLE}?list_id=eq.{list_id}&select=id"
                prospects_response = requests.get(prospects_url, headers=headers, timeout=10)
                if prospects_response.status_code == 200:
                    prospects = prospects_response.json()
                    list_item["count"] = len(prospects)
                    list_item["profile_count"] = len(prospects)
                else:
                    list_item["count"] = list_item.get("profile_count", 0)
            else:
                list_item["count"] = list_item.get("profile_count", 0)
        
        return JSONResponse(status_code=200, content=lists_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching lists: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"ok": False, "detail": f"Error fetching lists: {str(e)}"}
        )

@app.get("/lists/{list_id}")
def get_list_detail(list_id: str, x_api_key: Optional[str] = Header(None, alias="X-API-KEY")):
    """
    Get a specific list with its details.
    """
    try:
        require_api_key(x_api_key)
        
        url = f"{SUPABASE_URL}/rest/v1/{LISTS_TABLE}?id=eq.{list_id}&select=*"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        lists_data = response.json()
        
        if not lists_data:
            return JSONResponse(status_code=404, content={"detail": "List not found"})
        
        return JSONResponse(status_code=200, content=lists_data[0])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching list detail: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "detail": f"Error fetching list: {str(e)}"}
        )

@app.get("/lists/{list_id}/prospects")
def get_list_prospects(list_id: str, x_api_key: Optional[str] = Header(None, alias="X-API-KEY")):
    """
    Get all prospects for a specific list.
    """
    try:
        require_api_key(x_api_key)
        
        url = f"{SUPABASE_URL}/rest/v1/{PROSPECTS_TABLE}?list_id=eq.{list_id}&select=*&order=created_at.desc"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        prospects = response.json()
        
        return JSONResponse(status_code=200, content=prospects)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching prospects: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "detail": f"Error fetching prospects: {str(e)}"}
        )

@app.patch("/lists/{list_id}")
def update_list(
    list_id: str,
    body: UpdateListReq,
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY")
):
    """
    Update a list (rename, etc.)
    """
    try:
        require_api_key(x_api_key)
        
        url = f"{SUPABASE_URL}/rest/v1/{LISTS_TABLE}?id=eq.{list_id}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        # Prepare update data
        update_data = {
            "name": body.name,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        response = requests.patch(url, headers=headers, json=update_data, timeout=10)
        response.raise_for_status()
        updated_list = response.json()
        
        return JSONResponse(status_code=200, content=updated_list[0] if updated_list else {})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating list: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "detail": f"Error updating list: {str(e)}"}
        )

@app.delete("/lists/{list_id}")
def delete_list(list_id: str, x_api_key: Optional[str] = Header(None, alias="X-API-KEY")):
    """
    Delete a list. This will set list_id to NULL for associated prospects (due to ON DELETE SET NULL).
    """
    try:
        require_api_key(x_api_key)
        
        # First check if list exists
        url = f"{SUPABASE_URL}/rest/v1/{LISTS_TABLE}?id=eq.{list_id}&select=id"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        
        check_response = requests.get(url, headers=headers, timeout=10)
        check_response.raise_for_status()
        existing_list = check_response.json()
        
        if not existing_list:
            return JSONResponse(status_code=404, content={"detail": "List not found"})
        
        # Delete all associated prospects first
        prospects_delete_url = f"{SUPABASE_URL}/rest/v1/{PROSPECTS_TABLE}?list_id=eq.{list_id}"
        prospects_delete_response = requests.delete(prospects_delete_url, headers=headers, timeout=10)
        prospects_delete_response.raise_for_status()
        logger.info(f"Deleted all prospects associated with list ID: {list_id}")
        
        # Delete the list
        delete_url = f"{SUPABASE_URL}/rest/v1/{LISTS_TABLE}?id=eq.{list_id}"
        delete_response = requests.delete(delete_url, headers=headers, timeout=10)
        delete_response.raise_for_status()
        
        logger.info(f"Deleted list with ID: {list_id}")
        
        return JSONResponse(status_code=200, content={"ok": True, "message": "List deleted successfully"})
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting list: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "detail": f"Error deleting list: {str(e)}"}
        )

def _update_list_count_after_script(list_id: str):
    """Helper function to update list count after script completes"""
    try:
        logger.info(f"Counting prospects for list_id: {list_id}")
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
        }
        prospects_url = f"{SUPABASE_URL}/rest/v1/{PROSPECTS_TABLE}?list_id=eq.{list_id}&select=id"
        prospects_response = requests.get(prospects_url, headers=headers, timeout=10)
        if prospects_response.status_code == 200:
            prospects = prospects_response.json()
            count = len(prospects)
            
            # Update the list's profile_count
            update_url = f"{SUPABASE_URL}/rest/v1/{LISTS_TABLE}?id=eq.{list_id}"
            update_data = {"profile_count": count, "updated_at": datetime.now(timezone.utc).isoformat()}
            requests.patch(update_url, headers=headers, json=update_data, timeout=10)
            logger.info(f"Updated list {list_id} with profile_count: {count}")
    except Exception as e:
        logger.error(f"Error updating list profile_count: {str(e)}")

@app.post("/lists/populate")
def lists_populate(
    body: PopulateReq, 
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Builds/updates a prospect list by running the user's connect_and_save pipeline.
    Creates a new list entry in li_lists and updates database settings.
    Returns immediately and runs the script in the background.
    """
    # Use print AND logger to ensure visibility
    print("\n" + "=" * 80)
    print("*** ENDPOINT HIT: /lists/populate ***")
    print("=" * 80)
    
    try:
        logger.info("=" * 80)
        logger.info("REQUEST RECEIVED: /lists/populate")
        logger.info(f"Request body: {body}")
        logger.info(f"Request body dict: {body.dict()}")
        logger.info(f"API Key provided: {bool(x_api_key)}")
        logger.info(f"Received populate request: search_url={body.search_url[:50]}..., profile_limit={body.profile_limit}")
        
        print(f"[ENDPOINT] search_url: {body.search_url}")
        print(f"[ENDPOINT] profile_limit: {body.profile_limit}")
        print(f"[ENDPOINT] collect_only: {body.collect_only}")
        print(f"[ENDPOINT] send_note: {body.send_note}")
        print(f"[ENDPOINT] note_text: {body.note_text}")
        
        logger.info("=" * 80)
        
        # Validate API key
        require_api_key(x_api_key)

        # Create a new list entry in li_lists
        list_id = str(uuid.uuid4())
        list_name = f"List from {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}"
        
        list_data = {
            "id": list_id,
            "name": list_name,
            "search_url": body.search_url,
            "profile_limit": body.profile_limit,
            "collect_only": body.collect_only,
            "send_note": body.send_note,
            "note_text": body.note_text if body.note_text else None,
            "profile_count": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }
        
        # Create the list in Supabase
        list_url = f"{SUPABASE_URL}/rest/v1/{LISTS_TABLE}"
        list_response = requests.post(list_url, headers=headers, json=list_data, timeout=10)
        if list_response.status_code not in (200, 201):
            logger.error(f"Failed to create list: {list_response.status_code} - {list_response.text}")
            raise Exception(f"Failed to create list: {list_response.text}")
        
        logger.info(f"Created list with ID: {list_id}")

        # Permanently update settings in the database based on user input
        logger.info("Updating database settings...")
        _update_db_setting("SEARCH_URL", body.search_url)
        _update_db_setting("PROFILE_LIMIT", str(body.profile_limit))
        _update_db_setting("COLLECT_ONLY", "true" if body.collect_only else "false")
        _update_db_setting("SEND_NOTE", "true" if body.send_note else "false")
        
        # Store the list_id temporarily so connect_and_save can use it
        _update_db_setting("CURRENT_LIST_ID", list_id)
        
        # Update CONNECT_NOTE if provided, otherwise keep existing value
        if body.note_text:
            _update_db_setting("CONNECT_NOTE", body.note_text)
        
        logger.info("Database settings updated. Starting script in background...")
        
        # Run the script in a subprocess instead of a thread
        # Playwright requires an event loop which isn't available in regular threads
        logger.info(f"Starting subprocess to run connect_and_save with list_id: {list_id}")
        
        # Get the path to the script
        script_path = Path(__file__).parent.parent / "scripts" / "connect_and_save.py"
        
        # Start the script as a subprocess (not a thread, because Playwright needs an event loop)
        # Playwright cannot run in regular threads due to asyncio requirements
        logger.info(f"About to start subprocess: {sys.executable} {script_path}")
        logger.info(f"Working directory: {Path(__file__).parent.parent}")
        
        try:
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(Path(__file__).parent.parent),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Combine stderr with stdout
                text=True,
                bufsize=1,
                env=os.environ.copy()  # Pass all environment variables
            )
            
            logger.info(f"✓ Subprocess started successfully! PID: {process.pid}, list_id: {list_id}")
            logger.info(f"  Script path: {script_path}")
            logger.info(f"  Headless mode: {os.getenv('HEADLESS', 'false')}")
            
        except Exception as e:
            logger.error(f"❌ FAILED to start subprocess: {str(e)}")
            logger.error(traceback.format_exc())
            raise Exception(f"Failed to start script subprocess: {str(e)}")
        
        # Start a background thread to monitor the process and update count when done
        def monitor_process():
            try:
                # Read output in real-time and log it
                if process.stdout:
                    for line in iter(process.stdout.readline, ''):
                        if line:
                            logger.info(f"[Subprocess {process.pid}] {line.rstrip()}")
                
                process.wait()  # Wait for process to complete
                logger.info(f"Subprocess {process.pid} completed with return code: {process.returncode}")
                
                # Log any remaining output
                if process.stdout:
                    remaining = process.stdout.read()
                    if remaining:
                        logger.info(f"[Subprocess {process.pid} final output] {remaining}")
                
                if process.returncode != 0:
                    logger.error(f"Subprocess {process.pid} exited with error code: {process.returncode}")
                
                if list_id:
                    _update_list_count_after_script(list_id)
                    # Update list timestamp
                    update_url = f"{SUPABASE_URL}/rest/v1/{LISTS_TABLE}?id=eq.{list_id}"
                    update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
                    requests.patch(update_url, headers=headers, json=update_data, timeout=10)
                    logger.info(f"Updated list {list_id} after script completion")
            except Exception as e:
                logger.error(f"Error monitoring subprocess: {str(e)}")
                logger.error(traceback.format_exc())
                # Update timestamp even on error
                try:
                    if list_id:
                        update_url = f"{SUPABASE_URL}/rest/v1/{LISTS_TABLE}?id=eq.{list_id}"
                        update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
                        requests.patch(update_url, headers=headers, json=update_data, timeout=10)
                except:
                    pass
        
        # Use non-daemon thread so it doesn't get killed when main process is idle
        # This is critical for cloud platforms like Render that may kill daemon threads
        monitor_thread = Thread(target=monitor_process, daemon=False)
        monitor_thread.start()
        
        # Return success immediately with list_id
        return JSONResponse(
            status_code=200,
            content={"ok": True, "message": "List generation started in background", "list_id": list_id}
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions - they'll be handled by FastAPI with CORS middleware
        raise
    except Exception as e:
        # Log the full error
        logger.error(f"Error in lists_populate endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return error response with CORS headers ensured
        return JSONResponse(
            status_code=500,
            content={"ok": False, "detail": f"Internal server error: {str(e)}"}
        )

@app.post("/campaigns/send")
def campaigns_send(
    body: SendReq, 
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY")
):
    """
    Sends DMs to connected prospects. Runs the send_messages script in a subprocess
    to avoid event loop conflicts on Windows.
    """
    try:
        require_api_key(x_api_key)

        logger.info(f"Starting campaign send with limit: {body.limit}, list_ids: {body.list_ids}, sender_id: {body.sender_id}")
        
        # Set environment variables for the script
        env = os.environ.copy()
        if body.default_dm:
            env["CAMPAIGN_DM"] = body.default_dm
        if body.list_ids:
            env["CAMPAIGN_LIST_IDS"] = ",".join(body.list_ids)
        if body.sender_id:
            env["CAMPAIGN_SENDER_ID"] = body.sender_id
        env["CAMPAIGN_LIMIT"] = str(body.limit)
        
        # Run the script as a subprocess (not a thread, because Playwright needs an event loop)
        script_path = Path(__file__).parent.parent / "scripts" / "send_messages.py"
        
        if not script_path.exists():
            return JSONResponse(
                status_code=500,
                content={"ok": False, "detail": f"Script not found: {script_path}"}
            )
        
        # Run the script and capture output
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=str(Path(__file__).parent.parent),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        logger.info(f"✓ Subprocess started successfully! PID: {process.pid}")
        
        # Wait for process to complete and capture output
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Campaign send script failed with return code {process.returncode}")
            logger.error(f"Stderr: {stderr}")
            return JSONResponse(
                status_code=500,
                content={"ok": False, "detail": f"Script execution failed: {stderr[:200]}"}
            )
        
        # Parse output to extract results if available
        # For now, return success since the script updates the database directly
        logger.info(f"Campaign send completed successfully")
        logger.info(f"Stdout: {stdout[-500:]}")  # Last 500 chars of output
        
        # Try to extract stats from output if available
        attempted = 0
        sent = 0
        errors = 0
        
        # Look for pattern in stdout like "sent X messages" or similar
        import re
        sent_match = re.search(r'(\d+)\s+messages?\s+sent', stdout, re.IGNORECASE)
        if sent_match:
            sent = int(sent_match.group(1))
        
        # Return success response
        return JSONResponse(
            status_code=200,
            content={
                "ok": True,
                "attempted": attempted,
                "sent": sent,
                "errors": errors,
                "message": "Campaign started. Messages are being sent in the background."
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions - they'll be handled by FastAPI with CORS middleware
        raise
    except Exception as e:
        logger.error(f"Error in campaigns_send endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"ok": False, "detail": f"Internal server error: {str(e)}"}
        )

@app.post("/connections/verify")
def connections_verify(
    body: VerifyReq, 
    x_api_key: Optional[str] = Header(None, alias="X-API-KEY")
):
    """
    Re-check profiles that were invited but not yet marked 'connected'.
    Runs the verify_connections script in a subprocess to avoid event loop conflicts on Windows.
    """
    try:
        require_api_key(x_api_key)

        logger.info(f"Starting verify connections with limit: {body.limit}")
        
        # Run the script as a subprocess (not a thread, because Playwright needs an event loop)
        # This avoids the NotImplementedError on Windows when trying to create subprocesses
        # in FastAPI's async context
        script_path = Path(__file__).parent.parent / "scripts" / "verify_connections.py"
        
        if not script_path.exists():
            return JSONResponse(
                status_code=500,
                content={"ok": False, "detail": f"Script not found: {script_path}"}
            )
        
        # Set environment variable for limit (the script can read this)
        env = os.environ.copy()
        env["VERIFY_LIMIT"] = str(body.limit)
        
        # Run the script and capture output
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=str(Path(__file__).parent.parent),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        logger.info(f"✓ Subprocess started successfully! PID: {process.pid}")
        
        # Wait for process to complete and capture output
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"Verify connections script failed with return code {process.returncode}")
            logger.error(f"Stderr: {stderr}")
            return JSONResponse(
                status_code=500,
                content={"ok": False, "detail": f"Script execution failed: {stderr[:200]}"}
            )
        
        # Parse output if needed, or just return success
        # The script updates the database directly, so we just need to indicate success
        logger.info(f"Verify connections completed successfully")
        logger.info(f"Stdout: {stdout[-500:]}")  # Last 500 chars of output
        
        # Return success response
        # Note: The actual counts would need to be tracked differently if needed
        # For now, we return success and the frontend can refresh the lists
        return JSONResponse(
            status_code=200,
            content={"ok": True, "checked": body.limit, "connected": 0, "message": "Verification completed. Check your lists for updated connection statuses."}
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions - they'll be handled by FastAPI with CORS middleware
        raise
    except Exception as e:
        logger.error(f"Error in connections_verify endpoint: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"ok": False, "detail": f"Internal server error: {str(e)}"}
        )

