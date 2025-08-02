import streamlit as st
import datetime
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from streamlit_calendar import calendar
import pandas as pd
import io

# ---------------------------------------
# CONFIG & UTILS
# ---------------------------------------
SCOPES = ['https://www.googleapis.com/auth/calendar']

st.set_page_config(page_title="📅 Pro Google Calendar", layout="wide")
st.title("📅 Pro Google Calendar App")

def authenticate_google(json_file):
    try:
        creds_info = json.load(json_file)
        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=SCOPES
        )
        service = build('calendar', 'v3', credentials=creds)
        return service, None
    except Exception as err:
        return None, str(err)

def fetch_calendars(service):
    try:
        items = service.calendarList().list().execute().get("items", [])
        return items
    except Exception:
        return []

def fetch_events(service, calendar_id, max_results=100, time_min=None, time_max=None, q=None):
    try:
        params = {
            "calendarId": calendar_id,
            "singleEvents": True,
            "orderBy": "startTime",
            "maxResults": max_results,
            "timeMin": time_min,
        }
        if time_max:
            params["timeMax"] = time_max
        if q:
            params["q"] = q
        result = service.events().list(**params).execute()
        return result.get("items", [])
    except Exception as err:
        st.warning(f"Error fetching events: {err}")
        return []

def insert_event(service, calendar_id, event_body):
    try:
        newev = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        return newev
    except Exception as err:
        st.error(f"Could not create event: {err}")
        return None

def update_event(service, calendar_id, event_id, event_body):
    try:
        newev = service.events().update(calendarId=calendar_id, eventId=event_id, body=event_body).execute()
        return newev
    except Exception as err:
        st.error(f"Could not update event: {err}")
        return None

def delete_event(service, calendar_id, event_id):
    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return True
    except Exception as err:
        st.error(f"Could not delete event: {err}")
        return False

def gcal_event_to_calendar(ev):
    """Format API event for calendar widget"""
    start = ev['start'].get('dateTime', ev['start'].get('date'))
    end = ev['end'].get('dateTime', ev['end'].get('date'))
    return {
        "id": ev.get("id"),
        "title": ev.get("summary", "No Title"),
        "start": start,
        "end": end,
        "color": ev.get("colorId", "#3788d8"),
        "extendedProps": {
            "description": ev.get("description", ""),
            "location": ev.get("location", ""),
            "organizer": ev.get("organizer", {}).get("email", ""),
            "attendees": ", ".join([a.get('email') for a in ev.get('attendees', [])]) if ev.get('attendees') else "",
            "recurrence": ev.get("recurrence", []),
            "conference": ev.get("conferenceData", {}).get("entryPoints", [{}])[0].get("uri", ""),
            "att_status": ", ".join([f"{a.get('email')} ({a.get('responseStatus')})" for a in ev.get('attendees', [])]) if ev.get('attendees') else "",
        }
    }

def events_table(events):
    return pd.DataFrame([{
        "ID": e.get("id"),
        "Title": e.get("summary", "No Title"),
        "Start": e['start'].get('dateTime', e['start'].get('date')),
        "End": e['end'].get('dateTime', e['end'].get('date')),
        "Location": e.get('location', ''),
        "Organizer": e.get('organizer', {}).get('email', ''),
        "Attendees": ", ".join([a.get('email') for a in e.get('attendees', [])]) if e.get('attendees') else "",
        "Description": e.get('description', '')
    } for e in events])

def default_event_template(start_dt, end_dt):
    return {
        "summary": "",
        "location": "",
        "description": "",
        "start": {"dateTime": start_dt, "timeZone": "UTC"},
        "end": {"dateTime": end_dt, "timeZone": "UTC"},
        "attendees": [],
        "reminders": {"useDefault": True}
    }

# ---------------------------------------
# AUTHENTICATION
# ---------------------------------------
st.sidebar.header("🔐 Authentication")
uploaded_json = st.sidebar.file_uploader("Upload service_account.json", type=["json"])
if 'service' not in st.session_state:
    st.session_state['service'] = None
if uploaded_json:
    service, err = authenticate_google(uploaded_json)
    if service:
        st.session_state['service'] = service
        st.sidebar.success("✅ Authenticated with Google Calendar API!")
    else:
        st.sidebar.error(f"Google Auth Failed: {err}")

