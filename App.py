import streamlit as st
import datetime
import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from streamlit_calendar import calendar
import pandas as pd
import io
from fpdf import FPDF

# ---------------------------------------
# CONFIG & UTILITIES
# ---------------------------------------

SCOPES = ['https://www.googleapis.com/auth/calendar']
st.set_page_config(page_title="📅 Pro Google Calendar with Refresh & PDF", layout="wide")
st.title("📅 Pro Google Calendar App (with Refresh & PDF Export)")

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
        return service.calendarList().list().execute().get("items", [])
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
        return service.events().insert(calendarId=calendar_id, body=event_body).execute()
    except Exception as err:
        st.error(f"Could not create event: {err}")
        return None

def update_event(service, calendar_id, event_id, event_body):
    try:
        return service.events().update(calendarId=calendar_id, eventId=event_id, body=event_body).execute()
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

def create_pdf_report(df: pd.DataFrame) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Google Calendar Events Report", ln=True, align="C")
    pdf.ln(10)

    # Make sure to handle column widths and text wrapping properly
    col_widths = [30, 50, 40, 40, 50, 70]  # Adjust widths for columns
    headers = ["Title", "Start", "End", "Location", "Organizer", "Attendees"]

    # Header row
    for i, header in enumerate(headers):
        pdf.cell(col_widths[i], 10, header, border=1)
    pdf.ln()

    # Rows
    for _, row in df.iterrows():
        pdf.cell(col_widths[0], 10, str(row["Title"])[:25], border=1)
        pdf.cell(col_widths[1], 10, str(row["Start"])[:20], border=1)
        pdf.cell(col_widths[2], 10, str(row["End"])[:20], border=1)
        pdf.cell(col_widths[3], 10, str(row["Location"])[:30], border=1)
        pdf.cell(col_widths[4], 10, str(row["Organizer"])[:30], border=1)
        pdf.cell(col_widths[5], 10, str(row["Attendees"])[:50], border=1)
        pdf.ln()

    return pdf.output(dest='S').encode('latin1')


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
        st.sidebar.error(f"Google Authentication Failed: {err}")

# ---------------------------------------
# MAIN APP LOGIC
# ---------------------------------------

def load_events_for_calendar(service, cal_id, max_events, time_min, time_max, keyword, attendee_filter):
    events = fetch_events(service, cal_id, max_events, time_min, time_max, keyword)
    if attendee_filter:
        events = [e for e in events if any(
            attendee_filter.lower() in a.get('email', '').lower() for a in e.get('attendees', []))]
    return events

