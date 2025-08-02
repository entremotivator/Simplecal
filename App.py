import streamlit as st
import datetime
import json
import tempfile
from google.oauth2 import service_account
from googleapiclient.discovery import build
from streamlit_calendar import calendar

# Set the scope
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']

# Configure Streamlit page
st.set_page_config(page_title="📅 Google Calendar Viewer", layout="wide")
st.title("📅 Live Google Calendar Viewer")

def fetch_all_calendars(service):
    """Fetch list of all calendars"""
    try:
        calendar_list = service.calendarList().list().execute()
        calendars = calendar_list.get('items', [])
        return calendars
    except Exception as e:
        st.error(f"❌ Error fetching calendars: {str(e)}")
        return []

def fetch_calendar_events(service, calendar_ids, max_results=50, time_range='upcoming'):
    """Fetch events from multiple calendars"""
    all_events = []
    
    # Set time range
    if time_range == 'upcoming':
        time_min = datetime.datetime.utcnow().isoformat() + 'Z'
        time_max = None
    elif time_range == 'this_month':
        now = datetime.datetime.utcnow()
        time_min = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
        next_month = now.replace(day=1) + datetime.timedelta(days=32)
        time_max = next_month.replace(day=1).isoformat() + 'Z'
    elif time_range == 'this_year':
        now = datetime.datetime.utcnow()
        time_min = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0).isoformat() + 'Z'
        time_max = now.replace(year=now.year+1, month=1, day=1).isoformat() + 'Z'
    else:  # all_time
        time_min = None
        time_max = None
    
    for calendar_id in calendar_ids:
        try:
            # Fetch events from each calendar
            events_result = service.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime' if time_min else None
            ).execute()
            
            events = events_result.get('items', [])
            
            # Add calendar info to each event
            for event in events:
                event['calendar_id'] = calendar_id
                
            all_events.extend(events)
            
        except Exception as e:
            st.error(f"❌ Error fetching events from calendar {calendar_id}: {str(e)}")
    
    # Sort all events by start time
    if time_min:
        all_events.sort(key=lambda x: x['start'].get('dateTime', x['start'].get('date')))
    
    return all_events

def convert_to_calendar_format(events, calendars_info):
    """Convert Google Calendar events to fullcalendar format"""
    calendar_events = []
    
    # Create color mapping for different calendars
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9']
    color_map = {}
    
    for event in events:
        # Get start and end times
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        calendar_id = event.get('calendar_id', 'primary')
        
        # Assign color to calendar
        if calendar_id not in color_map:
            color_map[calendar_id] = colors[len(color_map) % len(colors)]
        
        # Find calendar name
        calendar_name = 'Primary'
        for cal in calendars_info:
            if cal['id'] == calendar_id:
                calendar_name = cal.get('summary', calendar_id)
                break
        
        # Create calendar event
        calendar_event = {
            "title": event.get("summary", "No Title"),
            "start": start,
            "end": end,
            "backgroundColor": color_map[calendar_id],
            "borderColor": color_map[calendar_id],
            "extendedProps": {
                "calendar_id": calendar_id,
                "calendar_name": calendar_name,
                "description": event.get("description", ""),
                "location": event.get("location", "")
            }
        }
        
        calendar_events.append(calendar_event)
    
    return calendar_events, color_map

# Main app
st.sidebar.header("🔐 Authentication")
st.sidebar.subheader("Upload service_account.json")
uploaded_file = st.sidebar.file_uploader(
    "Drag and drop file here", 
    type=["json"],
    help="Limit 200MB per file • JSON"
)

