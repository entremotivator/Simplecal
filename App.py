import streamlit as st
import json
import os
import datetime
import pandas as pd
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from st_aggrid import AgGrid, GridOptionsBuilder
from streamlit_calendar import calendar

# ---------- CONFIG ----------
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
st.set_page_config(page_title="📆 Google Calendar Viewer", layout="wide")

# ---------- TITLE ----------
st.title("📅 Live Google Calendar Viewer with Streamlit Calendar")

# ---------- SIDEBAR ----------
st.sidebar.header("🔐 Google API Setup")
uploaded_file = st.sidebar.file_uploader("Upload `credentials.json`", type="json")

# ---------- AUTH ----------
def authenticate(creds_path):
    flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
    creds = flow.run_local_server(port=0)
    return creds

# ---------- FETCH EVENTS ----------
def get_calendar_events(creds):
    service = build('calendar', 'v3', credentials=creds)
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    result = service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=50, singleEvents=True,
        orderBy='startTime').execute()
    return result.get('items', [])

# ---------- FORMAT FOR CALENDAR ----------
def format_for_calendar(events):
    cal_events = []
    for e in events:
        title = e.get('summary', 'Untitled')
        start = e['start'].get('dateTime', e['start'].get('date'))
        end = e['end'].get('dateTime', e['end'].get('date'))
        cal_events.append({
            "title": title,
            "start": start,
            "end": end
        })
    return cal_events

# ---------- FORMAT FOR TABLE ----------
def format_for_table(events):
    rows = []
    for e in events:
        rows.append({
            "Title": e.get('summary', 'Untitled'),
            "Start": e['start'].get('dateTime', e['start'].get('date')),
            "End": e['end'].get('dateTime', e['end'].get('date')),
            "Location": e.get('location', ''),
            "Description": e.get('description', '')
        })
    return pd.DataFrame(rows)

# ---------- MAIN LOGIC ----------
if uploaded_file:
    with open("temp_credentials.json", "wb") as f:
        f.write(uploaded_file.read())

    try:
        creds = authenticate("temp_credentials.json")
        events = get_calendar_events(creds)

        if events:
            st.success(f"✅ Loaded {len(events)} events")

            # ---------- CALENDAR VIEW ----------
            st.subheader("📆 Calendar View")
            calendar_events = format_for_calendar(events)
            calendar_options = {
                "initialView": "dayGridMonth",
                "editable": False,
                "selectable": False,
                "height": 650
            }
            calendar(events=calendar_events, options=calendar_options)

            # ---------- TABLE VIEW ----------
            st.subheader("📋 Event Table")
            df = format_for_table(events)
            gb = GridOptionsBuilder.from_dataframe(df)
            gb.configure_pagination()
            gb.configure_default_column(filter=True)
            AgGrid(df, gridOptions=gb.build(), theme="alpine")

        else:
            st.warning("No upcoming events found.")

    except Exception as e:
        st.error(f"Authentication failed: {e}")

else:
    st.info("👈 Upload your Google Calendar `credentials.json` file to begin.")
