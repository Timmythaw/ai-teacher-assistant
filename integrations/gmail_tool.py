# tools/gmail_tool.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flask import session
import base64
import mimetypes
import time
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Iterable, Optional, Tuple, Dict, Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from core.logger import logger


SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


def _guess_mime_type(path: str) -> Tuple[str, str]:
    """Guess MIME type for a file path."""
    ctype, encoding = mimetypes.guess_type(path)
    if ctype is None or encoding is not None:
        ctype = "application/octet-stream"
    maintype, subtype = ctype.split("/", 1)
    return maintype, subtype

def get_gmail_service(
    scopes: Iterable[str] = SCOPES,
):
    """
    Build and return a Gmail API service client using OAuth credentials
    obtained in the /auth/callback flow.

    Expects session["credentials"] to be set by auth_routes.callback.
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
            scopes=sess_creds.get("scopes") or scopes,
        )

        # Refresh if expired
        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                logger.info("Gmail credentials refreshed successfully")

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
                raise RuntimeError("Invalid Gmail credentials and no refresh token available.")

        service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail service initialized successfully (session-based)")
        return service

    except Exception as e:
        logger.error("Gmail authentication failed (session-based): %s", e, exc_info=True)
        raise RuntimeError(f"Gmail authentication failed: {e}")


def get_sender_address(service) -> str:
    """
    Get the authenticated user's email address.
    
    Args:
        service: Gmail API service client
        
    Returns:
        User's email address
        
    Raises:
        RuntimeError: If profile retrieval fails
    """
    try:
        profile = service.users().getProfile(userId="me").execute()
        email = profile.get("emailAddress")
        if not email:
            raise RuntimeError("No email address found in user profile")
        
        logger.debug("Retrieved sender email: %s", email)
        return email
        
    except Exception as e:
        logger.error("Failed to get sender address: %s", e)
        raise RuntimeError(f"Failed to get sender address: {e}")


def create_message(
    *,
    to: str,
    subject: str,
    body_html: Optional[str] = None,
    body_text: Optional[str] = None,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    attachments: Optional[Iterable[str]] = None,
    sender: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a MIME message for Gmail.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body_html: HTML body content (optional)
        body_text: Plain text body content (optional)
        cc: CC recipients (comma-separated)
        bcc: BCC recipients (comma-separated)
        attachments: Iterable of file paths
        sender: Sender email address
        
    Returns:
        Dict with 'raw' field containing base64-encoded message
        
    Raises:
        FileNotFoundError: If attachment file not found
        ValueError: If message creation fails
    """
    try:
        logger.debug("Creating email message to: %s, subject: %s", to, subject)
        
        if attachments:
            msg = MIMEMultipart()
            alt = MIMEMultipart("alternative")
            msg.attach(alt)
            if body_text:
                alt.attach(MIMEText(body_text, "plain"))
            if body_html:
                alt.attach(MIMEText(body_html, "html"))
        else:
            if body_html:
                msg = MIMEText(body_html, "html")
            else:
                msg = MIMEText(body_text or "", "plain")

        # Ensure we have a container to set headers cleanly
        if not isinstance(msg, MIMEMultipart):
            container = MIMEMultipart("alternative")
            container.attach(msg)
            msg = container

        # Set headers
        msg["To"] = to
        msg["Subject"] = subject
        if sender:
            msg["From"] = sender
        if cc:
            msg["Cc"] = cc
        if bcc:
            msg["Bcc"] = bcc

        # Add attachments
        if attachments:
            for path in attachments:
                path = path.strip()
                if not path:
                    continue
                    
                if not os.path.exists(path):
                    raise FileNotFoundError(f"Attachment not found: {path}")
                    
                try:
                    maintype, subtype = _guess_mime_type(path)
                    with open(path, "rb") as f:
                        part = MIMEBase(maintype, subtype)
                        part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition", "attachment", filename=os.path.basename(path)
                    )
                    msg.attach(part)
                    logger.debug("Added attachment: %s", path)
                except Exception as e:
                    logger.warning("Failed to add attachment %s: %s", path, e)

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        logger.debug("Email message created successfully")
        return {"raw": raw, "bcc": bcc}
        
    except Exception as e:
        logger.error("Failed to create email message: %s", e)
        raise ValueError(f"Failed to create email message: {e}")


def send_message(service, *, user_id: str = "me", message: Dict[str, Any], max_retries: int = 5):
    """
    Send an email with exponential backoff on rate limits.
    
    Args:
        service: Gmail API service client
        user_id: Gmail user ID (default: "me")
        message: Message dict with 'raw' field
        max_retries: Maximum retry attempts
        
    Returns:
        Gmail API response
        
    Raises:
        ValueError: If message format is invalid
        RuntimeError: If sending fails after retries
    """
    try:
        if not message or "raw" not in message:
            raise ValueError("Message must contain 'raw' field")
            
        logger.debug("Sending email message")
        
        for attempt in range(max_retries):
            try:
                response = (
                    service.users()
                    .messages()
                    .send(userId=user_id, body={"raw": message["raw"]})
                    .execute()
                )
                logger.info("Email sent successfully with ID: %s", response.get("id"))
                return response
                
            except HttpError as e:
                status = getattr(e, "status_code", None) or getattr(getattr(e, "resp", None), "status", None)
                if status in [403, 429]:  # Rate limited
                    sleep_s = min(30, (1.5 ** attempt))
                    logger.warning("Rate-limited (attempt %d/%d). Sleeping %.1fs…", 
                                 attempt + 1, max_retries, sleep_s)
                    time.sleep(sleep_s)
                    continue
                else:
                    logger.error("Gmail API error: %s", e)
                    raise
                    
        # If we get here, all retries failed
        raise RuntimeError(f"Failed to send email after {max_retries} attempts")
        
    except Exception as e:
        logger.error("Failed to send email: %s", e)
        raise


def create_draft(service, *, user_id: str = "me", message: Dict[str, Any]):
    """
    Create a draft email.
    
    Args:
        service: Gmail API service client
        user_id: Gmail user ID (default: "me")
        message: Message dict with 'raw' field
        
    Returns:
        Gmail API response
        
    Raises:
        ValueError: If message format is invalid
        RuntimeError: If draft creation fails
    """
    try:
        if not message or "raw" not in message:
            raise ValueError("Message must contain 'raw' field")
            
        logger.debug("Creating email draft")
        
        response = (
            service.users()
            .drafts()
            .create(userId=user_id, body={"message": {"raw": message["raw"]}})
            .execute()
        )
        
        logger.info("Email draft created successfully with ID: %s", response.get("id"))
        return response
        
    except Exception as e:
        logger.error("Failed to create email draft: %s", e)
        raise RuntimeError(f"Failed to create email draft: {e}")


# Test code - only run if this file is executed directly
if __name__ == "__main__":
    try:
        print("Testing Gmail tool...")
        # Note: This requires valid credentials.json to work
        print("Gmail tool functions loaded successfully")
        
    except Exception as e:
        print(f"Error testing Gmail tool: {e}")