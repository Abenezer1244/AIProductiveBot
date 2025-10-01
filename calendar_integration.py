from __future__ import annotations
import os
from typing import Optional
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
SCOPES = ["https://www.googleapis.com/auth/calendar"]
def _creds():
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN")
    if not (client_id and client_secret and refresh_token):
        raise RuntimeError("Missing Google OAuth env vars")
    return Credentials(None, refresh_token=refresh_token, token_uri="https://oauth2.googleapis.com/token",
                       client_id=client_id, client_secret=client_secret, scopes=SCOPES)
def create_event(summary: str, start_iso: str, end_iso: str, timezone: str = "UTC", calendar_id: Optional[str] = None):
    calendar_id = calendar_id or os.getenv("GOOGLE_CALENDAR_ID", "primary")
    service = build("calendar", "v3", credentials=_creds(), cache_discovery=False)
    body = {"summary": summary, "start": {"dateTime": start_iso, "timeZone": timezone},
            "end": {"dateTime": end_iso, "timeZone": timezone}}
    event = service.events().insert(calendarId=calendar_id, body=body).execute()
    return event.get("htmlLink", "")