# =======================================
# MAIN APP WHEN AUTHENTICATED
# =======================================
if st.session_state["service"]:
    service = st.session_state["service"]
    calendars = fetch_calendars(service)
    calendar_options = {c['summary']: c['id'] for c in calendars}
    calendar_keys = list(calendar_options.keys()) + ["Enter custom calendar email..."]

    cal_name = st.sidebar.selectbox("Select Calendar", options=calendar_keys)
    if cal_name == "Enter custom calendar email...":
        manual_email = st.sidebar.text_input("Manual Calendar Email", value="entremotivator@gmail.com")
        cal_id = manual_email
    else:
        cal_id = calendar_options[cal_name]

    # Theme switch
    st.sidebar.divider()
    theme = st.sidebar.radio("Theme", ("Light", "Dark"))
    if theme == "Dark":
        st.markdown(
            """
            <style>
            body, .stApp { background-color: #222 !important; color: #ddd !important; }
            div.st-eg {color: #ddd !important;}
            </style>
            """, unsafe_allow_html=True
        )
    # ---------------------------------------
    # Filters/Controls
    # ---------------------------------------
    st.sidebar.subheader("📅 Event Filters")
    max_events = st.sidebar.slider("Max events", 10, 300, 80, step=10)
    d1, d2 = st.sidebar.columns(2)
    today = datetime.date.today()
    with d1:
        start_date = st.date_input("From", today)
    with d2:
        end_date = st.date_input("To", today + datetime.timedelta(days=30))
    st.sidebar.subheader("🔎 Search/Filter")
    keyword = st.sidebar.text_input("Search events by keyword...")
    attn = st.sidebar.text_input("Filter by attendee email")
    show_past = st.sidebar.checkbox("Include past events", False)

    # Date/time range
    time_min = (
        datetime.datetime.combine(start_date, datetime.time.min).isoformat() + 'Z'
        if not show_past else None
    )
    time_max = (
        datetime.datetime.combine(end_date, datetime.time.max).isoformat() + 'Z'
    )

    # ---------------------------------------
    # Fetch events and filter
    # ---------------------------------------
    try:
        events = fetch_events(
            service, cal_id, max_results=max_events, time_min=time_min,
            time_max=time_max, q=keyword if keyword else None
        )
        if attn:
            events = [e for e in events if any(
                attn.lower() in a.get('email','').lower() for a in e.get('attendees', []))]
        st.info(f"Loaded {len(events)} events from calendar [{cal_id}]")
    except Exception as e:
        st.error(f"Could not fetch calendar: {cal_id}. Error: {str(e)}")
        events = []

    # ---------------------------------------
    # CALENDAR & EVENT DETAILS
    # ---------------------------------------
    calendar_events = [gcal_event_to_calendar(e) for e in events]
    calendar_options_obj = {
        "initialView": "dayGridMonth",
        "editable": False,
        "selectable": True,
        "height": "800px",
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek"
        },
        "themeSystem": "bootstrap",
        "eventClick": True
    }
    calres = calendar(
        events=calendar_events,
        options=calendar_options_obj,
        key="calendar"
    )

    # --- Event details/edit/delete modal
    if calres and calres.get("eventClick"):
        st.subheader("📋 Event Details")
        event_data = calres["eventClick"]["event"]
        eid = event_data.get("id")
        target_event = next((e for e in events if e.get("id")==eid), None)
        if not target_event:
            st.warning("Event not found (maybe deleted)")
        else:
            st.write(f"**Title:** {target_event.get('summary', '')}")
            st.write(f"**Start:** {target_event['start'].get('dateTime', target_event['start'].get('date'))}")
            st.write(f"**End:** {target_event['end'].get('dateTime', target_event['end'].get('date'))}")
            st.write(f"**Location:** {target_event.get('location', '')}")
            if target_event.get('description'):
                st.write(f"**Description:** {target_event['description']}")
            if target_event.get('recurrence'):
                st.write(f"**Recurrence:** {target_event['recurrence']}")
            if target_event.get('conferenceData'):
                uri = target_event['conferenceData'].get('entryPoints', [{}])[0].get('uri', '')
                if uri:
                    st.write(f"**Conference link:** {uri}")

            # -- Edit/Delete
            with st.expander("✏️ Edit/Delete Event"):
                e_title = st.text_input("Title", target_event.get("summary"), key="etitle")
                e_desc = st.text_area("Description", target_event.get("description", ""), key="edesc")
                e_loc = st.text_input("Location", target_event.get("location", ""), key="eloc")
                e_start = st.text_input("Start (ISO)", target_event['start'].get('dateTime', target_event['start'].get('date')), key="estart")
                e_end = st.text_input("End (ISO)", target_event['end'].get('dateTime', target_event['end'].get('date')), key="eend")
                if st.button("Update This Event", key="update_button"):
                    edit_body = {
                        "summary": e_title, "description": e_desc,"location": e_loc,
                        "start": {"dateTime": e_start, "timeZone": "UTC"},
                        "end": {"dateTime": e_end, "timeZone": "UTC"}
                    }
                    update_event(service, cal_id, eid, edit_body)
                    st.success("Event updated! Refreshing view...")
                    st.experimental_rerun()
                if st.button("Delete This Event", key="delete_button"):
                    delete_event(service, cal_id, eid)
                    st.warning("Deleted event, will refresh.")
                    st.experimental_rerun()

    # --- Add Event Section
    with st.expander("➕ Add New Event"):
        now = datetime.datetime.utcnow()
        default_start = now.replace(microsecond=0).isoformat()+"Z"
        default_end = (now + datetime.timedelta(hours=1)).replace(microsecond=0).isoformat()+"Z"
        title = st.text_input("New Event Title")
        description = st.text_area("Description")
        location = st.text_input("Location")
        start_at = st.text_input("Start (ISO8601)", default_start)
        end_at = st.text_input("End (ISO8601)", default_end)
        att_raw = st.text_input("Attendees (comma separated emails)")
        if st.button("Create Event", key="create_button"):
            to_add = default_event_template(start_at, end_at)
            to_add["summary"] = title
            to_add["description"] = description
            to_add["location"] = location
            if att_raw.strip():
                to_add["attendees"] = [{"email": email.strip()} for email in att_raw.split(",")]
            ev = insert_event(service, cal_id, to_add)
            if ev:
                st.success(f"Created new event: {ev['summary']}")
                st.experimental_rerun()

    # --- Download/View events table
    st.divider()
    st.markdown("### 📋 Events Table and Download")
    df = events_table(events)
    st.dataframe(df, use_container_width=True)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    st.download_button("Download as CSV", data=csv_buffer.getvalue(), file_name='calendar_events.csv')

else:
    st.info("👈 Please upload your service account JSON in the sidebar to get started.")

st.markdown("""
---
<sub>Tip: To access another calendar (e.g. entremotivator@gmail.com), share that calendar with your service account email (as found in your JSON file).</sub>
""", unsafe_allow_html=True)
