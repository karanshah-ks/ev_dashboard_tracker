import streamlit as st
import pandas as pd
import sqlite3
import datetime
import os
import requests
import pytz

DB_PATH = "ev_charging.db"
SLACK_WEBHOOK_URL = st.secrets["slack"]["webhook_url"]
TZ = pytz.timezone("America/Chicago")  # Austin, TX time zone

# --- Inject Dark Theme with Amazon Colors and UI Enhancements ---
st.markdown("""
    <style>
        body, .stApp {
            background-color: #212626;
            color: #f0f2f6;
        }
        .stButton>button {
            background-color: #ff9900 !important;
            color: #000000 !important;
            font-weight: bold;
            border-radius: 8px;
            padding: 0.5em 1em;
        }
        input, .stTextInput input,
        .stNumberInput input,
        .stSelectbox input,
        .stTextArea textarea {
            background-color: #232f3e !important;
            color: #ffffff !important;
        }
        label, .stMarkdown, .css-1cpxqw2, .css-1y4p8pa {
            color: #f0f2f6 !important;
        }
        .stDataFrame, .stDataFrame table {
            background-color: #1a1a1a;
            color: #ffffff;
        }
        h1, h2, h3, h4, h5, h6 {
            color: #ff9900 !important;
        }
        .sidebar-content {
            display: none;
        }
        a {
            color: #00afff !important;
        }
    </style>
    <div style="display:flex; align-items:center; justify-content:space-between; gap:1rem; margin-bottom: 1rem;">
        <div>
            <img src="https://upload.wikimedia.org/wikipedia/commons/d/de/Amazon_icon.png" width="50"/>
        </div>
        <div>
            <h1 style="color:#ff9900;">AUS20 EV Charging Tracker</h1>
            <p style="color:#f0f2f6; font-size: 14px;">
                📬 Please reach out to <strong><a href='https://amazon.slack.com/team/karvsha' target='_blank'>@karvsha</a></strong> on Slack for any issues or feedback.<br>
                📝 <a href='https://quip-amazon.com/xyz-feedback-form' target='_blank'>Submit feedback here</a>
            </p>
        </div>
    </div>
""", unsafe_allow_html=True)

# --- Slack Notification Function ---
def send_slack_notification(message):
    payload = {"text": message}
    try:
        requests.post(SLACK_WEBHOOK_URL, json=payload)
    except Exception as e:
        st.error(f"Slack notification failed: {e}")