if st.session_state["service"]:
    service = st.session_state["service"]

    calendars = fetch_calendars(service)
    calendar_options = {c['summary']: c['id'] for c in calendars}
    calendar_keys = list(calendar_options.keys())
    calendar_keys.append("Enter custom calendar email...")

    cal_name = st.sidebar.selectbox("Select Calendar", options=calendar_keys)
    if cal_name == "Enter custom calendar email...":
        cal_id = st.sidebar.text_input("Manual Calendar Email", value="entremotivator@gmail.com")
    else:
        cal_id = calendar_options[cal_name]

    st.sidebar.markdown("---")
    theme = st.sidebar.radio("Theme", ("Light", "Dark"), horizontal=True)
    if theme == "Dark":
        st.markdown(
            """
            <style>
            body, .stApp { background-color: #222 !important; color: #ddd !important; }
            div.st-eg {color: #ddd !important;}
            </style>
            """, unsafe_allow_html=True
        )
    else:
        st.markdown(
            """
            <style>
            body, .stApp { background-color: white !important; color: black !important; }
            </style>
            """, unsafe_allow_html=True
        )

    st.sidebar.subheader("📅 Event Filters & Controls")
    max_events = st.sidebar.slider("Max events to fetch", min_value=10, max_value=300, value=80, step=10)
    today = datetime.date.today()
    d1, d2 = st.sidebar.columns(2)
    with d1:
        start_date = st.date_input("From date", today)
    with d2:
        end_date = st.date_input("To date", today + datetime.timedelta(days=30))
    keyword = st.sidebar.text_input("Keyword search")
    attendee_filter = st.sidebar.text_input("Filter by Attendee Email (partial match)")
    include_past = st.sidebar.checkbox("Include past events", value=False)

    # ISO datetime strings for API
    time_min = datetime.datetime.combine(start_date, datetime.time.min).isoformat() + 'Z' if not include_past else None
    time_max = datetime.datetime.combine(end_date, datetime.time.max).isoformat() + 'Z'

    # --- Refresh button to reload events ---
    if 'events' not in st.session_state:
        st.session_state['events'] = []

    refresh_clicked = st.sidebar.button("🔄 Refresh Calendar")
    if refresh_clicked or not st.session_state['events']:
        # Reload events from API
        with st.spinner("Refreshing events..."):
            try:
                st.session_state['events'] = load_events_for_calendar(
                    service, cal_id, max_events, time_min, time_max, keyword, attendee_filter)
                st.success(f"Loaded {len(st.session_state['events'])} events")
            except Exception as e:
                st.error(f"Failed to fetch events from calendar {cal_id}: {str(e)}")
                st.session_state['events'] = []

    events = st.session_state['events']

    # --- Calendar Widget ---
    calendar_events = [gcal_event_to_calendar(e) for e in events]
    calendar_config = {
        "initialView": "dayGridMonth",
        "editable": False,
        "selectable": True,
        "height": "850px",
        "headerToolbar": {
            "left": "prev,next today",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay,listWeek"
        },
        "themeSystem": "bootstrap",
        "eventClick": True
    }

    cal_response = calendar(events=calendar_events, options=calendar_config, key="calendar")

    # --- Display event details when clicked ---
    if cal_response and cal_response.get("eventClick"):
        st.subheader("📋 Event Details")
        event_data = cal_response["eventClick"]["event"]
        eid = event_data.get("id")
        target_event = next((e for e in events if e.get("id") == eid), None)

        if target_event:
            st.markdown(f"**Title:** {target_event.get('summary', '')}")
            st.markdown(f"**Start:** {target_event['start'].get('dateTime', target_event['start'].get('date'))}")
            st.markdown(f"**End:** {target_event['end'].get('dateTime', target_event['end'].get('date'))}")
            st.markdown(f"**Location:** {target_event.get('location', '')}")

            if target_event.get('description'):
                st.markdown(f"**Description:** {target_event['description']}")
            if target_event.get('recurrence'):
                st.markdown(f"**Recurrence:** {target_event['recurrence']}")
            if target_event.get('conferenceData'):
                uri = target_event['conferenceData'].get('entryPoints', [{}])[0].get('uri', '')
                if uri:
                    st.markdown(f"**Conference link:** [Join Meeting]({uri})")

            with st.expander("✏️ Edit/Delete Event"):
                e_title = st.text_input("Title", target_event.get("summary"), key="edit_title")
                e_desc = st.text_area("Description", target_event.get("description", ""), key="edit_desc")
                e_loc = st.text_input("Location", target_event.get("location", ""), key="edit_location")
                e_start = st.text_input("Start (ISO time)", target_event['start'].get('dateTime', target_event['start'].get('date')), key="edit_start")
                e_end = st.text_input("End (ISO time)", target_event['end'].get('dateTime', target_event['end'].get('date')), key="edit_end")

                if st.button("Update Event", key="update_event_button"):
                    updated_event_body = {
                        "summary": e_title,
                        "description": e_desc,
                        "location": e_loc,
                        "start": {"dateTime": e_start, "timeZone": "UTC"},
                        "end": {"dateTime": e_end, "timeZone": "UTC"},
                    }
                    updated = update_event(service, cal_id, eid, updated_event_body)
                    if updated:
                        st.success("Event updated successfully!")
                        # Clear cached events to force refresh
                        st.session_state['events'] = []
                        st.experimental_rerun()

                if st.button("Delete Event", key="delete_event_button"):
                    deleted = delete_event(service, cal_id, eid)
                    if deleted:
                        st.warning("Event deleted!")
                        st.session_state['events'] = []
                        st.experimental_rerun()

    # --- Add New Event ---
    with st.expander("➕ Add New Event"):
        default_start = datetime.datetime.utcnow().replace(microsecond=0).isoformat()+"Z"
        default_end = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).replace(microsecond=0).isoformat()+"Z"
        new_title = st.text_input("New Event Title", key="new_title")
        new_desc = st.text_area("Description", key="new_desc")
        new_loc = st.text_input("Location", key="new_loc")
        new_start = st.text_input("Start (ISO8601)", default_start, key="new_start")
        new_end = st.text_input("End (ISO8601)", default_end, key="new_end")
        new_attendees_raw = st.text_input("Attendees (comma-separated emails)", key="new_attendees")

        if st.button("Create Event", key="create_event_button"):
            new_event = default_event_template(new_start, new_end)
            new_event['summary'] = new_title
            new_event['description'] = new_desc
            new_event['location'] = new_loc
            if new_attendees_raw.strip():
                new_event['attendees'] = [{"email": em.strip()} for em in new_attendees_raw.split(",") if em.strip()]
            created = insert_event(service, cal_id, new_event)
            if created:
                st.success(f"Event '{created.get('summary')}' created!")
                st.session_state['events'] = []
                st.experimental_rerun()

    # --- Events Table & Reports ---
    st.divider()
    st.markdown("### 📋 Events Table")
    events_df = events_table(events)
    st.dataframe(events_df, use_container_width=True)

    if not events_df.empty:
        # Offer CSV download
        csv_buffer = io.StringIO()
        events_df.to_csv(csv_buffer, index=False)
        st.download_button("Download table as CSV", data=csv_buffer.getvalue(), file_name="google_calendar_events.csv")

        # PDF Export Button
        if st.button("📄 Export Events to PDF"):
            pdf_bytes = create_pdf_report(events_df)
            st.download_button(
                label="Download PDF Report",
                data=pdf_bytes,
                file_name="calendar_events_report.pdf",
                mime="application/pdf"
            )

else:
    st.info("👈 Please upload your Google service account JSON to get started.\n\n"
            "**Tip:** To access other calendars (e.g. `entremotivator@gmail.com`), share that calendar "
            "with your service account email (found in your JSON credentials file).")

