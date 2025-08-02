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

# Configure Streamlit page
st.set_page_config(page_title="📅 Google Calendar Viewer", layout="wide")
st.title("📅 Live Google Calendar Viewer")

def fetch_calendar_events(service, max_results=50):
    """Fetch events from Google Calendar"""
    try:
        # Get current time
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        
        # Fetch events
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        return events
        
    except Exception as e:
        st.error(f"❌ Error fetching calendar events: {str(e)}")
        return []

def convert_to_calendar_format(events):
    """Convert Google Calendar events to fullcalendar format"""
    calendar_events = []
    
    for event in events:
        # Get start and end times
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        
        # Create calendar event
        calendar_event = {
            "title": event.get("summary", "No Title"),
            "start": start,
            "end": end,
        }
        
        # Add optional fields if available
        if event.get("description"):
            calendar_event["description"] = event["description"]
        
        if event.get("location"):
            calendar_event["location"] = event["location"]
            
        calendar_events.append(calendar_event)
    
    return calendar_events

# Main app logic
st.sidebar.header("🔐 Upload Google OAuth JSON")
uploaded_file = st.sidebar.file_uploader("Upload your `client_secret.json`", type=["json"])

if uploaded_file:
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
            tmp.write(uploaded_file.read())
            tmp_path = tmp.name
        
        # Simple authentication using InstalledAppFlow
        flow = InstalledAppFlow.from_client_secrets_file(tmp_path, SCOPES)
        creds = flow.run_local_server(port=0)
        
        # Build service
        service = build('calendar', 'v3', credentials=creds)
        
        # Sidebar controls
        st.sidebar.header("📅 Calendar Options")
        max_events = st.sidebar.slider("Max events to fetch", 10, 100, 50)
        
        # Fetch and display events
        with st.spinner("Fetching calendar events..."):
            events = fetch_calendar_events(service, max_events)
        
        if not events:
            st.warning("📅 No upcoming events found in your calendar.")
        else:
            st.success(f"✅ Fetched {len(events)} upcoming event(s) from your Google Calendar.")
            
            # Convert events for calendar display
            calendar_events = convert_to_calendar_format(events)
            
            # Calendar options
            calendar_options = {
                "initialView": "dayGridMonth",
                "editable": False,
                "selectable": True,
                "height": "600px",
                "headerToolbar": {
                    "left": "prev,next today",
                    "center": "title",
                    "right": "dayGridMonth,timeGridWeek,timeGridDay"
                }
            }
            
            # Display calendar
            selected_event = calendar(
                events=calendar_events, 
                options=calendar_options,
                key="calendar"
            )
            
            # Display event details if clicked
            if selected_event and selected_event.get("eventClick"):
                st.subheader("📋 Event Details")
                event_data = selected_event["eventClick"]["event"]
                
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Title:** {event_data.get('title', 'N/A')}")
                    st.write(f"**Start:** {event_data.get('start', 'N/A')}")
                    st.write(f"**End:** {event_data.get('end', 'N/A')}")
                
                with col2:
                    if event_data.get('description'):
                        st.write(f"**Description:** {event_data['description']}")
                    if event_data.get('location'):
                        st.write(f"**Location:** {event_data['location']}")
            
            # Show events list
            with st.expander("📋 Events List"):
                for i, event in enumerate(events, 1):
                    start_time = event['start'].get('dateTime', event['start'].get('date'))
                    st.write(f"{i}. **{event.get('summary', 'No Title')}** - {start_time}")
        
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
            
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")

else:
    st.info("👈 Upload your Google Calendar OAuth JSON file in the sidebar to get started.")
    
    # Instructions
    with st.expander("📖 Setup Instructions"):
        st.markdown("""
        ### How to get your OAuth credentials:
        
        1. **Go to Google Cloud Console**: https://console.cloud.google.com/
        2. **Create a new project** or select an existing one
        3. **Enable the Google Calendar API**:
           - Go to "APIs & Services" > "Library"
           - Search for "Google Calendar API" and enable it
        4. **Create OAuth 2.0 credentials**:
           - Go to "APIs & Services" > "Credentials"
           - Click "Create Credentials" > "OAuth client ID"
           - Choose "Desktop application"
           - Download the JSON file
        5. **Upload the JSON file** using the sidebar uploader
        """)
