import streamlit as st
import datetime
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from streamlit_calendar import calendar
import pandas as pd
import io

# ---------- CONFIGURATION ----------
SCOPES = ['https://www.googleapis.com/auth/calendar']
st.set_page_config(page_title="📅 Pro Google Calendar", layout="wide")
st.title("📅 Pro Google Calendar App (Advanced)")

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

# ---------- CALENDAR APIs ----------
def fetch_calendars(service):
    try:
        cals = service.calendarList().list().execute().get("items", [])
        return cals
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
        st.warning(f"Failed to get events: {err}")
        return []

def insert_event(service, calendar_id, event_body):
    try:
        event = service.events().insert(calendarId=calendar_id, body=event_body).execute()
        return event
    except Exception as err:
        st.warning(f"Could not create event: {err}")
        return None

def update_event(service, calendar_id, event_id, event_body):
    try:
        event = service.events().update(calendarId=calendar_id, eventId=event_id, body=event_body).execute()
        return event
    except Exception as err:
        st.warning(f"Could not update event: {err}")
        return None

def delete_event(service, calendar_id, event_id):
    try:
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        return True
    except Exception as err:
        st.warning(f"Could not delete event: {err}")
        return False

# ---------- UTILITIES AND FORMATTERS ----------
def gcal_event_to_calendar(ev):
    start = ev['start'].get('dateTime', ev['start'].get('date'))
    end = ev['end'].get('dateTime', ev['end'].get('date'))
    color = ev.get("colorId", "#3788d8")
    # Add conference link, recurrence, attendees etc.
    return {
        "id": ev.get("id"),
        "title": ev.get("summary", "No Title"),
        "start": start,
        "end": end,
        "color": color,
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
    df = pd.DataFrame([{
        "Id": e.get("id"),
        "Title": e.get("summary", "No Title"),
        "Start": e['start'].get('dateTime', e['start'].get('date')),
        "End": e['end'].get('dateTime', e['end'].get('date')),
        "Location": e.get('location', ''),
        "Organizer": e.get('organizer', {}).get('email', ''),
        "Attendees": ", ".join([a.get('email') for a in e.get('attendees', [])]) if e.get('attendees') else "",
        "Description": e.get('description', '')
    } for e in events])
    return df

def default_event_template(start_dt, end_dt):
    return {
        "summary": "",
        "location": "",
        "description": "",
        "start": {"dateTime": start_dt, "timeZone": "UTC"},
        "end": {"dateTime": end_dt, "timeZone": "UTC"},
        "attendees": [],
        "reminders": {
            "useDefault": True,
        }
    }

# ---------- AUTHENTICATION FLOW ----------
st.sidebar.header("🔐 Authentication")
uploaded_json = st.sidebar.file_uploader("Upload service_account.json", type=["json"])
if 'service' not in st.session_state:
    st.session_state['service'] = None
if uploaded_json:
    service, err = authenticate_google(uploaded_json)
    if service:
        st.session_state['service'] = service
        st.sidebar.success("Authenticated with Google Calendar API!")
    else:
        st.sidebar.error(f"Google Auth Failed: {err}")

if st.session_state["service"]:
    service = st.session_state["service"]
    # Get calendars
    calendars = fetch_calendars(service)
    calendar_options = {c['summary']: c['id'] for c in calendars}
    cal_name = st.sidebar.selectbox(
        "Select Calendar", options=list(calendar_options.keys())
    )
    cal_id = calendar_options[cal_name]

    # Theme switch
    st.sidebar.divider()
    theme = st.sidebar.radio("Theme", ("Light", "Dark"))
    if theme == "Dark":
        st.markdown(
            """
            <style>
            body, .stApp { background-color: #222; color: white; }
            </style>
            """, unsafe_allow_html=True,
        )

    # ------- Controls
    st.sidebar.subheader("📅 Filters/Controls")
    max_events = st.sidebar.slider("Max events", 10, 300, 80, step=5)

    d1, d2 = st.sidebar.columns(2)
    with d1:
        start_date = st.date_input("From", datetime.date.today())
    with d2:
        end_date = st.date_input("To", datetime.date.today() + datetime.timedelta(days=30))

    st.sidebar.subheader("🔎 Search/Filter")
    keyword = st.sidebar.text_input("Search events by keyword...")
    attn = st.sidebar.text_input("Filter by attendee email")
    show_past = st.sidebar.checkbox("Include past events", False)

    # ------- Fetch events
    time_min = (
        datetime.datetime.combine(start_date, datetime.time.min).isoformat() + 'Z'
        if not show_past else None
    )
    time_max = (
        datetime.datetime.combine(end_date, datetime.time.max).isoformat() + 'Z'
    )

    with st.spinner("Fetching events..."):
        events = fetch_events(
            service, cal_id, max_results=max_events, time_min=time_min,
            time_max=time_max, q=keyword if keyword else None
        )
    if attn:
        events = [e for e in events if any(
            attn in a.get('email', '') for a in e.get('attendees', []))]

    st.info(f"Loaded {len(events)} events from '{cal_name}' calendar.")

    # ------- Advanced calendar display
    calendar_events = [gcal_event_to_calendar(e) for e in events]
    calendar_options = {
        "initialView": "dayGridMonth",
        "height": "850px",
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek"
        },
        "selectable": True,
        "editable": False,
        "eventClick": True,
        "themeSystem": "bootstrap"
    }

    calendar_res = calendar(
        events=calendar_events,
        options=calendar_options,
        key="main_calendar"
    )

    st.divider()
    # ------- Event modal (View, Edit, Delete)
    if calendar_res and calendar_res.get("eventClick"):
        st.subheader("📋 Event Details")
        event_data = calendar_res["eventClick"]["event"]
        eid = event_data.get("id")
        target_event = next((e for e in events if e.get("id")==eid), None)
        if target_event:
            st.write(f"**Title:** {target_event.get('summary')}")
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

            # Edit/Delete options
            with st.expander("Edit/Delete Event"):
                e_title = st.text_input("Title", target_event.get("summary"))
                e_desc = st.text_area("Description", target_event.get("description", ""))
                e_loc = st.text_input("Location", target_event.get("location", ""))
                e_start = st.text_input("Start (ISO 8601)", target_event['start'].get('dateTime', target_event['start'].get('date')))
                e_end = st.text_input("End (ISO 8601)", target_event['end'].get('dateTime', target_event['end'].get('date')))
                if st.button("Update Event"):
                    edit_body = {
                        "summary": e_title, "description": e_desc,"location": e_loc,
                        "start": {"dateTime": e_start, "timeZone": "UTC"},
                        "end": {"dateTime": e_end, "timeZone": "UTC"}
                    }
                    update_event(service, cal_id, eid, edit_body)
                    st.experimental_rerun()
                if st.button("Delete Event", type="primary"):
                    delete_event(service, cal_id, eid)
                    st.experimental_rerun()

    # ------- Add Event Modal
    with st.expander("➕ Add New Event"):
        now = datetime.datetime.utcnow()
        default_start = now.replace(microsecond=0).isoformat()+"Z"
        default_end = (now + datetime.timedelta(hours=1)).replace(microsecond=0).isoformat()+"Z"
        title = st.text_input("Title")
        description = st.text_area("Description")
        location = st.text_input("Location")
        start_at = st.text_input("Start", default_start)
        end_at = st.text_input("End", default_end)
        att_raw = st.text_input("Attendees (comma separated emails)")
        if st.button("Create Event"):
            to_add = default_event_template(start_at, end_at)
            to_add["summary"] = title
            to_add["description"] = description
            to_add["location"] = location
            if att_raw.strip():
                to_add["attendees"] = [{"email": email.strip()} for email in att_raw.split(",")]
            ev = insert_event(service, cal_id, to_add)
            if ev:
                st.success(f"Created! Event id: {ev['id']}")
                st.experimental_rerun()

    st.divider()

    # ------- Download CSV and Table
    st.markdown("#### 📥 Download or View Events Table")
    df = events_table(events)
    st.dataframe(df, use_container_width=True)
    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    st.download_button("Download as CSV", data=csv_buffer.getvalue(), file_name='calendar_events.csv')

else:
    st.info("👈 Please upload your Google service account JSON to start. Learn how to create one in the [Google Cloud Console](https://console.cloud.google.com/apis/credentials).")  # No link, for info only
