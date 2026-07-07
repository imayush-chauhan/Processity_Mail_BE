"""Google OAuth 2.0 flow for Gmail access.

    /auth/google/login    -> redirect user to Google consent
    /auth/google/callback -> exchange code, cache credentials
    /auth/status          -> is Gmail connected?

Single-user token store (see core/gmail_client.py). ``prompt=consent`` +
``access_type=offline`` guarantees a refresh token so the demo keeps working
after the access token expires.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from google_auth_oauthlib.flow import Flow

from core import config, gmail_client

router = APIRouter(prefix="/auth", tags=["auth"])


def _build_flow() -> Flow:
    config.require_google()
    client_config = {
        "web": {
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [config.GOOGLE_REDIRECT_URI],
        }
    }
    return Flow.from_client_config(
        client_config,
        scopes=config.GMAIL_SCOPES,
        redirect_uri=config.GOOGLE_REDIRECT_URI,
        # Confidential client: the client_secret secures the token exchange, so PKCE is
        # optional. Disable it — login and callback build separate Flow objects, so an
        # auto-generated code_verifier would be lost between them ("Missing code verifier").
        autogenerate_code_verifier=False,
    )


@router.get("/google/login")
def google_login():
    flow = _build_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return RedirectResponse(auth_url)


@router.get("/google/callback")
def google_callback(request: Request):
    error = request.query_params.get("error")
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    code = request.query_params.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    flow = _build_flow()
    try:
        flow.fetch_token(code=code)
        gmail_client.save_credentials(flow.credentials)
    except Exception as e:
        # Surface the real cause (scope mismatch, invalid_grant, redirect_uri_mismatch, ...)
        # instead of an opaque 500 so OAuth failures are diagnosable at a glance.
        raise HTTPException(status_code=400, detail=f"OAuth token exchange failed: {e}")

    if config.FRONTEND_URL:
        return RedirectResponse(f"{config.FRONTEND_URL}?connected=1")
    return {"status": "connected", "message": "Gmail authorized. You can close this tab."}


@router.get("/status")
def auth_status():
    return {"connected": gmail_client.is_connected()}
