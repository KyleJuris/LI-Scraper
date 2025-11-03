# upload_json.py
# Upload storage_state.json to Supabase (table: li_senders)

import json
import requests
from dotenv import load_dotenv
import os

# Load .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
TABLE_NAME = os.getenv("SUPABASE_SENDERS_TABLE", "li_senders")

JSON_PATH = "storage_state.json"
SENDER_NAME = "linkedin_sender_1"  # Supabase will auto-generate UUID

with open(JSON_PATH, "r", encoding="utf-8") as f:
    storage_state = json.load(f)

url = f"{SUPABASE_URL}/rest/v1/{TABLE_NAME}"
headers = {
    "apikey": SUPABASE_ANON_KEY,
    "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    "Content-Type": "application/json",
}

payload = {
    "name": SENDER_NAME,
    "storage_state": storage_state
}

r = requests.post(url, headers=headers, json=payload)
print(r.status_code, r.text)
