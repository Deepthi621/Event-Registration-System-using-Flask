from flask import Flask, render_template, request, redirect, session, flash, url_for # Added url_for just in case
import mysql.connector
from config import DB_CONFIG
from datetime import datetime, date, time
import os
import re
from threading import Thread # Import Thread
from flask_mail import Mail, Message
# import smtplib # Not strictly needed if using Flask-Mail
from markupsafe import escape
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

app = Flask(__name__)
app.secret_key = 'your_secure_secret_key' # Consider using environment variables
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.logger.addHandler(handler)
app.logger.setLevel(logging.DEBUG)

# Configure Flask-Mail (make sure these match your config.py)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'bhavanabc05@gmail.com' # Use environment variable
# WARNING: Ensure there are no trailing spaces in your password!
app.config['MAIL_PASSWORD'] = 'tcssykfzmkyspleh'  # Use environment variable and ACTUAL app password
app.config['MAIL_DEFAULT_SENDER'] = ('Event Portal', 'bhavanabc05@gmail.com') # Use MAIL_DEFAULT_SENDER
mail = Mail(app)


def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        app.logger.error(f"Database connection error: {err}") # Log DB errors
        flash(f"Database connection error. Please try again later.", 'error') # User-friendly message
        return None

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Helper Function for Async Email ---
def send_async_email(app_context, msg):
    """Sends email in a separate thread."""
    with app_context: # Need app context for Flask-Mail to work correctly in a thread
        try:
            mail.send(msg)
            app.logger.info(f"Welcome email sent successfully to {msg.recipients[0]}")
        except Exception as e:
            app.logger.error(f"Failed to send welcome email to {msg.recipients[0]}: {str(e)}")
            # You might want to add more robust error handling here,
            # like retrying or notifying an admin

# ----------------------
# Routes
# ----------------------

@app.route('/')
def home():
    # Check for flash messages from registration/login if needed
    return render_template('index.html')

@app.route('/test-email')
def test_email():
    try:
        # Use default sender from config
        msg = Message('Test Email from Event Portal',
                      recipients=['2023cs_bhavanabc_a@nie.ac.in']) # Send to your test recipient
        msg.body = f"This is a test email sent at {datetime.now()} from your Flask app configured with Flask-Mail."
        # Optional: Add HTML body
        # msg.html = "<h1>Test Email</h1><p>This is a <b>test</b> email.</p>"

        # Send synchronously for testing purposes
        mail.send(msg)

        app.logger.info("Test email sent successfully!")
        return "Test Email sent successfully!"
    except Exception as e:
        app.logger.error(f"Error sending test email: {str(e)}")
        return f"Error sending test email: {str(e)}"


@app.route('/register', methods=['POST'])
def register_user():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password') # Consider hashing the password!
    role = request.form.get('role')

    # Basic Validation (Add more robust validation as needed)
    if not all([name, email, password, role]):
        flash("All fields are required!", 'error')
        return redirect(url_for('home')) # Redirect to home or specific registration page

    # Email format validation (simple example)
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
         flash("Invalid email format!", 'error')
         return redirect(url_for('home'))

    conn = get_db_connection()
    if not conn:
        # Flash message is already set in get_db_connection
        return redirect(url_for('home'))

    try:
        with conn.cursor() as cursor:
            # Check if email already exists
            cursor.execute("SELECT Email FROM Users WHERE Email = %s", (email,))
            existing_user = cursor.fetchone()
            if existing_user:
                flash("Email already exists! Please login or use a different email.", 'error')
                conn.close()
                return redirect(url_for('home'))

            # **IMPORTANT: Hash the password before storing!**
            # Use a library like werkzeug.security or passlib
            # Example using werkzeug (install with pip install Werkzeug):
            # from werkzeug.security import generate_password_hash
            # hashed_password = generate_password_hash(password)
            # For now, storing plain text as per original code, but strongly advise against it.
            hashed_password = password # Replace with actual hashing

            cursor.execute(
                "INSERT INTO Users (Name, Email, Password, Role) VALUES (%s, %s, %s, %s)",
                (name, email, hashed_password, role) # Store hashed password
            )
            conn.commit()
            app.logger.info(f"User {email} registered successfully.")

            # --- Send Welcome Email (Asynchronously) ---
            try:
                msg_subject = "Welcome to Event Portal!"
                # You can create an HTML template for a nicer email
                # msg_html = render_template('emails/welcome.html', user_name=name)
                msg_body = f"Hi {escape(name)},\n\nThank you for registering at Event Portal.\nWe're excited to have you!\n\nYou can now log in using your email address.\n\nBest regards,\nThe Event Portal Team"

                msg = Message(subject=msg_subject,
                              recipients=[email],
                              body=msg_body)
                              # html=msg_html) # Uncomment if using HTML email

                # Pass the app context to the thread
                thread = Thread(target=send_async_email, args=[app.app_context(), msg])
                thread.start()
                # If you wanted synchronous sending (not recommended for web requests):
                # mail.send(msg)
                # app.logger.info(f"Welcome email sent successfully to {email}")

            except Exception as e:
                # Log the error, but don't stop the user registration flow
                app.logger.error(f"Failed to *initiate* sending welcome email to {email}: {str(e)}")
                # You could flash a milder warning if needed, but generally logging is sufficient
                # flash("Registration successful, but couldn't send welcome email.", 'warning')
                flash("Registration successful! Please check your email (optional) and login.", "success")


    # It's better to catch specific errors if possible
    except mysql.connector.IntegrityError: # Handles race conditions if email check fails
        flash("Email already exists!", 'error')
        app.logger.warning(f"Registration attempt failed for existing email: {email}")
    except mysql.connector.Error as err:
        flash(f"Registration failed due to a database error. Please try again later.", 'error') # User-friendly message
        app.logger.error(f"Registration database error for {email}: {err}")
    except Exception as e:
        flash("An unexpected error occurred during registration. Please try again later.", 'error')
        app.logger.error(f"Unexpected registration error for {email}: {e}", exc_info=True) # Log stack trace
    finally:
        if conn and conn.is_connected():
            conn.close()

    return redirect(url_for('home')) # Redirect to home or login page

