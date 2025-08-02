import streamlit as st
import json
import datetime
import pandas as pd
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from streamlit_calendar import calendar
from st_aggrid import AgGrid, GridOptionsBuilder

# ---- CONFIG ----
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
st.set_page_config(page_title="📅 St. Cloud Calendar Viewer", layout="wide")

# ---- HEADER ----
st.title("📅 St. Cloud Google Calendar Viewer")
st.markdown("""
Upload your Google Calendar `credentials.json`, authorize the app, and view your upcoming events in both a calendar and table view.

🔒 OAuth is handled securely. Your data is not stored.
""")

# ---- SIDEBAR ----
st.sidebar.header("🔐 Upload OAuth Credentials")
uploaded_file = st.sidebar.file_uploader("Upload Google OAuth `credentials.json`", type="json")

# ---- AUTH FUNCTION (streamlit cloud safe) ----
def authenticate_with_google(credentials_data):
    with open("temp_credentials.json", "w") as f:
        json.dump(credentials_data, f)
    flow = InstalledAppFlow.from_client_secrets_file("temp_credentials.json", SCOPES)
    creds = flow.run_console()  # Use console-based auth for Streamlit Cloud
    return creds

# ---- FETCH EVENTS ----
def fetch_calendar_events(creds):
    service = build('calendar', 'v3', credentials=creds)
    now = datetime.datetime.utcnow().isoformat() + 'Z'
    result = service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=50, singleEvents=True,
        orderBy='startTime'
    ).execute()
    return result.get('items', [])

# ---- FORMAT EVENTS FOR DISPLAY ----
def format_for_calendar(events):
    return [
        {
            "title": e.get("summary", "No Title"),
            "start": e["start"].get("dateTime", e["start"].get("date")),
            "end": e["end"].get("dateTime", e["end"].get("date")),
        }
        for e in events
    ]

def format_for_table(events):
    return pd.DataFrame([
        {
            "Title": e.get("summary", "No Title"),
            "Start": e["start"].get("dateTime", e["start"].get("date")),
            "End": e["end"].get("dateTime", e["end"].get("date")),
            "Location": e.get("location", ""),
            "Description": e.get("description", "")
        }
        for e in events
    ])

# ---- MAIN APP LOGIC ----
if uploaded_file:
    try:
        creds_data = json.load(uploaded_file)

        if "installed" not in creds_data:
            st.error("❌ Invalid credentials file. Must be a Desktop OAuth Client.")
        else:
            creds = authenticate_with_google(creds_data)
            events = fetch_calendar_events(creds)

            if events:
                st.success(f"✅ Loaded {len(events)} events")

                # 📅 Calendar View
                st.subheader("📅 Calendar View")
                calendar_options = {
                    "initialView": "dayGridMonth",
                    "editable": False,
                    "selectable": False,
                    "height": 650
                }
                calendar(events=format_for_calendar(events), options=calendar_options)

                # 📋 Table View
                st.subheader("📋 Event Table")
                df = format_for_table(events)
                gb = GridOptionsBuilder.from_dataframe(df)
                gb.configure_pagination()
                gb.configure_default_column(filter=True)
                AgGrid(df, gridOptions=gb.build(), theme="alpine", height=400)

            else:
                st.info("No upcoming events found.")
    except Exception as e:
        st.error(f"❌ Authentication failed: {e}")
else:
    st.info("👈 Upload your Google OAuth credentials JSON file to begin.")

