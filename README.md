 A Flask-based web application for managing event registrations, payments, feedback, and reports.

📌 Features
✅ User Roles:

Organizers (Create & manage events)

Attendees (Register for events & submit feedback)

✅ Event Management:

Create, view, and manage events

Track registrations and payments

✅ Registration & Payments:

Attendees can register for events

Payment tracking (Pending/Completed/Failed)

✅ Feedback System:

Attendees can submit ratings & comments

Organizers can view feedback

✅ Reports & Photos:

Organizers can generate event reports

Upload photos for reports

✅ User Profiles:

Profile photo uploads

Personal details management

⚙️ Setup & Installation
1. Prerequisites
Python 3.8+

MySQL (or MariaDB)

pip (Python package manager)

2. Clone the Repository
bash
git clone https://github.com/your-repo/event-registration-portal.git
cd event-registration-portal
3. Set Up a Virtual Environment (Optional but Recommended)
bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
4. Install Dependencies
bash
pip install -r requirements.txt
(If requirements.txt doesn’t exist, install manually:)

bash
pip install flask mysql-connector-python flask-mail werkzeug
5. Database Setup
Create a MySQL database:

sql
CREATE DATABASE EventRegistrationDB;
USE EventRegistrationDB;
Run the SQL schema script (from database_setup.sql or manually execute the SQL commands).

Configure config.py:

python
DB_CONFIG = {
    'host': 'localhost',
    'user': 'your_mysql_username',
    'password': 'your_mysql_password',
    'database': 'EventRegistrationDB'
}
6. Configure Email (Optional for Notifications)
Update app.py with your SMTP settings:

python
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your_email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your_app_password'  # Use an App Password for Gmail
7. Run the Application
bash
python app.py
(or flask run if using Flask CLI)

🔹 Access the app at: http://127.0.0.1:5000

