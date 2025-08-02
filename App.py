import streamlit as st
import datetime
import os
import json
import tempfile
import pickle
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from streamlit_calendar import calendar

# Set the scope
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Configure Streamlit page
st.set_page_config(page_title="📅 Google Calendar Viewer", layout="wide")
st.title("📅 Live Google Calendar Viewer")

def save_credentials(creds):
    """Save credentials to session state"""
    st.session_state['credentials'] = creds

def load_credentials():
    """Load credentials from session state"""
    return st.session_state.get('credentials', None)

def authenticate_user(client_secrets_path):
    """Handle Google OAuth authentication"""
    try:
        # Check if we have valid credentials in session
        creds = load_credentials()
        
        if creds and creds.valid:
            return creds
        
        # If we have expired credentials, try to refresh them
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                save_credentials(creds)
                return creds
            except Exception as e:
                st.warning(f"Failed to refresh credentials: {str(e)}")
        
        # Create new credentials
        flow = Flow.from_client_secrets_file(
            client_secrets_path,
            scopes=SCOPES,
            redirect_uri='http://localhost:8080'
        )
        
        # Generate authorization URL
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        
        st.markdown("### 🔐 Authorization Required")
        st.markdown(f"**Step 1:** Click the link below to authorize the application:")
        st.markdown(f"[🔗 Authorize Google Calendar Access]({auth_url})")
        
        # Input field for authorization code
        auth_code = st.text_input(
            "**Step 2:** Paste the authorization code here:",
            placeholder="Enter the authorization code from Google...",
            help="After clicking the link above, you'll get a code. Paste it here."
        )
        
        if auth_code:
            try:
                # Exchange authorization code for credentials
                flow.fetch_token(code=auth_code)
                creds = flow.credentials
                save_credentials(creds)
                st.success("✅ Authentication successful!")
                st.rerun()
                return creds
            except Exception as e:
                st.error(f"❌ Authentication failed: {str(e)}")
                return None
        
        return None
        
    except Exception as e:
        st.error(f"❌ Authentication error: {str(e)}")
        return None

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
def main():
    # Sidebar for file upload and controls
    st.sidebar.header("🔐 Google OAuth Setup")
    
    # File upload
    uploaded_file = st.sidebar.file_uploader(
        "Upload your `client_secret.json`", 
        type=["json"],
        help="Download this from Google Cloud Console > APIs & Services > Credentials"
    )
    
    if uploaded_file:
        try:
            # Save uploaded file temporarily
            with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as tmp:
                tmp.write(uploaded_file.read())
                tmp_path = tmp.name
            
            # Validate credentials file
            with open(tmp_path) as f:
                creds_json = json.load(f)
            
            # Check if it's the correct type of OAuth client
            if creds_json.get("installed") is None and creds_json.get("web") is None:
                st.sidebar.error("❌ Invalid credentials file. Must be an OAuth 2.0 Client ID.")
                return
            
            st.sidebar.success("✅ Valid credentials file uploaded")
            
            # Authentication
            creds = authenticate_user(tmp_path)
            
            if creds:
                # Build service
                service = build('calendar', 'v3', credentials=creds)
                
                # Sidebar controls
                st.sidebar.header("📅 Calendar Options")
                max_events = st.sidebar.slider("Max events to fetch", 10, 100, 50)
                
                # Add refresh button
                if st.sidebar.button("🔄 Refresh Calendar"):
                    st.cache_data.clear()
                
                # Clear credentials button
                if st.sidebar.button("🚪 Logout"):
                    if 'credentials' in st.session_state:
                        del st.session_state['credentials']
                    st.rerun()
                
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
            st.error(f"❌ Error processing file: {str(e)}")
    
    else:
        st.info("👈 Please upload your Google Calendar OAuth JSON file in the sidebar to get started.")
        
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
            
            ### Security Note:
            Your credentials are only stored in your browser session and are not saved permanently.
            """)

if __name__ == "__main__":
    main()
