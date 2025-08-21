import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pickle
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from core.logger import logger

SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/forms.responses.readonly",
    "https://www.googleapis.com/auth/drive.file"
]

def get_google_service(api: str, version: str,
                       credentials_path="/home/timmy/ai-teacher-assistant/credentials.json",
                       token_path="/home/timmy/ai-teacher-assistant/token.pickle"):
    """
    Authenticate and return a Google API service client with error handling.
    """
    creds = None
    try:
        if os.path.exists(token_path):
            with open(token_path, "rb") as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                logger.info("Google credentials refreshed successfully.")
            else:
                if not os.path.exists(credentials_path):
                    raise FileNotFoundError(
                        f"Missing {credentials_path}. Please download from Google Cloud Console."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=8080)
                logger.info("Google OAuth flow completed successfully.")

            # Save token for reuse
            with open(token_path, "wb") as token:
                pickle.dump(creds, token)
                logger.info("Google credentials cached at %s", token_path)

        return build(api, version, credentials=creds)

    except HttpError as e:
        logger.error("Google API HttpError: %s", e)
        raise
    except Exception as e:
        logger.error("Google auth failed: %s", e, exc_info=True)
        raise