# ... (rest of your routes and main execution block) ...

@app.route('/login', methods=['POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')

    conn = get_db_connection()
    if not conn:
        return redirect('/')

    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT * FROM Users WHERE Email = %s AND Password = %s",
                (email, password)
            )
            user = cursor.fetchone()

            if user:
                session['user_id'] = user['UserID']
                session['role'] = user['Role']
                return redirect('/dashboard')

            flash("Invalid credentials!", 'error')
    except mysql.connector.Error as err:
        flash(f"Login error: {err}", 'error')
    finally:
        conn.close()

    return redirect('/')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/')

    conn = get_db_connection()
    if not conn:
        return redirect('/')

    try:
        with conn.cursor(dictionary=True) as cursor:
            if session['role'] == 'Organizer':
                # Existing organizer dashboard logic
                cursor.execute("""
                    SELECT E.*,
                           COUNT(CASE WHEN R.Status = 'Active' THEN 1 END) AS active_registrations,
                           COALESCE(SUM(CASE WHEN P.Status = 'Completed' THEN P.Amount ELSE 0 END), 0) AS total_collected,
                           (SELECT COUNT(*) FROM Feedback WHERE EventID = E.EventID) AS feedback_count,
                           TIME_FORMAT(StartTime, '%H:%i') AS StartTime,
                           TIME_FORMAT(EndTime, '%H:%i') AS EndTime
                    FROM Events E
                    LEFT JOIN Registrations R ON E.EventID = R.EventID
                    LEFT JOIN Payments P ON R.RegistrationID = P.RegistrationID
                    WHERE E.OrganizerID = %s
                    GROUP BY E.EventID
                """, (session['user_id'],))
                events = cursor.fetchall()

                cursor.execute("""
                    SELECT E.EventName, 
                           U.Name AS attendee_name,
                           U.Email AS attendee_email,
                           COALESCE(P.Amount, 0) AS Amount,
                           COALESCE(P.Status, 'Pending') AS payment_status,
                           R.Status AS registration_status
                    FROM Registrations R
                    JOIN Events E ON R.EventID = E.EventID
                    JOIN Users U ON R.UserID = U.UserID
                    LEFT JOIN Payments P ON R.RegistrationID = P.RegistrationID
                    WHERE E.OrganizerID = %s 
                      AND R.Status = 'Active'
                """, (session['user_id'],))
                registrations = cursor.fetchall()

                total_collected = sum(float(event.get('total_collected', 0)) for event in events)
                total_feedback = sum(int(event.get('feedback_count', 0)) for event in events)

                # Get past events for report creation
                cursor.execute("""
                    SELECT EventID, EventName, Date 
                    FROM Events 
                    WHERE OrganizerID = %s AND Date < CURDATE()
                """, (session['user_id'],))
                past_events = cursor.fetchall()

                return render_template(
                    'organizer_dashboard.html',
                    events=events,
                    registrations=registrations,
                    current_date=date.today(),
                    total_collected=total_collected,
                    total_feedback=total_feedback,
                    past_events=past_events
                )

            else:
                # Attendee Dashboard Logic
                cursor.execute("""
                    SELECT E.*,
                           EXISTS(
                               SELECT 1 FROM Registrations R
                               WHERE R.EventID = E.EventID
                                 AND R.UserID = %s
                                 AND R.Status = 'Active'
                           ) AS is_registered,
                           (SELECT R.RegistrationID 
                            FROM Registrations R
                            WHERE R.EventID = E.EventID
                              AND R.UserID = %s
                              AND R.Status = 'Active' 
                            LIMIT 1) AS registration_id,
                           (SELECT R.Status 
                            FROM Registrations R
                            WHERE R.EventID = E.EventID
                              AND R.UserID = %s 
                            LIMIT 1) AS registration_status
                    FROM Events E
                    WHERE E.Date >= CURDATE()
                """, (session['user_id'], session['user_id'], session['user_id']))
                events = cursor.fetchall()

                return render_template('attendee_dashboard.html', events=events)

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", 'error')
        return redirect('/')
    except Exception as e:
        flash(f"Unexpected error: {str(e)}", 'error')
        return redirect('/')
    finally:
        if conn:
            conn.close()

