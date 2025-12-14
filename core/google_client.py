import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import session
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from core.logger import logger


def get_google_service(api: str, version: str):
    """
    Build and return a Google API service client using OAuth credentials
    obtained from the web OAuth flow (stored in Flask session).
    
    This replaces the old local OAuth flow with session-based web OAuth.
    
    Args:
        api: Google API name (e.g., "gmail", "calendar", "forms")
        version: API version (e.g., "v1", "v3")
        
    Returns:
        Google API service client
        
    Raises:
        RuntimeError: If no credentials in session or authentication fails
    """
    try:
        # Get credentials from session (set in auth_routes.callback)
        sess_creds = session.get("credentials")
        if not sess_creds:
            raise RuntimeError("No OAuth credentials in session; user must log in first.")

        # Reconstruct Credentials object
        creds = Credentials(
            token=sess_creds.get("token"),
            refresh_token=sess_creds.get("refresh_token"),
            token_uri=sess_creds.get("token_uri"),
            client_id=sess_creds.get("client_id"),
            client_secret=sess_creds.get("client_secret"),
            scopes=sess_creds.get("scopes"),
        )

        # Refresh if expired
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                logger.info("%s credentials refreshed successfully", api.capitalize())

                # Save refreshed token back to session
                session["credentials"] = {
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": creds.scopes,
                }
            else:
                raise RuntimeError(f"Invalid {api} credentials and no refresh token available.")

        service = build(api, version, credentials=creds)
        logger.info("%s service initialized successfully (session-based)", api.capitalize())
        return service

    except Exception as e:
        logger.error("%s authentication failed (session-based): %s", api.capitalize(), e, exc_info=True)
        raise RuntimeError(f"{api.capitalize()} authentication failed: {e}")
