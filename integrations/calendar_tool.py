import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import datetime
from googleapiclient.errors import HttpError
from core.google_client import get_google_service
from core.logger import logger

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

def fetch_calendar_events(days_ahead: int = 7) -> list:
    """
    Fetch upcoming events from Google Calendar within N days.
    Returns a list of event dicts. Handles errors gracefully.
    """
    try:
        logger.info("Fetching calendar events for next %d days", days_ahead)

        service = get_google_service("calendar", "v3")

        now = datetime.datetime.utcnow().isoformat() + "Z"
        end = (datetime.datetime.utcnow() + datetime.timedelta(days=days_ahead)).isoformat() + "Z"

        events_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            timeMax=end,
            maxResults=50,
            singleEvents=True,
            orderBy="startTime"
        ).execute()

        events = events_result.get("items", [])
        logger.info("Retrieved %d events from Google Calendar", len(events))
        return events

    except HttpError as e:
        logger.error("Google Calendar API error: %s", e)
        return {"error": f"Google Calendar API error: {e}"}
    except Exception as e:
        logger.error("Failed to fetch calendar events: %s", e, exc_info=True)
        return {"error": f"Failed to fetch calendar events: {e}"}

#events = fetch_calendar_events(days_ahead=7)