# ----------------------
# Report Routes
# ----------------------

@app.route('/event-reports')
def event_reports():
    if 'user_id' not in session or session.get('role') != 'Organizer':
        return redirect('/')

    conn = get_db_connection()
    if not conn:
        return redirect('/')

    try:
        with conn.cursor(dictionary=True) as cursor:
            # Fetch reports first
            cursor.execute("""
                SELECT 
                    r.ReportID,
                    r.Content,
                    r.CreatedAt,
                    e.EventName,
                    e.Date AS EventDate,
                    GROUP_CONCAT(rp.filename) AS photos 
                FROM Reports r
                JOIN Events e ON r.EventID = e.EventID
                LEFT JOIN ReportPhotos rp ON r.ReportID = rp.ReportID
                WHERE e.OrganizerID = %s
                GROUP BY r.ReportID
                ORDER BY r.CreatedAt DESC
            """, (session['user_id'],))
            reports = cursor.fetchall()

            # Process reports
            for report in reports:
                report['Content'] = report['Content'].replace('\n', '<br>')
                report['photos'] = report['photos'].split(',') if report['photos'] else []

            # Fetch past events
            cursor.execute("""
                SELECT EventID, EventName, Date 
                FROM Events 
                WHERE OrganizerID = %s AND Date < CURDATE()
                ORDER BY Date DESC
            """, (session['user_id'],))
            past_events = cursor.fetchall()

            # Create template
            report_template = """📋 EVENT REPORT TEMPLATE

Event Name: [Enter event name]
Date: [Enter date]
Venue: [Enter venue]
Organized By: [Enter organizer]

Introduction:
[Write a brief introduction about the event's purpose and objectives]

Event Details:
[Describe what happened during the event, including timeline and activities]

Highlights:
[List key moments, special attractions, or notable participants]

Outcome/Conclusion:
[Summarize the event's success, learnings, and future plans]"""

            return render_template('event_report.html',
                                reports=reports,
                                past_events=past_events,
                                report_template=report_template,
                                current_date=datetime.now().date())

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", 'error')
        return redirect('/dashboard')
    finally:
        if conn:
            conn.close()

from werkzeug.utils import secure_filename
from datetime import datetime
import os

# ... other imports ...

@app.route('/create-report', methods=['POST'])
def create_report():
    if 'user_id' not in session or session.get('role') != 'Organizer':
        return redirect('/')

    # Validate form inputs
    if not request.form.get('event_id') or not request.form.get('content'):
        flash("All required fields must be filled", 'error')
        return redirect('/event-reports')

    try:
        event_id = int(request.form['event_id'])
    except ValueError:
        flash("Invalid event selection", 'error')
        return redirect('/event-reports')

    content = request.form['content'].strip()
    files = request.files.getlist('photos')

    conn = get_db_connection()
    if not conn:
        return redirect('/event-reports')

    try:
        with conn.cursor() as cursor:
            # Verify event ownership and validity
            cursor.execute("""
                SELECT EventID FROM Events 
                WHERE EventID = %s 
                AND OrganizerID = %s 
                AND Date < CURDATE()
                LIMIT 1
            """, (event_id, session['user_id']))
            if not cursor.fetchone():
                flash("Invalid event selection", 'error')
                return redirect('/event-reports')

            # Check for existing report
            cursor.execute("""
                SELECT ReportID FROM Reports
                WHERE EventID = %s
                LIMIT 1
            """, (event_id,))
            if cursor.fetchone():
                flash("A report already exists for this event", 'error')
                return redirect('/event-reports')

            # Create report
            cursor.execute("""
                INSERT INTO Reports (EventID, Content)
                VALUES (%s, %s)
            """, (event_id, content))
            report_id = cursor.lastrowid

            # Handle file uploads securely
            for file in files[:6]:  # Limit to 6 files
                if file and file.filename != '':
                    if not allowed_file(file.filename):
                        flash("Invalid file type", 'error')
                        continue

                    # Secure filename handling
                    original_filename = secure_filename(file.filename)
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    filename = f"{timestamp}_{original_filename}"
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    
                    # Save file and record in database
                    file.save(file_path)
                    cursor.execute("""
                        INSERT INTO ReportPhotos (ReportID, filename)
                        VALUES (%s, %s)
                    """, (report_id, filename))

            conn.commit()
            flash("Report created successfully!", 'success')

    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Report creation failed: {err}", 'error')
    except Exception as e:
        conn.rollback()
        flash("An error occurred during file upload", 'error')
    finally:
        conn.close()

    return redirect('/event-reports')

