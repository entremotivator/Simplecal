import streamlit as st
import json
import datetime
import pandas as pd
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from st_aggrid import AgGrid, GridOptionsBuilder
from streamlit_calendar import calendar

# Set Streamlit page config
st.set_page_config(page_title="📆 Google Calendar Viewer", layout="wide")
st.title("📅 Live Google Calendar Viewer with Calendar View")

# Sidebar file upload
st.sidebar.header("🔐 Google API Setup")
uploaded_file = st.sidebar.file_uploader("Upload Google OAuth Credentials JSON", type="json")

# Scopes for Google Calendar read-only
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

def authenticate_with_google(credentials_data):
    # Save temporary credentials file
    with open("temp_google_creds.json", "w") as temp_file:
        json.dump(credentials_data, temp_file)
    # Run OAuth flow using temporary file
    flow = InstalledAppFlow.from_client_secrets_file("temp_google_creds.json", SCOPES)
    creds = flow.run_local_server(port=0)
    return creds

def fetch_calendar_events(creds):
    service = build('calendar', 'v3', credentials=creds)
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=50, singleEvents=True,
        orderBy='startTime'
    ).execute()
    return events_result.get('items', [])

def format_for_calendar(events):
    cal_events = []
    for e in events:
        start = e['start'].get('dateTime', e['start'].get('date'))
        end = e['end'].get('dateTime', e['end'].get('date'))
        cal_events.append({
            "title": e.get('summary', 'No Title'),
            "start": start,
            "end": end
        })
    return cal_events

def format_for_table(events):
    table_data = []
    for e in events:
        table_data.append({
            "Title": e.get('summary', 'No Title'),
            "Start": e['start'].get('dateTime', e['start'].get('date')),
            "End": e['end'].get('dateTime', e['end'].get('date')),
            "Location": e.get('location', ''),
            "Description": e.get('description', '')
        })
    return pd.DataFrame(table_data)

# Main logic
if uploaded_file:
    try:
        credentials_data = json.load(uploaded_file)

        # Make sure this is the correct type of credentials
        if "installed" not in credentials_data:
            st.error("❌ This file does not contain 'installed' credentials. Make sure it's an 'OAuth Client ID' for a desktop app.")
        else:
            creds = authenticate_with_google(credentials_data)
            events = fetch_calendar_events(creds)

            if events:
                st.success(f"✅ Loaded {len(events)} calendar events")

                # 📆 Calendar view
                st.subheader("📆 Calendar View")
                calendar_events = format_for_calendar(events)
                calendar_options = {
                    "initialView": "dayGridMonth",
                    "editable": False,
                    "selectable": False,
                    "height": 650
                }
                calendar(events=calendar_events, options=calendar_options)

                # 📋 Table view
                st.subheader("📋 Event Table")
                df = format_for_table(events)
                gb = GridOptionsBuilder.from_dataframe(df)
                gb.configure_pagination()
                gb.configure_default_column(filter=True)
                AgGrid(df, gridOptions=gb.build(), theme="alpine")

            else:
                st.info("No upcoming events found in your calendar.")

    except Exception as e:
        st.error(f"❌ Authentication failed: {e}")

else:
    st.info("👈 Upload your valid Google OAuth credentials JSON to continue.")
