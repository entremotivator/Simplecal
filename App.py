import streamlit as st
import datetime
import os
import json
import tempfile
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from streamlit_calendar import calendar

# Set the scope
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

st.set_page_config(page_title="📅 Google Calendar Viewer", layout="wide")
st.title("📅 Live Google Calendar Viewer")

# Sidebar upload
st.sidebar.header("🔐 Upload Google OAuth JSON")
uploaded_file = st.sidebar.file_uploader("Upload your `client_secret.json`", type=["json"])

if uploaded_file:
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name

        # Validate if it's Desktop OAuth
        with open(tmp_path) as f:
            creds_json = json.load(f)

        if creds_json.get("installed") is None:
            st.error("❌ Invalid credentials file. Must be a Desktop OAuth Client.")
        else:
            # Authenticate
            flow = InstalledAppFlow.from_client_secrets_file(tmp_path, SCOPES)
            creds = flow.run_local_server(port=0)
            service = build('calendar', 'v3', credentials=creds)

            # Fetch events
            now = datetime.datetime.utcnow().isoformat() + 'Z'
            events_result = service.events().list(calendarId='primary', timeMin=now,
                                                  maxResults=20, singleEvents=True,
                                                  orderBy='startTime').execute()
            events = events_result.get('items', [])

            if not events:
                st.warning("No upcoming events found.")
            else:
                st.success(f"✅ Fetched {len(events)} upcoming event(s) from your Google Calendar.")

                # Convert to fullcalendar format
                calendar_events = []
                for event in events:
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    end = event['end'].get('dateTime', event['end'].get('date'))
                    calendar_events.append({
                        "title": event.get("summary", "No Title"),
                        "start": start,
                        "end": end,
                    })

                # Show in calendar
                calendar_options = {
                    "initialView": "dayGridMonth",
                    "editable": False,
                    "selectable": True,
                    "height": "600px"
                }

                calendar(events=calendar_events, options=calendar_options)

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
else:
    st.info("👈 Upload your Google Calendar OAuth JSON file in the sidebar.")