@app.route('/view-reports')
def view_reports():
    if 'user_id' not in session:
        return redirect('/login')
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Get reports with event details
        cursor.execute("""
    SELECT 
        r.ReportID,
        r.Content,
        r.CreatedAt,
        e.EventName,
        e.Date AS EventDate,  # Fixed column alias
        GROUP_CONCAT(rp.filename) AS photos 
    FROM Reports r
    JOIN Events e ON r.EventID = e.EventID
    LEFT JOIN ReportPhotos rp ON r.ReportID = rp.ReportID
    WHERE e.Date < CURDATE()
    GROUP BY r.ReportID
    ORDER BY r.CreatedAt DESC
""")
        reports = cursor.fetchall()

        # Process photo filenames
        for report in reports:
            report['photos'] = report['photos'].split(',') if report['photos'] else []

        return render_template('view_report.html', reports=reports)

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", 'error')
        return redirect('/dashboard')
    except Exception as e:
        flash("Error loading reports", 'error')
        return redirect('/dashboard')
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

@app.route('/create-event', methods=['POST'])
def create_event():
    if session.get('role') != 'Organizer':
        return redirect('/')

    # Extract form data
    event_name = request.form.get('event_name')
    venue = request.form.get('venue')
    date_str = request.form.get('date')
    start_time_str = request.form.get('start_time')
    end_time_str = request.form.get('end_time')
    start_time = datetime.strptime(start_time_str, '%H:%M').time()
    end_time = datetime.strptime(end_time_str, '%H:%M').time()
    capacity = request.form.get('capacity')
    fee = request.form.get('fee')
    organizer_id = session['user_id']

    # Validate all fields
    if not all([event_name, venue, date_str, start_time_str, end_time_str, capacity, fee]):
        flash("All fields are required!", 'error')
        return redirect('/dashboard')

    try:
        # Convert date and time strings to datetime objects
        event_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        
        # Check if date is in the past
        if event_date < date.today():
            flash("Cannot create events for past dates!", 'error')
            return redirect('/dashboard')

        # Check time logic
        if start_time >= end_time:
            flash("Start Time must be before End Time!", 'error')
            return redirect('/dashboard')

        # Validate numerical values
        capacity = int(capacity)
        fee = float(fee)
        
        if capacity <= 0:
            flash("Capacity must be a positive number!", 'error')
            return redirect('/dashboard')
            
        if fee < 0:
            flash("Fee cannot be negative!", 'error')
            return redirect('/dashboard')

    except ValueError as e:
        flash(f"Invalid input: {str(e)}", 'error')
        return redirect('/dashboard')

    conn = get_db_connection()
    if not conn:
        return redirect('/dashboard')

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO Events (EventName, Venue, Date, StartTime, EndTime, Capacity, Fee, OrganizerID)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (event_name, venue, event_date, start_time, end_time, capacity, fee, organizer_id))
            conn.commit()
            flash("Event created successfully!", 'success')
    except mysql.connector.Error as err:
        flash(f"Event creation failed: {err}", 'error')
    finally:
        conn.close()

    return redirect('/dashboard')


