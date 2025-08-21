import streamlit as st
import datetime
import json
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import sys
import os

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import existing functions
from tools.calendar_tool import fetch_calendar_events
from agents.timetable_agent import timetable_agent

# Google API settings
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CLIENT_SECRETS_FILE = "credentials.json"

st.title("📅 AI Teaching Assistant – Timetable Agent")

# Store session credentials
if "credentials" not in st.session_state:
    st.session_state["credentials"] = None

# Step 1: Google Login
# The following block is commented out to disable Google login functionality.
# if not st.session_state.credentials:
#     st.info("Please connect your Google account to continue.")
#     flow = Flow.from_client_config(client_config, scopes=["https://www.googleapis.com/auth/userinfo.email"])
#
#     auth_url, _ = flow.authorization_url(prompt="consent")
#     st.markdown(f"[🔑 Login with Google]({auth_url})")
client_config = {
    "installed": {
        "client_id": st.secrets["google"]["GOOGLE_CLIENT_ID"],
        "client_secret": st.secrets["google"]["GOOGLE_CLIENT_SECRET"],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost:8501/"],
    }
}

if st.session_state["credentials"] is None:
    if st.button("🔑 Login with Google"):
#        flow = InstalledAppFlow.from_client_secrets_file(
#           "credentials.json",  # this file is required only once in dev
#           SCOPES
#        )
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
        creds = flow.run_local_server(port=8080)
        st.session_state["credentials"] = creds.to_json()
        st.success("✅ Google account connected. Please refresh the page.")

else:
    creds = Credentials.from_authorized_user_info(json.loads(st.session_state["credentials"]), SCOPES)
    service = build("calendar", "v3", credentials=creds)

    # Step 2: Fetch events using the existing function
    try:
        events = fetch_calendar_events(days_ahead=7, service=service)
        
        st.subheader("📌 Upcoming Events (next 7 days)")
        if not events:
            st.write("No upcoming events found.")
        else:
            for e in events:
                start = e["start"].get("dateTime", e["start"].get("date"))
                st.write(f"- {start} → {e.get('summary','(No Title)')}")

        # Step 3: Use the existing timetable_agent function
        if st.button("Suggest Lesson Times"):
            user_request = "Suggest 3 suitable 1-hour lesson slots in the next week for Algebra class during weekdays 9am–5pm."
            
            with st.spinner("AI is analyzing your calendar and suggesting times..."):
                suggestion = timetable_agent(user_request)
            
            st.subheader("✨ Suggested Lesson Times")
            st.write(suggestion)
            
    except Exception as e:
        st.error(f"Error fetching calendar events: {str(e)}")
        st.info("Please ensure your Google credentials are properly configured.")
