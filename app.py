import streamlit as st
import json
from datetime import datetime, date, timedelta
import math
from icalendar import Calendar, Event
from io import BytesIO
import unittest
import os
from typing import Dict, List, Tuple

st.set_page_config(page_title="MediRemind", layout="wide")

@st.cache_data
def load_data() -> Dict:
    try:
        with open('mediremind_data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("Data file not found. Starting with empty data.")
        return {"medications": [], "appointments": []}
    except json.JSONDecodeError:
        st.error("Error parsing JSON file. Please check the format.")
        return {"medications": [], "appointments": []}

def save_data(data: Dict) -> None:
    try:
        with open('mediremind_data.json', 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        st.error(f"Error saving data: {e}")

def validate_medication(med: Dict) -> Tuple[bool, str]:
    if not med['name'].strip():
        return False, "Medication name cannot be empty"
    if 'stock' in med:
        if med['stock']['current_quantity'] < 0:
            return False, "Current quantity cannot be negative"
        if med['stock']['consumption_rate'] <= 0:
            return False, "Consumption rate must be positive"
        if med['stock']['alert_threshold'] < 0:
            return False, "Alert threshold cannot be negative"
    return True, ""

def validate_appointment(appt: Dict) -> Tuple[bool, str]:
    try:
        datetime.fromisoformat(appt['date_time'])
    except ValueError:
        return False, "Invalid date/time format"
    return True, ""

def get_next_reminder(med: Dict) -> datetime:
    schedule_time = datetime.strptime(med['schedule'], '%H:%M:%S').time()
    today = datetime.now()
    next_reminder = datetime.combine(today.date(), schedule_time)
    if next_reminder < today:
        next_reminder += timedelta(days=1)
    return next_reminder

def generate_calendar(data: Dict, selected_meds: List[str] = None) -> BytesIO:
    cal = Calendar()
    meds = [med for med in data['medications'] if not selected_meds or med['name'] in selected_meds]
    
    for med in meds:
        event = Event()
        event.add('summary', f'Take {med["name"]}')
        event.add('dtstart', get_next_reminder(med))
        frequency = st.session_state.get(f'freq_{med["name"]}', "daily")
        if frequency == "every_other_day":
            event.add('rrule', {'freq': 'daily', 'interval': 2})
        elif frequency == "weekly":
            event.add('rrule', {'freq': 'weekly', 'byday': 'MO'})
        else:
            event.add('rrule', {'freq': 'daily'})
        cal.add_component(event)
        
        if 'stock' in med:
            current_quantity = med['stock']['current_quantity']
            consumption_rate = med['stock']['consumption_rate']
            alert_threshold = med['stock']['alert_threshold']
            if consumption_rate > 0 and current_quantity > alert_threshold:
                days_until_low = math.ceil((current_quantity - alert_threshold) / consumption_rate)
                notification_date = date.today() + timedelta(days=days_until_low)
                stock_event = Event()
                stock_event.add('summary', f'Refill {med["name"]}')
                stock_event.add('dtstart', datetime(notification_date.year, notification_date.month, notification_date.day))
                cal.add_component(stock_event)
    
    for appt in data['appointments']:
        event = Event()
        event.add('summary', appt.get('description', 'Doctor Appointment'))
        event.add('dtstart', datetime.fromisoformat(appt['date_time']))
        cal.add_component(event)
    
    ics_file = BytesIO()
    ics_file.write(cal.to_ical())
    ics_file.seek(0)
    return ics_file

if 'data' not in st.session_state:
    st.session_state.data = load_data()

st.sidebar.title("MediRemind Navigation")
selected_page = st.sidebar.selectbox("Select a page", ["Home", "Medications", "Doctor Appointments", "Generate Calendar", "Help", "Export/Import"])

if selected_page == "Home":
    st.title("MediRemind - Home")
    st.markdown('<div role="region" aria-label="Upcoming Events Summary">', unsafe_allow_html=True)
    upcoming_events = []
    for med in st.session_state.data['medications']:
        next_reminder = get_next_reminder(med)
        upcoming_events.append({
            'start_time': next_reminder,
            'summary': f'Take {med["name"]}'
        })
        if 'stock' in med:
            current_quantity = med['stock']['current_quantity']
            consumption_rate = med['stock']['consumption_rate']
            alert_threshold = med['stock']['alert_threshold']
            if consumption_rate > 0 and current_quantity > alert_threshold:
                days_until_low = math.ceil((current_quantity - alert_threshold) / consumption_rate)
                notification_date = date.today() + timedelta(days=days_until_low)
                upcoming_events.append({
                    'start_time': datetime(notification_date.year, notification_date.month, notification_date.day),
                    'summary': f'Refill {med["name"]}'
                })
    for appt in st.session_state.data['appointments']:
        date_time = datetime.fromisoformat(appt['date_time'])
        upcoming_events.append({
            'start_time': date_time,
            'summary': appt.get('description', 'Doctor Appointment')
        })
    upcoming_events.sort(key=lambda x: x['start_time'])
    if upcoming_events:
        st.write("Next event:", upcoming_events[0]['summary'], "at", upcoming_events[0]['start_time'].strftime('%Y-%m-%d %H:%M'))
    st.markdown('</div>', unsafe_allow_html=True)

elif selected_page == "Medications":
    st.title("Medications")
    for idx, med in enumerate(st.session_state.data['medications']):
        with st.expander(med['name'], expanded=False):
            new_name = st.text_input("Name", value=med['name'], key=f"name_{idx}", help="Enter the medication name")
            schedule_time = st.time_input("Schedule Time", value=datetime.strptime(med['schedule'], '%H:%M:%S').time(), key=f"schedule_{idx}", help="Set the time to take this medication")
            frequency = st.selectbox("Reminder Frequency", ["daily", "every_other_day", "weekly"], key=f"freq_{med['name']}", help="Choose how often to be reminded")
            st.session_state[f'freq_{med["name"]}'] = frequency
            if 'stock' in med:
                current_quantity = st.number_input("Current Quantity", value=med['stock']['current_quantity'], min_value=0, key=f"quantity_{idx}", help="Number of pills currently available")
                consumption_rate = st.number_input("Consumption Rate (per day)", value=med['stock']['consumption_rate'], min_value=0, key=f"rate_{idx}", help="How many pills you take daily")
                alert_threshold = st.number_input("Alert Threshold", value=med['stock']['alert_threshold'], min_value=0, key=f"threshold_{idx}", help="Notify when stock falls below this amount")
                if st.button("Remove Stock Information", key=f"remove_stock_{idx}"):
                    del med['stock']
            else:
                if st.button("Add Stock Information", key=f"add_stock_{idx}"):
                    med['stock'] = {
                        "current_quantity": 0,
                        "consumption_rate": 0,
                        "alert_threshold": 0
                    }
            if st.button("Delete Medication", key=f"delete_med_{idx}"):
                st.session_state.data['medications'].pop(idx)
            med['name'] = new_name
            med['schedule'] = schedule_time.strftime('%H:%M:%S')
            is_valid, error = validate_medication(med)
            if not is_valid:
                st.error(error)
    if st.button("Add New Medication"):
        new_med = {
            "name": "",
            "schedule": "00:00:00"
        }
        st.session_state.data['medications'].append(new_med)
    if st.button("Save Changes"):
        has_errors = False
        for med in st.session_state.data['medications']:
            is_valid, error = validate_medication(med)
            if not is_valid:
                st.error(error)
                has_errors = True
        if not has_errors:
            save_data(st.session_state.data)
            st.toast("Changes saved successfully")

elif selected_page == "Doctor Appointments":
    st.title("Doctor Appointments")
    for idx, appt in enumerate(st.session_state.data['appointments']):
        with st.expander(appt.get('description', 'Appointment'), expanded=False):
            date_input = st.date_input("Date", value=datetime.fromisoformat(appt['date_time']).date(), key=f"date_{idx}", help="Select the appointment date")
            time_input = st.time_input("Time", value=datetime.fromisoformat(appt['date_time']).time(), key=f"time_{idx}", help="Select the appointment time")
            description = st.text_area("Description", value=appt.get('description', ''), key=f"desc_{idx}", help="Describe the appointment purpose")
            if st.button("Delete Appointment", key=f"delete_appt_{idx}"):
                st.session_state.data['appointments'].pop(idx)
            new_datetime = datetime.combine(date_input, time_input).isoformat()
            appt['date_time'] = new_datetime
            appt['description'] = description
            is_valid, error = validate_appointment(appt)
            if not is_valid:
                st.error(error)
    if st.button("Add New Appointment"):
        new_appt = {
            "date_time": datetime.now().isoformat(),
            "description": ""
        }
        st.session_state.data['appointments'].append(new_appt)
    if st.button("Save Changes"):
        has_errors = False
        for appt in st.session_state.data['appointments']:
            is_valid, error = validate_appointment(appt)
            if not is_valid:
                st.error(error)
                has_errors = True
        if not has_errors:
            save_data(st.session_state.data)
            st.toast("Changes saved successfully")

elif selected_page == "Generate Calendar":
    st.title("Generate Calendar")
    st.markdown('<div role="region" aria-label="Calendar Generation Options">', unsafe_allow_html=True)
    med_names = [med['name'] for med in st.session_state.data['medications']]
    selected_meds = st.multiselect("Select medications to include", med_names, help="Choose which medications to include in the calendar")
    if st.button("Generate and Download Calendar"):
        ics_file = generate_calendar(st.session_state.data, selected_meds)
        st.download_button(
            label="Download Calendar",
            data=ics_file,
            file_name="mediremind.ics",
            mime="text/calendar"
        )
        st.toast("Calendar generated and downloaded successfully")
    st.markdown('</div>', unsafe_allow_html=True)

elif selected_page == "Export/Import":
    st.title("Data Export/Import")
    if st.button("Export Data"):
        st.download_button("Download Data", json.dumps(st.session_state.data), "mediremind_data.json", "text/json")
        st.toast("Data exported successfully")
    uploaded_file = st.file_uploader("Import Data", type="json", help="Upload a JSON file to restore your data")
    if uploaded_file:
        try:
            new_data = json.load(uploaded_file)
            if not isinstance(new_data, dict) or 'medications' not in new_data or 'appointments' not in new_data:
                st.error("Invalid data format. Please upload a valid MediRemind JSON file.")
            st.stop()
            for med in new_data['medications']:
                is_valid, error = validate_medication(med)
                if not is_valid:
                    st.error(f"Invalid medication: {error}")
                    st.stop()
            for appt in new_data['appointments']:
                is_valid, error = validate_appointment(appt)
                if not is_valid:
                    st.error(f"Invalid appointment: {error}")
                    st.stop()
            st.session_state.data = new_data
            save_data(st.session_state.data)
            st.toast("Data imported successfully")
        except json.JSONDecodeError:
            st.error("Invalid JSON file format")
        except Exception as e:
            st.error(f"Error importing data: {e}")

elif selected_page == "Help":
    st.title("MediRemind Help")
    st.markdown("""
    ### How to Use MediRemind
    - **Home**: View upcoming medication reminders and appointments.
    - **Medications**: Add, edit, or delete medications, including schedules and stock tracking. Use the "Save Changes" button to persist updates.
    - **Doctor Appointments**: Schedule and manage doctor visits with dates, times, and descriptions.
    - **Generate Calendar**: Select medications to include in your calendar and download an `.ics` file for reminders.
    - **Export/Import**: Backup your data by exporting to a JSON file or restore data by importing a valid JSON file.
    - **Tips**:
      - Ensure medication names are not empty and stock quantities are positive.
      - Use the calendar export to set reminders in your preferred app (e.g., Google Calendar).
    """)

save_data(st.session_state.data)

class TestMediRemind(unittest.TestCase):
    def setUp(self):
        self.test_data = {"medications": [], "appointments": []}
    
    def test_load_data_file_not_found(self):
        if os.path.exists('mediremind_data.json'):
            os.remove('mediremind_data.json')
        result = load_data()
        self.assertEqual(result, {"medications": [], "appointments": []})
    
    def test_validate_medication_invalid_name(self):
        med = {"name": "", "schedule": "00:00:00"}
        is_valid, error = validate_medication(med)
        self.assertFalse(is_valid)
        self.assertEqual(error, "Medication name cannot be empty")
    
    def test_validate_appointment_invalid_datetime(self):
        appt = {"date_time": "invalid", "description": ""}
        is_valid, error = validate_appointment(appt)
        self.assertFalse(is_valid)
        self.assertEqual(error, "Invalid date/time format")

if __name__ == "__main__":
    pass