@app.route('/register-event/<int:event_id>', methods=['GET', 'POST'])
def register_event(event_id):
    # Initialize registration_id to None to avoid potential unassigned variable warnings
    registration_id = None

    # Check if user is logged in and is an Attendee
    if 'user_id' not in session or session.get('role') != 'Attendee':
        flash("Please log in as an Attendee to register for events.", 'warning')
        return redirect('/')

    conn = get_db_connection()
    if not conn:
        # Flash message is already set in get_db_connection
        return redirect('/dashboard')

    try:
        with conn.cursor() as cursor:
            cursor.execute("START TRANSACTION")

            # Check if already has an active registration
            cursor.execute("""
                SELECT RegistrationID FROM Registrations
                WHERE UserID = %s AND EventID = %s AND Status = 'Active'
                FOR UPDATE
            """, (session['user_id'], event_id))
            if cursor.fetchone():
                flash("You're already registered for this event!", 'error')
                conn.rollback()
                return redirect('/dashboard')

            # Get event details (using correct column names based on your schema) with lock
            cursor.execute("""
                SELECT EventName, Date, StartTime, Fee, Capacity FROM Events
                WHERE EventID = %s AND Date >= CURDATE()
                FOR UPDATE
            """, (event_id,))
            event = cursor.fetchone()

            if not event:
                flash("Event not found or has already occurred!", 'error')
                conn.rollback()
                return redirect('/dashboard')

            # Adjust variables to match the order of columns selected
            event_name, event_date, start_time, fee, capacity = event[0], event[1], event[2], float(event[3]), int(event[4])

            if capacity <= 0:
                flash("Event is full!", 'error')
                conn.rollback()
                return redirect('/dashboard')

            # Check for existing cancelled registration
            cursor.execute("""
                SELECT RegistrationID FROM Registrations
                WHERE UserID = %s AND EventID = %s AND Status = 'Cancelled'
                FOR UPDATE
            """, (session['user_id'], event_id))
            existing_reg = cursor.fetchone()

            if existing_reg:
                # Reactivate cancelled registration
                registration_id = existing_reg[0] # registration_id is assigned here
                cursor.execute("""
                    UPDATE Registrations
                    SET Status = 'Active', CancellationReason = NULL
                    WHERE RegistrationID = %s
                """, (registration_id,))

                # Update payment if exists
                cursor.execute("""
                    UPDATE Payments
                    SET Status = 'Pending'
                    WHERE RegistrationID = %s AND Status = 'Cancelled'
                """, (registration_id,))
                app.logger.info(f"User {session['user_id']} reactivated registration {registration_id} for EventID {event_id}.")


            else:
                # Create new registration
                cursor.execute("""
                    INSERT INTO Registrations (UserID, EventID, Status)
                    VALUES (%s, %s, 'Active')
                """, (session['user_id'], event_id))
                registration_id = cursor.lastrowid # registration_id is assigned here
                app.logger.info(f"User {session['user_id']} created registration {registration_id} for EventID {event_id}.")

                # Create payment record
                cursor.execute("""
                    INSERT INTO Payments (RegistrationID, Amount, Status)
                    VALUES (%s, %s, 'Pending')
                """, (registration_id, fee))
                app.logger.info(f"Created payment record {cursor.lastrowid} for registration {registration_id} with amount {fee}.")


            # Update capacity
            cursor.execute("""
                UPDATE Events SET Capacity = Capacity - 1
                WHERE EventID = %s AND Capacity > 0
            """, (event_id,))

            if cursor.rowcount == 0:
                flash("Failed to update event capacity! Event might have just become full.", 'error')
                conn.rollback()
                return redirect('/dashboard')

            conn.commit()
            # Use the assigned registration_id in the log
            app.logger.info(f"Transaction committed for registration {registration_id}, capacity updated for EventID {event_id}.")

            # --- Retrieve User Email and Name for Sending Confirmation ---
            cursor.execute("SELECT Email, Name FROM Users WHERE UserID = %s", (session['user_id'],))
            user_info = cursor.fetchone()
            user_email, user_name = user_info[0], user_info[1]
            app.logger.info(f"Retrieved user email {user_email} for confirmation.")


            # --- Send Registration Confirmation Email (Asynchronously) ---
            try:
                msg_subject = f"Registration Confirmed for: {escape(event_name)}"
                msg_body = (
                    f"Hi {escape(user_name)},\n\n"
                    f"This email confirms your registration for the event:\n\n"
                    f"Event Name: {escape(event_name)}\n"
                    f"Date: {event_date}\n"
                    f"Start Time: {start_time.strftime('%H:%M') if isinstance(start_time, time) else start_time}\n\n" # Use start_time
                    # Include End Time if you like
                    # f"End Time: {end_time.strftime('%H:%M') if isinstance(end_time, time) else end_time}\n\n"
                    f"Registration ID: {registration_id}\n" # registration_id is definitely available here
                    f"Amount Due: {fee:.2f}\n\n"
                    f"Please proceed to the payments section to complete your registration.\n\n"
                    f"Best regards,\n"
                    f"The Event Portal Team"
                )

                msg = Message(
                    subject=msg_subject,
                    recipients=[user_email],
                    body=msg_body
                )

                # Pass the app context to the thread
                thread = Thread(target=send_async_email, args=[app.app_context(), msg])
                thread.start()
                # Use the assigned registration_id in the log
                app.logger.info(f"Initiated sending registration confirmation email for RegistrationID {registration_id} to {user_email}.")


            except Exception as e:
                # Log the error
                app.logger.error(f"Failed to *initiate* sending registration confirmation email for RegistrationID {registration_id} to {user_email}: {str(e)}")
                # Note: If the error occurred *before* registration_id was assigned, this log line might still error.
                # However, with registration_id = None initialized, it will be None in that case.


            flash("Registration successful! A confirmation email has been sent. Please proceed to payment.", 'success')
            return redirect('/payments')

    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Registration failed due to a database error. Please try again later. Details: {err}", 'error')
        app.logger.error(f"Registration database error for UserID {session.get('user_id')} EventID {event_id}: {err}", exc_info=True)
        # If a DB error happens here before registration_id is assigned, registration_id will be None
        # If the error happened AFTER registration_id was assigned, it will have the value.
    except Exception as e:
        conn.rollback()
        flash("An unexpected error occurred during registration. Please try again later.", 'error')
        app.logger.error(f"Unexpected registration error for UserID {session.get('user_id')} EventID {event_id}: {e}", exc_info=True)
         # If an unexpected error happens here before registration_id is assigned, registration_id will be None
         # If the error happened AFTER registration_id was assigned, it will have the value.
    finally:
        if conn and conn.is_connected():
            conn.close()

    return redirect('/dashboard')