# --- DATABASE CONNECTION ---
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# --- DATABASE SETUP ---
def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS charging (
                    alias TEXT,
                    car TEXT,
                    battery INTEGER,
                    station INTEGER,
                    start_time TEXT,
                    pin TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS waitlist (
                    alias TEXT,
                    car TEXT,
                    battery INTEGER,
                    request_time TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS reservations (
                    alias TEXT PRIMARY KEY,
                    timestamp TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS archive_charging (
                    alias TEXT,
                    car TEXT,
                    battery INTEGER,
                    station INTEGER,
                    start_time TEXT,
                    pin TEXT,
                    archived_on TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS archive_waitlist (
                    alias TEXT,
                    car TEXT,
                    battery INTEGER,
                    request_time TEXT,
                    archived_on TEXT
                )''')
    conn.commit()
    conn.close()

# --- RESET AT 8PM CST ---
def auto_reset(force=False):
    conn = get_conn()
    c = conn.cursor()
    now = datetime.datetime.now(TZ)
    current_date = now.date().isoformat()

    c.execute("SELECT value FROM metadata WHERE key='last_reset'")
    row = c.fetchone()

    should_reset = force or (not row or row[0] < current_date and now.hour >= 20)

    if should_reset:
        archived_on = now.isoformat()
        c.execute("INSERT INTO archive_charging SELECT *, ? FROM charging", (archived_on,))
        c.execute("INSERT INTO archive_waitlist SELECT *, ? FROM waitlist", (archived_on,))
        c.execute("DELETE FROM charging")
        c.execute("DELETE FROM waitlist")
        c.execute("DELETE FROM reservations")
        c.execute("REPLACE INTO metadata (key, value) VALUES ('last_reset', ?)", (current_date,))
        conn.commit()

    conn.close()

# --- INITIALIZE ---
init_db()
auto_reset()

#st.title("🔌 EV Charging Station Dashboard")
conn = get_conn()
c = conn.cursor()

# --- STATION SETUP: 5 on Floor 1 (101–105), 12 on Floor 3 (301–312) ---
ALL_STATIONS = list(range(101, 106)) + list(range(301, 313))

# --- SHOW AVAILABLE STATIONS ---
c.execute("SELECT station FROM charging")
occupied = [row[0] for row in c.fetchall()]
available_stations = [s for s in ALL_STATIONS if s not in occupied]

if available_stations:
    st.success(f"✅ Available Stations: {available_stations}")
else:
    st.warning("❌ All stations are currently occupied.")

# --- CHARGING FORM ---
if available_stations:
    st.markdown("## 🚗 Start Charging")
    with st.form("charge_form"):
        alias = st.text_input("Your Work Alias (e.g. karvsha)")
        car = st.text_input("Car Number / Model")
        battery = st.number_input("Battery %", 0, 100, step=1)
        station = st.selectbox("Choose from available stations", available_stations)
        pin = st.text_input("Enter a 4-digit PIN to manage your session later", max_chars=4, type="password")
        submit = st.form_submit_button("Start Charging")

        if submit:
            now = datetime.datetime.now(TZ)
            c.execute("SELECT * FROM charging WHERE station=?", (station,))
            if c.fetchone():
                st.error("Station just got occupied. Please refresh.")
            else:
                c.execute("INSERT INTO charging VALUES (?, ?, ?, ?, ?, ?)", (alias, car, battery, station, now.isoformat(), pin))
                c.execute("DELETE FROM reservations WHERE alias=?", (alias,))
                c.execute("DELETE FROM waitlist WHERE alias=?", (alias,))
                st.success(f"Charging started at station {station}")
            conn.commit()
# --- JOIN WAITLIST ---
st.markdown("## 📝 Join the Waitlist")
with st.form("waitlist_form"):
    w_alias = st.text_input("Your Work Alias", key="waitlist_alias")
    w_car = st.text_input("Car Number / Model", key="waitlist_car")
    w_battery = st.number_input("Battery %", 0, 100, step=1, key="waitlist_battery")
    join = st.form_submit_button("Join Waitlist")

    if join:
        now = datetime.datetime.now()
        c.execute("SELECT 1 FROM waitlist WHERE alias=?", (w_alias,))
        if not c.fetchone():
            c.execute("INSERT INTO waitlist VALUES (?, ?, ?, ?)", (w_alias, w_car, w_battery, now.isoformat()))
            st.success("You've been added to the waitlist.")
        else:
            st.info("You're already in the waitlist.")
        conn.commit()

# --- VIEW CURRENT WAITLIST ---
st.markdown("## 📋 Current Waitlist")
c.execute("SELECT alias, car, battery, request_time FROM waitlist ORDER BY request_time")
waitlist_data = c.fetchall()
if waitlist_data:
    waitlist_df = pd.DataFrame(waitlist_data, columns=["Alias", "Car", "Battery %", "Requested At"])
    st.dataframe(waitlist_df)
else:
    st.info("No one in the waitlist right now.")

# --- FREE STATION FORM ---
st.markdown("## ❌ Free Your Station")
with st.form("free_form"):
    station_to_free = st.selectbox("Station to free", ALL_STATIONS, key="free_select")
    input_pin = st.text_input("Enter your 4-digit PIN", max_chars=4, type="password")
    free_submit = st.form_submit_button("Free Station")

    if free_submit:
        c.execute("SELECT pin FROM charging WHERE station=?", (station_to_free,))
        row = c.fetchone()
        if row and row[0] == input_pin:
            c.execute("DELETE FROM charging WHERE station=?", (station_to_free,))
            st.success(f"Station {station_to_free} is now free")
            c.execute("SELECT alias FROM waitlist ORDER BY request_time")
            next_wait = c.fetchone()
            if next_wait:
                alias = next_wait[0]
                c.execute("DELETE FROM waitlist WHERE alias=?", (alias,))
                c.execute("REPLACE INTO reservations VALUES (?, ?)", (alias, datetime.datetime.now().isoformat()))
                send_slack_notification(f"🔔 <@{alias}> A charging spot is available! Please claim any open station within 5 minutes.")
                st.info(f"Reservation granted to {alias} and notification sent.")
            conn.commit()
        else:
            st.error("Incorrect PIN. Access denied.")

# --- RESERVATIONS VIEW AND AUTO-EXPIRY ---
st.markdown("## ⏳ Pending Reservations")
c.execute("SELECT * FROM reservations")
reservations = c.fetchall()
now = datetime.datetime.now()
if reservations:
    for alias, timestamp in reservations:
        reserved_time = datetime.datetime.fromisoformat(timestamp)
        seconds = 300 - int((now - reserved_time).total_seconds())
        if seconds > 0:
            st.write(f"@{alias} has {seconds} seconds left to claim a spot.")
        else:
            c.execute("DELETE FROM reservations WHERE alias=?", (alias,))
            c.execute("SELECT alias FROM waitlist ORDER BY request_time")
            next_wait = c.fetchone()
            if next_wait:
                new_alias = next_wait[0]
                c.execute("DELETE FROM waitlist WHERE alias=?", (new_alias,))
                c.execute("REPLACE INTO reservations VALUES (?, ?)", (new_alias, datetime.datetime.now().isoformat()))
                send_slack_notification(f"🔔 <@{new_alias}> A charging spot is now available! Please claim any open station within 5 minutes.")
                st.info(f"Reservation moved to {new_alias} and notification sent.")
    conn.commit()
else:
    st.info("No active reservations.")

# --- CURRENT STATUS ---
st.markdown("## 📊 Charging Status")
c.execute("SELECT * FROM charging")
data = c.fetchall()
df = pd.DataFrame(data, columns=["Alias", "Car", "Battery %", "Station", "Start Time", "PIN"])
if not df.empty:
    df["Start Time"] = pd.to_datetime(df["Start Time"])

    # Handle tz-aware vs tz-naive safely
    if df["Start Time"].dt.tz is None:
        df["Start Time"] = df["Start Time"].dt.tz_localize("UTC").dt.tz_convert(TZ)
    else:
        df["Start Time"] = df["Start Time"].dt.tz_convert(TZ)

    now = pd.Timestamp.now(tz=TZ)
    df["Time Elapsed (min)"] = (now - df["Start Time"]).dt.total_seconds() // 60
    df["Overstayed"] = df["Time Elapsed (min)"] > 120
    st.dataframe(df[["Alias", "Car", "Battery %", "Station", "Start Time", "Time Elapsed (min)", "Overstayed"]])
else:
    st.info("No cars charging.")

# --- ADMIN RESET CONTROL ---
st.markdown("## 🔐 Admin Controls")
admin_alias = st.text_input("Enter your alias to unlock admin controls:")

if admin_alias.strip().lower() == "evchargingkaran":
    if st.button("🔁 Admin: Reset Charging & Waitlist"):
        auto_reset(force=True)
        st.success("Reset executed successfully.")


conn.close()
