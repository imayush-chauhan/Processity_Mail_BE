"""OAuth credential store + authorized Gmail service factory.

Single-user token cache (``token.json``) — right-sized for the hiring demo.
The OAuth *flow* itself lives in ``routers/auth.py``; this module only persists
credentials and hands back a ready-to-use Gmail API client.
"""
import json
import os
import threading

from fastapi import HTTPException
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from core import config

_lock = threading.Lock()


def save_credentials(creds: Credentials) -> None:
    """Persist credentials (incl. refresh token) to disk."""
    with _lock:
        with open(config.TOKEN_PATH, "w") as f:
            f.write(creds.to_json())


def load_credentials() -> Credentials | None:
    """Load cached credentials, refreshing them if expired. None if not connected."""
    if not os.path.exists(config.TOKEN_PATH):
        return None
    with open(config.TOKEN_PATH, "r") as f:
        data = json.load(f)
    creds = Credentials.from_authorized_user_info(data, config.GMAIL_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        save_credentials(creds)
    return creds


def is_connected() -> bool:
    try:
        return load_credentials() is not None
    except Exception:
        return False


def get_gmail_service():
    """Return an authorized Gmail API service, or 401 if the user hasn't connected."""
    creds = load_credentials()
    if creds is None or not creds.valid:
        raise HTTPException(
            status_code=401,
            detail="Gmail not connected. Visit /auth/google/login to authorize.",
        )
    # cache_discovery=False avoids noisy warnings / file writes on serverless hosts.
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def get_optional_gmail_service():
    """Like get_gmail_service but returns None instead of raising when not connected.

    Lets the assistant handle compose/navigate requests even before Gmail is linked,
    degrading only the data-backed tools (search/open/reply).
    """
    try:
        return get_gmail_service()
    except HTTPException:
        return None
    except Exception:
        return None
