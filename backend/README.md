# LinkedIn Automation API (Render)

A thin FastAPI wrapper around three existing scripts:
- `scripts/connect_and_save.py`
- `scripts/send_messages.py`
- `scripts/verify_connections.py`

## Endpoints

- `GET /health` → `{ ok: true }`
- `POST /lists/populate`  
  Body:
  ```json
  {
    "search_url": "https://www.linkedin.com/search/results/people/?keywords=...",
    "profile_limit": 50,
    "collect_only": true,
    "send_note": false,
    "note_text": "",
    "sender_rotation": "round_robin"
  }
  ```

- `POST /campaigns/send`
  Body:
  ```json
  {
    "limit": 20,
    "default_dm": "Optional override"
  }
  ```

- `POST /connections/verify`
  Body:
  ```json
  {
    "limit": 50
  }
  ```

Protect calls by sending header `X-API-KEY: <BACKEND_API_KEY>`.
If `BACKEND_API_KEY` is unset, the API is open (dev mode only).

