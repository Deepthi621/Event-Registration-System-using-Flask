from flask import Flask, render_template, request, redirect, session, flash, url_for # Added url_for just in case
import mysql.connector
from config import DB_CONFIG
from datetime import datetime, date, time
import os
import re
from threading import Thread # Import Thread
from flask_mail import Mail, Message ,Attachment
# import smtplib # Not strictly needed if using Flask-Mail
from markupsafe import escape
import logging
from logging.handlers import RotatingFileHandler
import mimetypes

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

LOGO_FILENAME='event_logo.avif'
LOGO_PATH = os.path.join(app.root_path, 'static', LOGO_FILENAME)

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
                           U.ProfilePhotoFilename,
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
        flash("Please log in as an Attendee to complete payments.", 'warning')
        return redirect('/')

    conn = get_db_connection()
    if not conn:
        return redirect('/payments')

    # Variables to hold data for email, initialized to None
    user_email = None
    user_name = None
    event_name = None
    paid_amount = None
    payment_success = False # Flag to indicate if payment update succeeded

    try:
        with conn.cursor(dictionary=True) as cursor: # Use dictionary=True for easier access
            # First, retrieve necessary details for the email *and* for the update check
            cursor.execute("""
                SELECT
                    P.PaymentID,
                    P.Amount,
                    P.Status AS PaymentStatus,
                    E.EventName,
                    U.Email,
                    U.Name,
                    R.Status AS RegistrationStatus
                FROM Payments P
                JOIN Registrations R ON P.RegistrationID = R.RegistrationID
                JOIN Events E ON R.EventID = E.EventID
                JOIN Users U ON R.UserID = U.UserID -- Join to get user details
                WHERE P.PaymentID = %s AND R.UserID = %s
                FOR UPDATE -- Lock these rows as we might update the payment
            """, (payment_id, session['user_id']))
            payment_details = cursor.fetchone()

            if not payment_details:
                flash("Payment record not found.", 'error')
                conn.rollback() # Rollback the FOR UPDATE lock
                return redirect('/payments')

            # Check if payment is already completed or registration is not active
            if payment_details['PaymentStatus'] != 'Pending' or payment_details['RegistrationStatus'] != 'Active':
                 flash("Payment is not pending or registration is not active.", 'warning')
                 conn.rollback() # Rollback the FOR UPDATE lock
                 return redirect('/payments')

            # Extract details for email
            user_email = payment_details['Email']
            user_name = payment_details['Name']
            event_name = payment_details['EventName']
            paid_amount = payment_details['Amount'] # Amount from the payment record


            # Now perform the update
            cursor.execute("""
                UPDATE Payments
                SET Status = 'Completed'
                WHERE PaymentID = %s
            """, (payment_id,))

            # Check if the update affected exactly one row
            if cursor.rowcount == 1:
                 conn.commit()
                 payment_success = True # Set flag to indicate success
                 app.logger.info(f"Payment {payment_id} completed successfully by UserID {session['user_id']}.")
                 flash("Payment completed successfully!", 'success')
            else:
                 # This case should theoretically not be hit if the SELECT FOR UPDATE worked correctly
                 # but it's a safeguard.
                 conn.rollback()
                 app.logger.warning(f"Payment {payment_id} update failed or affected multiple/zero rows for UserID {session['user_id']}. Rolled back.")
                 flash("Payment update failed. Please try again.", 'error')


    except mysql.connector.Error as err:
        conn.rollback() # Ensure rollback on DB errors
        flash(f"Payment failed due to a database error: {err}", 'error')
        app.logger.error(f"Payment database error for PaymentID {payment_id}, UserID {session.get('user_id')}: {err}", exc_info=True)
    except Exception as e:
        conn.rollback() # Ensure rollback on unexpected errors
        flash(f"An unexpected error occurred during payment.", 'error')
        app.logger.error(f"Unexpected error during payment completion for PaymentID {payment_id}, UserID {session.get('user_id')}: {e}", exc_info=True)

    finally:
        if conn and conn.is_connected():
            conn.close()

    # --- Send Payment Confirmation Email (Asynchronously) ---
    # Only send if the database update was successful and we have user/event details
    if payment_success and user_email and user_name and event_name and paid_amount is not None:
        try:
            msg_subject = f"Payment Confirmed for: {escape(event_name)}"
            msg_body = (
                f"Hi {escape(user_name)},\n\n"
                f"This email confirms your payment for the event registration:\n\n"
                f"Event Name: {escape(event_name)}\n"
                f"Amount Paid: {paid_amount:.2f}\n" # Format amount to 2 decimal places
                f"Payment ID: {payment_id}\n\n"
                f"Your registration is now fully confirmed.\n\n"
                f"Thank you for your payment!\n\n"
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
            app.logger.info(f"Initiated sending payment confirmation email to {user_email} for PaymentID {payment_id}.")

        except Exception as e:
            # Log the email sending error
            app.logger.error(f"Failed to initiate sending payment confirmation email to {user_email} for PaymentID {payment_id}: {str(e)}")
            # Note: We don't flash an error here because the payment itself was successful.
            # The log is sufficient for this background task failure.

    # Always redirect to the payments page after the attempt
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
    """Handles submitting feedback for an event."""
    # Check if user is logged in and is an Attendee
    if 'user_id' not in session or session.get('role') != 'Attendee':
        flash("Please log in as an Attendee to submit feedback.", 'warning')
        return redirect(url_for('home')) # Redirect to home or login page

    conn = get_db_connection()
    if not conn:
        # get_db_connection already flashes an error
        return redirect(url_for('my_registrations')) # Redirect to a page listing registrations

    try:
        # Use cursor(dictionary=True) for easier access to column names
        with conn.cursor(dictionary=True) as cursor:
            # Get event details with time validation and user info (for email)
            cursor.execute("""
                SELECT E.EventName, E.Date AS event_date, E.EndTime,
                       TIMESTAMP(E.Date, E.EndTime) AS event_end,
                       TIMESTAMP(E.Date, E.EndTime) + INTERVAL 48 HOUR AS feedback_deadline,
                       U.Email, U.Name  -- Fetch user email and name for the email
                FROM Events E
                JOIN Registrations R ON E.EventID = R.EventID
                JOIN Users U ON R.UserID = U.UserID  -- Join to get user details
                WHERE R.UserID = %s
                AND E.EventID = %s
                AND R.Status = 'Active' -- Ensure the user is registered and active for this event
            """, (session['user_id'], event_id))
            event_user_data = cursor.fetchone()

            # If no matching active registration found, the user cannot give feedback
            if not event_user_data:
                flash("Invalid event or registration for feedback submission.", 'error')
                app.logger.warning(f"User {session['user_id']} attempted feedback for invalid/inactive event registration {event_id}")
                return redirect(url_for('my_registrations'))

            # Extract necessary data including user info
            event_name = event_user_data['EventName']
            user_email = event_user_data['Email']
            user_name = event_user_data['Name']

            # Convert database timestamps to Python datetime objects
            # Use .get() with None as default just in case, though TIMESTAMP should return values
            event_end = event_user_data.get('event_end')
            feedback_deadline = event_user_data.get('feedback_deadline')

            # Check for potential issues with timestamp calculations
            if event_end is None or feedback_deadline is None:
                 flash("Could not determine event completion time or feedback deadline.", 'error')
                 app.logger.error(f"TIMESTAMP calculation returned NULL for EventID {event_id}. Check database data/functions.")
                 return redirect(url_for('my_registrations'))


            current_time = datetime.now()

            # Check if event hasn't ended yet
            if current_time < event_end:
                flash("This event has not yet completed. Feedback cannot be submitted yet.", 'warning')
                return redirect(url_for('my_registrations'))

            # Check if feedback window has expired
            if current_time > feedback_deadline:
                flash("Feedback submission is only allowed within 48 hours after event completion.", 'error')
                return redirect(url_for('my_registrations'))

            # --- Handle form submission (POST request) ---
            if request.method == 'POST':
                rating = request.form.get('rating')
                comment = request.form.get('comment', '').strip()

                # Basic validation for rating
                if not rating or not rating.isdigit() or int(rating) not in range(1, 6):
                    flash("Please provide a valid rating (1-5).", 'error')
                    return redirect(url_for('submit_feedback', event_id=event_id))

                # Convert rating to integer
                rating = int(rating)

                try:
                    # Use a new cursor for the INSERT/UPDATE operation for safety/clarity
                    # Using default cursor (dictionary=False) here
                    with conn.cursor() as insert_cursor:
                         # Use ON DUPLICATE KEY UPDATE as defined in your schema for Feedback
                         # Assumes a UNIQUE constraint on (UserID, EventID) in the Feedback table
                        insert_cursor.execute("""
                            INSERT INTO Feedback (UserID, EventID, Rating, Comment)
                            VALUES (%s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                            Rating = VALUES(Rating), Comment = VALUES(Comment),
                            FeedbackDate = CURRENT_TIMESTAMP() -- Optional: update timestamp on change
                        """, (session['user_id'], event_id, rating, comment))
                        conn.commit()
                        app.logger.info(f"Feedback submitted/updated by UserID {session['user_id']} for EventID {event_id}. Rating: {rating}")


                    # --- Send Simplified Feedback Confirmation Email (Asynchronously) ---
                    # This email just confirms receipt of feedback, without details or logo
                    try:
                        # Use user_email and user_name fetched earlier
                        msg_subject = f"Thank You For Your Feedback - {escape(event_name)}"

                        # --- Create Simplified HTML and Plain Text Email Bodies ---
                        msg_html = f"""
                        <html>
                        <head></head>
                        <body>
                            <p>Hi {escape(user_name)},</p>
                            <p>Thank you for submitting your valuable feedback for the event: <strong>{escape(event_name)}</strong>.</p>
                            <p>Your input helps us improve future events.</p>
                            <p>Best regards,<br>The Event Portal Team</p>
                        </body>
                        </html>
                        """

                        msg_body = (
                            f"Hi {escape(user_name)},\n\n"
                            f"Thank you for submitting your valuable feedback for the event: {escape(event_name)}.\n\n"
                            f"Your input helps us improve future events.\n\n"
                            f"Best regards,\n"
                            f"The Event Portal Team"
                        )

                        # Create the Message object
                        msg = Message(
                            subject=msg_subject,
                            recipients=[user_email], # Send to the user's email
                            body=msg_body, # Set the plain text body
                            html=msg_html  # Set the HTML body
                        )

                        # --- NO LOGO ATTACHMENT IN THIS EMAIL as requested ---
                        # The code to attach the logo is intentionally omitted here.

                        # Pass the created Message object to the async sender
                        thread = Thread(target=send_async_email, args=[app.app_context(), msg])
                        thread.start()
                        app.logger.info(f"Initiated sending simplified feedback confirmation email to {user_email} for EventID {event_id}.")

                    except Exception as e:
                        # Log the error initiating the email sending process
                        app.logger.error(f"Failed to initiate sending simplified feedback confirmation email to {user_email} for EventID {event_id}: {str(e)}", exc_info=True)
                        # No flash message needed here, as feedback was saved successfully.


                    flash("Feedback submitted successfully! A confirmation email has been sent.", 'success')
                    return redirect(url_for('my_registrations')) # Redirect after successful POST

                except mysql.connector.IntegrityError as err:
                     # This might catch duplicate feedback if ON DUPLICATE KEY UPDATE didn't work as expected,
                     # or other integrity errors.
                     conn.rollback()
                     flash(f"Failed to save feedback due to an integrity error (e.g., duplicate): {err}", 'error')
                     app.logger.error(f"Database integrity error saving feedback for UserID {session['user_id']} EventID {event_id}: {err}", exc_info=True)
                     return redirect(url_for('submit_feedback', event_id=event_id)) # Use url_for
                except mysql.connector.Error as err:
                    conn.rollback() # Rollback the potential INSERT/UPDATE if it failed
                    flash(f"Failed to save feedback due to a database error: {err}", 'error')
                    app.logger.error(f"Database error saving feedback for UserID {session['user_id']} EventID {event_id}: {err}", exc_info=True)
                    return redirect(url_for('submit_feedback', event_id=event_id)) # Use url_for
                except Exception as e:
                    conn.rollback() # Ensure rollback on unexpected errors during save/email init
                    flash(f"An unexpected error occurred while saving feedback.", 'error')
                    app.logger.error(f"Unexpected error saving feedback for UserID {session['user_id']} EventID {event_id}: {e}", exc_info=True)
                    return redirect(url_for('submit_feedback', event_id=event_id)) # Use url_for


            # --- Handle GET request - show form ---
            # This block executes if the request method is GET.
            # The initial query using cursor(dictionary=True) has already fetched event_user_data
            # and validated the user/event/time window.

            # Fetch existing feedback specifically for displaying the form fields if user is updating
            # Reuse the same dictionary=True cursor within the `with` block
            cursor.execute("""
                SELECT Rating, Comment FROM Feedback
                WHERE UserID = %s AND EventID = %s
            """, (session['user_id'], event_id))
            existing_feedback = cursor.fetchone() # Use fetchone as cursor is dictionary=True

            # Pass data to the template for rendering the form
            # Pass the original fetched data dictionary 'event_user_data' as 'event' to the template
            # This resolves the 'event' is undefined error in the template
            return render_template(
                'feedback_form.html',
                event=event_user_data, # <-- Pass the dictionary here as 'event'
                # You can still pass specific values too if your template uses them directly
                event_name=event_name, # Convenient for template access
                event_id=event_id,     # Convenient for template action URLs
                existing_feedback=existing_feedback, # Pass existing feedback data
                # Pass the deadline as a formatted string for display in the template
                deadline=feedback_deadline.strftime('%Y-%m-%d %H:%M:%S')
            )

    except mysql.connector.Error as err:
        # Handle database errors from the initial SELECT query or other DB ops before POST block
        flash(f"Database error accessing event details: {err}", 'error')
        app.logger.error(f"Database error in submit_feedback route (initial fetch/validation) for UserID {session.get('user_id')} EventID {event_id}: {err}", exc_info=True)
        return redirect(url_for('my_registrations'))
    except Exception as e:
        # Handle any other unexpected errors from the initial part of the route before POST block
        flash(f"An unexpected error occurred retrieving event details: {str(e)}", 'error')
        app.logger.error(f"Unexpected error in submit_feedback route (initial fetch/validation) for UserID {session.get('user_id')} EventID {event_id}: {e}", exc_info=True)
        return redirect(url_for('my_registrations'))

    finally:
        # Ensure the database connection is closed in all cases
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

STATIC_PROFILE_PHOTOS_FOLDER = 'static/profile_photos'
PROFILE_PHOTOS_FOLDER = os.path.join(app.root_path, STATIC_PROFILE_PHOTOS_FOLDER)

os.makedirs(PROFILE_PHOTOS_FOLDER, exist_ok=True)
app.logger.info(f"Profile photos upload path set to: {PROFILE_PHOTOS_FOLDER}")

ALLOWED_PROFILE_PHOTO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.logger.info(f"Allowed profile photo extensions: {ALLOWED_PROFILE_PHOTO_EXTENSIONS}")

def allowed_profile_photo(filename):
    """Checks if a profile photo filename has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_PROFILE_PHOTO_EXTENSIONS

# --- Route to Display User Profile ---
@app.route('/profile')
def profile():
    """Displays the logged-in user's profile."""
    # Ensure user is logged in
    if 'user_id' not in session:
        flash("Please log in to view your profile.", "warning")
        return redirect(url_for('login')) # Redirect to your login route

    conn = get_db_connection()
    if not conn:
        return redirect(url_for('dashboard')) # Redirect somewhere appropriate if DB fails

    user = None
    try:
        with conn.cursor(dictionary=True) as cursor:
            # Fetch user details, including the profile photo filename
            cursor.execute("SELECT UserID, Name, Email, Role, ProfilePhotoFilename FROM Users WHERE UserID = %s", (session['user_id'],))
            user = cursor.fetchone()

        if user:
            # Render the profile template, passing the user data
            return render_template('profile.html', user=user)
        else:
            # This case should theoretically not happen if session['user_id'] is valid
            flash("User not found.", "error")
            return redirect(url_for('dashboard')) # Or logout

    except mysql.connector.Error as err:
        flash(f"Database error fetching profile: {err}", 'error')
        app.logger.error(f"Database error fetching profile for UserID {session['user_id']}: {err}", exc_info=True)
        return redirect(url_for('dashboard'))
    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", 'error')
        app.logger.error(f"Unexpected error fetching profile for UserID {session['user_id']}: {e}", exc_info=True)
        return redirect(url_for('dashboard'))
    finally:
        if conn and conn.is_connected():
            conn.close()

# --- Route to Edit User Profile (GET and POST) ---
@app.route('/edit-profile', methods=['GET', 'POST'])
def edit_profile():
    """Displays form to edit profile and handles profile photo upload."""
    # Ensure user is logged in
    if 'user_id' not in session:
        flash("Please log in to edit your profile.", "warning")
        return redirect(url_for('login'))

    conn = get_db_connection()
    if not conn:
        return redirect(url_for('profile')) # Redirect back to profile if DB fails

    user = None
    try:
        with conn.cursor(dictionary=True) as cursor:
            # Fetch user details
            cursor.execute("SELECT UserID, Name, Email, Role, ProfilePhotoFilename FROM Users WHERE UserID = %s", (session['user_id'],))
            user = cursor.fetchone()

        if not user:
            # Should not happen if session is valid, but good check
            flash("User not found.", "error")
            return redirect(url_for('profile'))

        if request.method == 'POST':
            # --- Handle Profile Photo Upload ---
            # Check if the post request has the file part
            if 'profile_photo' not in request.files:
                flash('No file part in the request.', 'warning')
                # Continue processing other form data if any, or return to form
                # For now, let's assume photo is optional and proceed
                pass # No photo uploaded, just skip photo processing

            else:
                file = request.files['profile_photo']

                # If user does not select a file, browser submits an empty file without a filename
                if file.filename == '':
                    # User didn't select a new file, might be saving other profile details
                    # flash('No selected file.', 'warning') # Or maybe just informational
                    pass # No new photo uploaded

                # Process the uploaded file
                elif file and allowed_profile_photo(file.filename):
                    try:
                        # Generate a secure filename to prevent directory traversal attacks
                        filename = secure_filename(file.filename)
                        # Create a unique filename to avoid overwriting existing files
                        # Could add a timestamp or UUID: filename = f"{uuid.uuid4()}_{filename}"
                        # For simplicity, let's use UserID to name the photo file
                        # You might want to handle different extensions if needed
                        file_extension = filename.rsplit('.', 1)[1].lower()
                        photo_filename_in_db = f"{session['user_id']}.{file_extension}"
                        file_path = os.path.join(PROFILE_PHOTOS_FOLDER, photo_filename_in_db)

                        # Save the file
                        file.save(file_path)
                        app.logger.info(f"Saved profile photo for UserID {session['user_id']} as {photo_filename_in_db}")

                        # Update the database with the new filename
                        with conn.cursor() as cursor:
                            cursor.execute("UPDATE Users SET ProfilePhotoFilename = %s WHERE UserID = %s", (photo_filename_in_db, session['user_id']))
                            conn.commit()
                        flash("Profile photo updated successfully!", "success")

                    except Exception as file_upload_error:
                         conn.rollback() # Rollback potential DB changes if update failed after save
                         flash(f"Error uploading profile photo: {str(file_upload_error)}", "error")
                         app.logger.error(f"Error uploading profile photo for UserID {session['user_id']}: {file_upload_error}", exc_info=True)


                else:
                    # File is not allowed
                    flash('Allowed photo types are: png, jpg, jpeg, gif.', 'error')
                    # Return to the form so user can try again
                    return redirect(url_for('edit_profile')) # Stay on the edit page

            # --- Handle Other Profile Fields (if your form allows editing Name, etc.) ---
            # Example:
            # new_name = request.form.get('name')
            # if new_name and new_name != user['Name']:
            #     try:
            #         with conn.cursor() as cursor:
            #              cursor.execute("UPDATE Users SET Name = %s WHERE UserID = %s", (new_name, session['user_id']))
            #              conn.commit()
            #         flash("Name updated successfully!", "success")
            #     except mysql.connector.Error as err:
            #          conn.rollback()
            #          flash(f"Error updating name: {err}", "error")
            #          app.logger.error(f"DB error updating name for UserID {session['user_id']}: {err}")
            #     except Exception as e:
            #          conn.rollback()
            #          flash(f"Unexpected error updating name: {str(e)}", "error")
            #          app.logger.error(f"Unexpected error updating name for UserID {session['user_id']}: {e}")


            # After processing POST, redirect back to the profile page to see changes
            return redirect(url_for('profile'))

        # --- Handle GET Request ---
        # Render the edit profile form, passing user data to pre-fill
        return render_template('edit_profile.html', user=user)

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", 'error')
        app.logger.error(f"Database error in edit_profile route for UserID {session.get('user_id')}: {err}", exc_info=True)
        return redirect(url_for('profile'))
    except Exception as e:
        flash(f"An unexpected error occurred: {str(e)}", 'error')
        app.logger.error(f"Unexpected error in edit_profile route for UserID {session.get('user_id')}: {e}", exc_info=True)
        return redirect(url_for('profile'))
    finally:
        # Ensure the connection is closed
        if conn and conn.is_connected():
            conn.close()

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)