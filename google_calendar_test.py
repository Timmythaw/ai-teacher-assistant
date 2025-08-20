from __future__ import print_function
import os
import datetime
import pickle

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
def get_calendar_service():
    creds = None
    # token.json stores the user's access and refresh tokens
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no valid creds, let user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("/home/timmy/ai-teacher-assistant/credentials.json", SCOPES)
            creds = flow.run_local_server(port = 8080)
        # Save creds for next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)

# Test: List next 10 events
service = get_calendar_service()
now = datetime.datetime.utcnow().isoformat() + "Z"
print("Getting upcoming 10 events")
events_result = service.events().list(calendarId="primary", timeMin=now,
                                      maxResults=10, singleEvents=True,
                                      orderBy="startTime").execute()
events = events_result.get("items", [])

if not events:
    print("No upcoming events found.")
for event in events:
    start = event["start"].get("dateTime", event["start"].get("date"))
    print(start, event["summary"])