@app.route('/payments')
def payments():
    if 'user_id' not in session or session.get('role') != 'Attendee':
        return redirect('/')

    conn = get_db_connection()
    if not conn:
        return redirect('/dashboard')

    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute("""
                SELECT P.PaymentID, E.EventID, E.EventName, P.Amount, P.Status
                FROM Payments P
                JOIN Registrations R ON P.RegistrationID = R.RegistrationID
                JOIN Events E ON R.EventID = E.EventID
                WHERE R.UserID = %s AND P.Status = 'Pending' AND R.Status = 'Active'
            """, (session['user_id'],))
            pending_payments = cursor.fetchall()

        return render_template('payments.html', pending_payments=pending_payments)
    except mysql.connector.Error as err:
        flash(f"Database error: {err}", 'error')
        return redirect('/dashboard')
    finally:
        conn.close()

@app.route('/complete-payment/<int:payment_id>')
def complete_payment(payment_id):
    if 'user_id' not in session or session.get('role') != 'Attendee':
        return redirect('/')

    conn = get_db_connection()
    if not conn:
        return redirect('/payments')

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE Payments P
                JOIN Registrations R ON P.RegistrationID = R.RegistrationID
                SET P.Status = 'Completed'
                WHERE P.PaymentID = %s AND R.UserID = %s AND P.Status = 'Pending' AND R.Status = 'Active'
            """, (payment_id, session['user_id']))

            if cursor.rowcount == 0:
                flash("Payment not found or already completed", 'error')
            else:
                conn.commit()
                flash("Payment completed successfully!", 'success')

    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Payment failed: {err}", 'error')
    finally:
        conn.close()

    return redirect('/payments')



@app.route('/my-registrations')
def my_registrations():
    if 'user_id' not in session or session.get('role') != 'Attendee':
        return redirect('/')

    conn = get_db_connection()
    if not conn:
        return redirect('/')

    try:
        with conn.cursor(dictionary=True) as cursor:
            # Fixed SQL query with proper parentheses
            cursor.execute("""
    SELECT R.RegistrationID, 
           E.EventID, 
           E.EventName, 
           E.Date AS EventDate,
           TIME_FORMAT(E.StartTime, '%h:%i %p') AS StartTime,
           TIME_FORMAT(E.EndTime, '%h:%i %p') AS EndTime,
           E.Venue,
           COALESCE(P.Amount, 0) AS Amount,
           COALESCE(P.Status, 'Pending') AS payment_status,
           R.Status AS registration_status,
           P.PaymentID,
           R.CancellationReason,
           EXISTS (
               SELECT 1 
               FROM Feedback F 
               WHERE F.EventID = E.EventID 
               AND F.UserID = R.UserID
           ) AS has_given_feedback,
           (NOW() >= TIMESTAMP(E.Date, E.EndTime) 
           AND 
           NOW() <= TIMESTAMP(E.Date, E.EndTime) + INTERVAL 48 HOUR
           ) AS allow_feedback
    FROM Registrations R
    JOIN Events E ON R.EventID = E.EventID
    LEFT JOIN Payments P ON R.RegistrationID = P.RegistrationID
    WHERE R.UserID = %s
    ORDER BY E.Date DESC
