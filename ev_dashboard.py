import streamlit as st
import pandas as pd
import datetime

# Initialize session state for data
if 'charging_data' not in st.session_state:
    st.session_state.charging_data = pd.DataFrame(columns=['Car', 'Battery %', 'Station', 'Start Time'])

if 'waitlist' not in st.session_state:
    st.session_state.waitlist = {i: [] for i in range(1, 13)}  # station numbers 1 to 12

if 'pending_reservations' not in st.session_state:
    st.session_state.pending_reservations = {}  # station: (user, timestamp)

st.title("EV Charging Station Dashboard")

st.subheader("Park and Charge")
with st.form("charging_form"):
    car = st.text_input("Car Number / Model")
    battery = st.number_input("Battery %", min_value=0, max_value=100, step=1)
    station = st.selectbox("Charging Station Number", list(range(1, 13)))
    submit = st.form_submit_button("Start Charging")

    if submit:
        occupied_stations = st.session_state.charging_data['Station'].tolist()
        if station in occupied_stations:
            st.warning(f"Station {station} is already occupied. Adding you to the waitlist.")
            st.session_state.waitlist[station].append({'Car': car, 'Battery %': battery, 'Request Time': datetime.datetime.now()})
        else:
            new_entry = pd.DataFrame([[car, battery, station, datetime.datetime.now()]], columns=st.session_state.charging_data.columns)
            st.session_state.charging_data = pd.concat([st.session_state.charging_data, new_entry], ignore_index=True)
            st.success(f"Car parked at station {station}.")

st.subheader("Current Charging Status")
now = datetime.datetime.now()
data = st.session_state.charging_data.copy()
data['Duration (mins)'] = data['Start Time'].apply(lambda t: int((now - t).total_seconds() / 60))
data['Overdue'] = data['Duration (mins)'] > 120
st.dataframe(data)

st.subheader("Free a Charging Station")
station_to_remove = st.selectbox("Select a station to free", list(range(1, 13)))
if st.button("Free Station"):
    initial_count = len(st.session_state.charging_data)
    st.session_state.charging_data = st.session_state.charging_data[st.session_state.charging_data['Station'] != station_to_remove]
    if len(st.session_state.charging_data) < initial_count:
        st.success(f"Station {station_to_remove} is now free.")

        # Trigger reservation for next person in waitlist
        if st.session_state.waitlist[station_to_remove]:
            next_user = st.session_state.waitlist[station_to_remove].pop(0)
            st.session_state.pending_reservations[station_to_remove] = (next_user, datetime.datetime.now())
            st.info(f"Reservation for station {station_to_remove} held for {next_user['Car']} for 5 minutes.")
    else:
        st.warning("That station was already free.")

# Check reservation timeouts
for station, (user, timestamp) in list(st.session_state.pending_reservations.items()):
    if (now - timestamp).total_seconds() > 300:  # 5 minutes
        st.warning(f"Reservation expired for {user['Car']} at station {station}.")
        del st.session_state.pending_reservations[station]
        if st.session_state.waitlist[station]:
            next_user = st.session_state.waitlist[station].pop(0)
            st.session_state.pending_reservations[station] = (next_user, datetime.datetime.now())
            st.info(f"Reservation passed to {next_user['Car']} at station {station}.")

st.subheader("Pending Reservations")
if st.session_state.pending_reservations:
    for station, (user, timestamp) in st.session_state.pending_reservations.items():
        remaining_time = 300 - int((now - timestamp).total_seconds())
        st.write(f"Station {station} reserved for {user['Car']} for {remaining_time} more seconds.")
else:
    st.write("No active reservations.")

st.subheader("Waitlist View")
for station in range(1, 13):
    if st.session_state.waitlist[station]:
        st.write(f"Station {station} waitlist: {[user['Car'] for user in st.session_state.waitlist[station]]}")
