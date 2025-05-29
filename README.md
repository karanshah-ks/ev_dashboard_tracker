📍 Problem Statement
At our office, we have 17 EV charging stations split across two floors (5 on 1st floor and 12 on 3rd). However, there was no organized system to track usage. Common issues included:
People leaving cars for too long even after charging completed
No visibility into which stations were occupied
No fair queueing system for those waiting to charge
Lack of accountability on who was charging and for how long

✅ Solution
To solve this, I built an interactive web app using Streamlit that allows:
Drivers to register their EV when they start charging (with time, battery %, and station number)
Auto-removal of entries after 2 hours and ability to free up station manually using a PIN
If all stations are full, users can join a global waitlist
As soon as someone frees a station:
The first person in the waitlist is notified via Slack
If they don’t claim it in 5 mins, the next person is notified automatically

The app shows:
Real-time charging status
Waitlist order
Pending reservations
A daily reset at 8 PM CST clears the app and archives the data for future analytics
The app is mobile-friendly, styled in Amazon dark theme, and includes a feedback form

⚙️ Tech Stack
Frontend & UI: Streamlit (Python-based UI framework)
Backend: SQLite database for all session storage
Notifications: Slack Webhooks for real-time reservation alerts
Time Zone Handling: pytz for Austin (CST) timing
Hosting: Streamlit Cloud
Version Control: Git + GitHub

🧠 Key Features
👤 Work-alias based entry (e.g., karvsha) for identity and Slack mentions
🔐 PIN protection to prevent others from freeing your station
📋 Clean waitlist and reservation management
🔄 Auto-reset with archive tables for future reporting