""", (session['user_id'],))
            
            registrations = cursor.fetchall()
            current_date = date.today()

            return render_template(
                'my_registrations.html',
                registrations=registrations,
                current_date=current_date
            )

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", 'error')
        return redirect('/dashboard')
    finally:
        if conn.is_connected():
            conn.close()


from datetime import date

from datetime import date

@app.route('/cancel-registration/<int:registration_id>', methods=['POST'])
def cancel_registration(registration_id):
    if 'user_id' not in session or session.get('role') != 'Attendee':
        return redirect('/')

    cancellation_reason = request.form.get('cancellation_reason', '').strip()
    if not cancellation_reason:
        flash("Please provide a cancellation reason", 'error')
        return redirect('/my-registrations')

    conn = get_db_connection()
    if not conn:
        return redirect('/my-registrations')

    try:
        with conn.cursor() as cursor:
            cursor.execute("START TRANSACTION")

            # Get event details (EventName, StartTime), event Date, and user email
            cursor.execute("""
                SELECT R.EventID, E.EventName, E.Date, E.StartTime, U.Email, U.Name
                FROM Registrations R
                JOIN Events E ON R.EventID = E.EventID
                JOIN Users U ON R.UserID = U.UserID  -- Corrected join condition
                WHERE R.RegistrationID = %s
                AND R.UserID = %s
                AND R.Status = 'Active'
                FOR UPDATE
            """, (registration_id, session['user_id']))
            result = cursor.fetchone()

            if not result:
                flash("Registration not found or already cancelled", 'error')
                conn.rollback()
                return redirect('/my-registrations')

            event_id, event_name, event_date, start_time, user_email, user_name = result

            # Prevent cancellation for past events
            if event_date < date.today():
                flash("Cannot cancel registration for completed events", 'error')
                conn.rollback()
                return redirect('/my-registrations')

            # Update registration status with cancellation reason
            cursor.execute("""
                UPDATE Registrations
                SET Status = 'Cancelled',
                    CancellationReason = %s
                WHERE RegistrationID = %s
            """, (cancellation_reason, registration_id))

            # Increase event capacity
            cursor.execute("""
                UPDATE Events
                SET Capacity = Capacity + 1
                WHERE EventID = %s
            """, (event_id,))

            # Update payment status if exists and is pending
            cursor.execute("""
                UPDATE Payments
                SET Status = 'Cancelled'
                WHERE RegistrationID = %s
                AND Status = 'Pending'
            """, (registration_id,))

            conn.commit()
            app.logger.info(f"Registration {registration_id} cancelled successfully.")

            # --- Send Cancellation Confirmation Email (Asynchronously) ---
            try:
                msg_subject = f"Cancellation Confirmation for: {escape(event_name)}"
                msg_body = (
                    f"Hi {escape(user_name)},\n\n"
                    f"This email confirms that your registration for the event:\n\n"
                    f"Event Name: {escape(event_name)}\n"
                    f"scheduled for {event_date} at {start_time.strftime('%H:%M') if isinstance(start_time, time) else start_time}\n"
                    f"has been successfully cancelled.\n\n"
                    f"We're sorry you won't be able to attend.\n\n"
                    f"Reason for cancellation: {escape(cancellation_reason)}\n\n"
                    f"If you have any questions, please contact us.\n\n"
                    f"Best regards,\n"
                    f"The Event Portal Team"
                )

                msg = Message(
                    subject=msg_subject,
                    recipients=[user_email],
                    body=msg_body
                )

                # Pass the app context to the thread
                thread = Thread(target=send_async_email, args=[app.app_context(), msg])
                thread.start()
                app.logger.info(f"Initiated sending cancellation confirmation email to {user_email} for registration {registration_id}.")

            except Exception as e:
                app.logger.error(f"Failed to initiate sending cancellation email to {user_email} for registration {registration_id}: {str(e)}")

            flash("Registration cancelled successfully. A confirmation email has been sent.", 'success')

    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Cancellation failed: {err}", 'error')
        app.logger.error(f"Cancellation database error for registration {registration_id}: {err}", exc_info=True)
    except Exception as e:
        conn.rollback()
        flash(f"An unexpected error occurred during cancellation.",'error')
        app.logger.error(f"Unexpected error during cancellation of registration {registration_id}: {e}", exc_info=True)

    finally:
        if conn and conn.is_connected():
            conn.close()

    return redirect('/my-registrations')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')



@app.route('/submit-feedback/<int:event_id>', methods=['GET', 'POST'])
def submit_feedback(event_id):
    if 'user_id' not in session or session.get('role') != 'Attendee':
        flash("Please log in as an Attendee to submit feedback.", 'warning')
        return redirect('/')

    conn = get_db_connection()
    if not conn:
        return redirect('/my-registrations')

    try:
        with conn.cursor(dictionary=True) as cursor:
            # Get event details with time validation and user info
            # Added U.Email, U.Name to the select list
            cursor.execute("""
                SELECT E.EventName, E.Date AS event_date, E.EndTime,
                        TIMESTAMP(E.Date, E.EndTime) AS event_end,
                        TIMESTAMP(E.Date, E.EndTime) + INTERVAL 48 HOUR AS feedback_deadline,
                        U.Email, U.Name # Fetch user email and name here
                FROM Events E
                JOIN Registrations R ON E.EventID = R.EventID
                JOIN Users U ON R.UserID = U.UserID # Join to get user details
                WHERE R.UserID = %s
                AND E.EventID = %s
                AND R.Status = 'Active'
            """, (session['user_id'], event_id))
            event_user_data = cursor.fetchone()

            if not event_user_data:
                flash("Invalid event or registration for feedback submission.", 'error')
                return redirect('/my-registrations')

            # Extract data including user info
            event_name = event_user_data['EventName']
            user_email = event_user_data['Email']
            user_name = event_user_data['Name']

            # Convert database times to Python datetime objects
            try:
                event_end = event_user_data['event_end']
                feedback_deadline = event_user_data['feedback_deadline']
            except KeyError:
                flash("Event time data is invalid.", 'error')
                return redirect('/my-registrations')

            current_time = datetime.now()

            # Check if event hasn't ended yet
            if current_time < event_end:
                flash("This event has not yet completed. Feedback cannot be submitted yet.", 'warning')
                return redirect('/my-registrations')

            # Check if feedback window has expired
            if current_time > feedback_deadline:
                flash("Feedback submission is only allowed within 48 hours after event completion.", 'error')
                return redirect('/my-registrations')

            # Handle form submission (POST request)
            if request.method == 'POST':
                rating = request.form.get('rating')
                comment = request.form.get('comment', '').strip()

                if not rating or not rating.isdigit() or int(rating) not in range(1, 6):
                    flash("Please provide a valid rating (1-5).", 'error')
                    return redirect(f'/submit-feedback/{event_id}')

                try:
                    # We use a new cursor for the INSERT/UPDATE to avoid potential issues
                    # with the dictionary=True cursor if needed, though it should be fine.
                    # Explicitly creating a new one is safer if different cursor types/settings are used.
                    with conn.cursor() as insert_cursor:
                        insert_cursor.execute("""
                            INSERT INTO Feedback (UserID, EventID, Rating, Comment)
                            VALUES (%s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                            Rating = VALUES(Rating), Comment = VALUES(Comment)
                        """, (session['user_id'], event_id, rating, comment))
                        conn.commit()
                        app.logger.info(f"Feedback submitted/updated by UserID {session['user_id']} for EventID {event_id}.")


                    # --- Send Feedback Confirmation Email (Asynchronously) ---
                    try:
                        msg_subject = f"Feedback Received for: {escape(event_name)}"
                        msg_body = (
                            f"Hi {escape(user_name)},\n\n"
                            f"Thank you for providing feedback for the event:\n\n"
                            f"Event Name: {escape(event_name)}\n"
                            f"Your Rating: {rating}/5\n"
                            f"Your Comment: {escape(comment) if comment else 'No comment provided'}\n\n"
                            f"Your feedback is valuable to us!\n\n"
                            f"Best regards,\n"
                            f"The Event Portal Team"
                        )

                        msg = Message(
                            subject=msg_subject,
                            recipients=[user_email],
                            body=msg_body
                        )

                        # Pass the app context to the thread
                        thread = Thread(target=send_async_email, args=[app.app_context(), msg])
                        thread.start()
                        app.logger.info(f"Initiated sending feedback confirmation email to {user_email} for EventID {event_id}.")

                    except Exception as e:
                        app.logger.error(f"Failed to initiate sending feedback confirmation email to {user_email} for EventID {event_id}: {str(e)}")
                        # Log the error, but don't interrupt the user flow


                    flash("Feedback submitted successfully! A confirmation email has been sent.", 'success')
                    return redirect('/my-registrations')

                except mysql.connector.Error as err:
                    conn.rollback() # Rollback the potential INSERT/UPDATE if it failed
                    flash(f"Failed to save feedback: {err}", 'error')
                    app.logger.error(f"Database error saving feedback for UserID {session['user_id']} EventID {event_id}: {err}", exc_info=True)
                    return redirect(f'/submit-feedback/{event_id}')
                except Exception as e:
                    conn.rollback() # Rollback on unexpected errors
                    flash(f"An unexpected error occurred while saving feedback.", 'error')
                    app.logger.error(f"Unexpected error saving feedback for UserID {session['user_id']} EventID {event_id}: {e}", exc_info=True)
                    return redirect(f'/submit-feedback/{event_id}')


            # GET request - show form
            # This part remains largely the same, but uses event_user_data for event info
            # Need to re-fetch existing feedback as the first query only got event/user data
            cursor.execute("""
                SELECT Rating, Comment FROM Feedback
                WHERE UserID = %s AND EventID = %s
            """, (session['user_id'], event_id))
            existing_feedback = cursor.fetchone() # Use fetchone as it's dictionary=True cursor


            # Pass correct variables to template
            return render_template(
                'feedback_form.html',
                event_name=event_name, # Pass event name explicitly
                event_id=event_id, # Pass event_id for form action
                existing_feedback=existing_feedback,
                deadline=feedback_deadline.strftime('%Y-%m-%d %H:%M:%S')
            )

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", 'error')
        app.logger.error(f"Database error in submit_feedback route for UserID {session.get('user_id')} EventID {event_id}: {err}", exc_info=True)
        return redirect('/my-registrations')
    except Exception as e:
        flash(f"Unexpected error: {str(e)}", 'error')
        app.logger.error(f"Unexpected error in submit_feedback route for UserID {session.get('user_id')} EventID {event_id}: {e}", exc_info=True)
        return redirect('/my-registrations')

    finally:
        if conn and conn.is_connected():
            conn.close()

@app.route('/event-feedback/<int:event_id>')
def view_feedback(event_id):
    conn = get_db_connection()
    if not conn:
        return redirect('/dashboard')

    try:
        with conn.cursor(dictionary=True) as cursor:
            # Verify organizer owns the event
            if session.get('role') == 'Organizer':
                cursor.execute("""
                    SELECT 1 FROM Events 
                    WHERE EventID = %s AND OrganizerID = %s
                """, (event_id, session['user_id']))
                if not cursor.fetchone():
                    flash("You can only view feedback for your own events", 'error')
                    return redirect('/dashboard')

            # Get event details
            cursor.execute("SELECT EventName FROM Events WHERE EventID = %s", (event_id,))
            event = cursor.fetchone()

            # Get feedback
            cursor.execute("""
                SELECT U.Name, F.Rating, F.Comment, F.FeedbackDate
                FROM Feedback F
                JOIN Users U ON F.UserID = U.UserID
                WHERE F.EventID = %s
                ORDER BY F.FeedbackDate DESC
            """, (event_id,))
            feedbacks = cursor.fetchall()

        return render_template('event_feedback.html', 
                             event=event, 
                             feedbacks=feedbacks)

    except mysql.connector.Error as err:
        flash(f"Error retrieving feedback: {err}", 'error')
        return redirect('/dashboard')
    finally:
        conn.close()

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)