if uploaded_file:
    try:
        # Load service account credentials
        service_account_info = json.load(uploaded_file)
        credentials = service_account.Credentials.from_service_account_info(
            service_account_info, 
            scopes=SCOPES
        )
        
        # Build service
        service = build('calendar', 'v3', credentials=credentials)
        
        # Fetch all available calendars
        with st.spinner("Fetching available calendars..."):
            all_calendars = fetch_all_calendars(service)
        
        if not all_calendars:
            st.error("❌ No calendars found or insufficient permissions.")
        else:
            # Sidebar controls
            st.sidebar.header("📅 Calendar Selection")
            
            # Display available calendars with checkboxes
            st.sidebar.subheader("Select Calendars:")
            selected_calendars = []
            
            # Primary calendar first
            for calendar in all_calendars:
                if calendar.get('primary', False):
                    is_selected = st.sidebar.checkbox(
                        f"📅 {calendar.get('summary', 'Primary')} (Primary)",
                        value=True,
                        key=f"cal_{calendar['id']}"
                    )
                    if is_selected:
                        selected_calendars.append(calendar['id'])
            
            # Other calendars
            for calendar in all_calendars:
                if not calendar.get('primary', False):
                    calendar_name = calendar.get('summary', calendar['id'])
                    is_selected = st.sidebar.checkbox(
                        f"📅 {calendar_name}",
                        value=True,
                        key=f"cal_{calendar['id']}"
                    )
                    if is_selected:
                        selected_calendars.append(calendar['id'])
            
            # Manual calendar ID/email input
            st.sidebar.subheader("Add Calendar by ID/Email:")
            manual_calendar = st.sidebar.text_input(
                "Calendar ID or Email:",
                placeholder="example@gmail.com or calendar_id",
                help="Enter a calendar ID or email address to add it manually"
            )
            
            if st.sidebar.button("➕ Add Calendar"):
                if manual_calendar and manual_calendar not in selected_calendars:
                    selected_calendars.append(manual_calendar)
                    st.sidebar.success(f"Added: {manual_calendar}")
            
            # Show selected calendars
            if selected_calendars:
                st.sidebar.subheader("Selected Calendars:")
                for cal_id in selected_calendars:
                    # Find calendar name
                    cal_name = cal_id
                    for cal in all_calendars:
                        if cal['id'] == cal_id:
                            cal_name = cal.get('summary', cal_id)
                            break
                    st.sidebar.text(f"• {cal_name}")
            
            # Other options
            st.sidebar.header("📊 Display Options")
            max_events = st.sidebar.slider("Max events per calendar", 10, 200, 100)
            
            time_range = st.sidebar.selectbox(
                "Time Range:",
                options=['upcoming', 'this_month', 'this_year', 'all_time'],
                format_func=lambda x: {
                    'upcoming': '📅 Upcoming Events',
                    'this_month': '📅 This Month',
                    'this_year': '📅 This Year',
                    'all_time': '📅 All Time'
                }[x]
            )
            
            # Refresh button
            if st.sidebar.button("🔄 Refresh Data"):
                st.cache_data.clear()
                st.rerun()
            
            if selected_calendars:
                # Fetch and display events
                with st.spinner("Fetching calendar events..."):
                    events = fetch_calendar_events(service, selected_calendars, max_events, time_range)
                
                if not events:
                    st.warning("📅 No events found in the selected calendars and time range.")
                else:
                    st.success(f"✅ Fetched {len(events)} event(s) from {len(selected_calendars)} calendar(s).")
                    
                    # Convert events for calendar display
                    calendar_events, color_map = convert_to_calendar_format(events, all_calendars)
                    
                    # Show calendar legend
                    st.subheader("📊 Calendar Legend")
                    legend_cols = st.columns(min(len(color_map), 4))
                    for i, (cal_id, color) in enumerate(color_map.items()):
                        col = legend_cols[i % len(legend_cols)]
                        cal_name = cal_id
                        for cal in all_calendars:
                            if cal['id'] == cal_id:
                                cal_name = cal.get('summary', cal_id)
                                break
                        col.markdown(f'<div style="background-color: {color}; padding: 5px; border-radius: 5px; margin: 2px; text-align: center; color: white; font-weight: bold;">{cal_name}</div>', unsafe_allow_html=True)
                    
                    # Calendar options
                    calendar_options = {
                        "initialView": "dayGridMonth",
                        "editable": False,
                        "selectable": True,
                        "height": "700px",
                        "headerToolbar": {
                            "left": "prev,next today",
                            "center": "title",
                            "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek"
                        },
                        "views": {
                            "listWeek": {
                                "buttonText": "List"
                            }
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
                        extended_props = event_data.get("extendedProps", {})
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Title:** {event_data.get('title', 'N/A')}")
                            st.write(f"**Start:** {event_data.get('start', 'N/A')}")
                            st.write(f"**End:** {event_data.get('end', 'N/A')}")
                            st.write(f"**Calendar:** {extended_props.get('calendar_name', 'N/A')}")
                        
                        with col2:
                            if extended_props.get('description'):
                                st.write(f"**Description:** {extended_props['description']}")
                            if extended_props.get('location'):
                                st.write(f"**Location:** {extended_props['location']}")
                    
                    # Show events summary by calendar
                    with st.expander(f"📋 Events Summary ({len(events)} total events)"):
                        # Group events by calendar
                        events_by_calendar = {}
                        for event in events:
                            cal_id = event.get('calendar_id', 'primary')
                            if cal_id not in events_by_calendar:
                                events_by_calendar[cal_id] = []
                            events_by_calendar[cal_id].append(event)
                        
                        for cal_id, cal_events in events_by_calendar.items():
                            # Find calendar name
                            cal_name = cal_id
                            for cal in all_calendars:
                                if cal['id'] == cal_id:
                                    cal_name = cal.get('summary', cal_id)
                                    break
                            
                            st.write(f"**{cal_name}** ({len(cal_events)} events):")
                            for i, event in enumerate(cal_events[:10], 1):  # Show first 10 events
                                start_time = event['start'].get('dateTime', event['start'].get('date'))
                                st.write(f"  {i}. {event.get('summary', 'No Title')} - {start_time}")
                            
                            if len(cal_events) > 10:
                                st.write(f"  ... and {len(cal_events) - 10} more events")
                            st.write("")
            else:
                st.info("📅 Please select at least one calendar to display events.")
            
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")

else:
    st.info("👈 Upload your service account JSON file in the sidebar to get started.")
