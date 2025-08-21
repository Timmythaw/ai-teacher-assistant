import datetime
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

def get_calendar_service():
    creds = Credentials.from_authorized_user_file("/home/timmy/ai-teacher-assistant/token.json", SCOPES)
    return build("calendar", "v3", credentials=creds)

def fetch_calendar_events(days_ahead: int = 7, service=None):
    """Fetch upcoming events from Google Calendar within N days."""
    if service is None:
        service = get_calendar_service()
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
    return events