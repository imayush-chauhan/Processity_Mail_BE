"""Environment-backed settings for the Processity mail backend.

Single source of truth for config. Mirrors the dotenv pattern used across the
sibling FastAPI backends (razor_apis, talk_to_clinician).
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Google returns extra/reordered scopes (adds `email` alongside userinfo.email when
# `openid` is present); relax oauthlib's exact-scope check so /auth/google/callback
# doesn't 500 with "Scope has changed". setdefault lets an explicit env var still win.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

# --- Google OAuth / Gmail ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv(
    "GOOGLE_REDIRECT_URI", "http://localhost:10000/auth/google/callback"
)

# Scopes: read mail, send mail, and modify labels (mark read/unread).
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

# Where OAuth credentials are cached. Single-user store for the hiring demo;
# a production build would use per-user encrypted storage.
TOKEN_PATH = os.getenv("TOKEN_PATH", "token.json")

# --- Anthropic (assistant) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# House convention (see razor_apis/services/claude.py). Swap to a larger model
# if you need stronger multi-step tool planning.
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

# --- App ---
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "10"))
FRONTEND_URL = os.getenv("FRONTEND_URL", "")


def require_google() -> None:
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        raise RuntimeError(
            "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET not configured. See .env.example."
        )
