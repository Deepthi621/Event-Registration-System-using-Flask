from flask import Flask, render_template, request, redirect, session, flash
import mysql.connector
from config import DB_CONFIG
from datetime import datetime, date,time
import os

app = Flask(__name__)
app.secret_key = 'your_secure_secret_key'
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as err:
        flash(f"Database connection error: {err}", 'error')
        return None

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ----------------------
# Routes
# ----------------------

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register_user():
    name = request.form.get('name')
    email = request.form.get('email')
    password = request.form.get('password')
    role = request.form.get('role')

    if not all([name, email, password, role]):
        flash("All fields are required!", 'error')
        return redirect('/')

    conn = get_db_connection()
    if not conn:
        return redirect('/')

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO Users (Name, Email, Password, Role) VALUES (%s, %s, %s, %s)",
                (name, email, password, role)
            )
            conn.commit()
            flash("Registration successful! Please login.", 'success')
    except mysql.connector.IntegrityError:
        flash("Email already exists!", 'error')
    except mysql.connector.Error as err:
        flash(f"Registration failed: {err}", 'error')
    finally:
        conn.close()

    return redirect('/')

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
    if 'user_id' not in session or session.get('role') != 'Attendee':
        return redirect('/')

    conn = get_db_connection()
    if not conn:
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

            # Get event details with lock
            cursor.execute("""
                SELECT Fee, Capacity FROM Events 
                WHERE EventID = %s AND Date >= CURDATE() 
                FOR UPDATE
            """, (event_id,))
            event = cursor.fetchone()

            if not event:
                flash("Event not found or has already occurred!", 'error')
                conn.rollback()
                return redirect('/dashboard')

            fee, capacity = float(event[0]), int(event[1])
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
                registration_id = existing_reg[0]
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
            else:
                # Create new registration
                cursor.execute("""
                    INSERT INTO Registrations (UserID, EventID, Status)
                    VALUES (%s, %s, 'Active')
                """, (session['user_id'], event_id))
                registration_id = cursor.lastrowid

                # Create payment record
                cursor.execute("""
                    INSERT INTO Payments (RegistrationID, Amount, Status)
                    VALUES (%s, %s, 'Pending')
                """, (registration_id, fee))

            # Update capacity
            cursor.execute("""
                UPDATE Events SET Capacity = Capacity - 1 
                WHERE EventID = %s AND Capacity > 0
            """, (event_id,))

            if cursor.rowcount == 0:
                flash("Failed to update event capacity!", 'error')
                conn.rollback()
                return redirect('/dashboard')

            conn.commit()
            flash("Registration successful! Please proceed to payment.", 'success')
            return redirect('/payments')

    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Registration failed: {err}", 'error')
    finally:
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

            # Get event date along with registration details
            cursor.execute("""
                SELECT R.EventID, E.Date 
                FROM Registrations R
                JOIN Events E ON R.EventID = E.EventID
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

            event_id, event_date = result

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
            flash("Registration cancelled successfully", 'success')

    except mysql.connector.Error as err:
        conn.rollback()
        flash(f"Cancellation failed: {err}", 'error')
    finally:
        if conn.is_connected():
            conn.close()

    return redirect('/my-registrations')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')



@app.route('/submit-feedback/<int:event_id>', methods=['GET', 'POST'])
def submit_feedback(event_id):
    if 'user_id' not in session or session.get('role') != 'Attendee':
        return redirect('/')
    
    conn = get_db_connection()
    if not conn:
        return redirect('/my-registrations')

    try:
        with conn.cursor(dictionary=True) as cursor:
            # Get event details with time validation
            cursor.execute("""
                SELECT E.EventName, E.Date AS event_date, E.EndTime, 
                       TIMESTAMP(E.Date, E.EndTime) AS event_end,
                       TIMESTAMP(E.Date, E.EndTime) + INTERVAL 48 HOUR AS feedback_deadline
                FROM Events E
                JOIN Registrations R ON E.EventID = R.EventID
                WHERE R.UserID = %s 
                AND E.EventID = %s 
                AND R.Status = 'Active'
            """, (session['user_id'], event_id))
            event_data = cursor.fetchone()
            
            if not event_data:
                flash("Invalid event or registration", 'error')
                return redirect('/my-registrations')

            from datetime import datetime, timedelta

            # Convert database times to Python datetime objects
            try:
                event_end = event_data['event_end']
                feedback_deadline = event_data['feedback_deadline']
            except KeyError:
                flash("Event time data is invalid", 'error')
                return redirect('/my-registrations')

            current_time = datetime.now()

            # Check if event hasn't ended yet
            if current_time < event_end:
                flash("This event has not yet completed. Feedback cannot be submitted yet.", 'warning')
                return redirect('/my-registrations')

            # Check if feedback window has expired
            if current_time > feedback_deadline:
                flash("Feedback submission is only allowed within 48 hours after event completion", 'error')
                return redirect('/my-registrations')

            # Handle form submission
            if request.method == 'POST':
                rating = request.form.get('rating')
                comment = request.form.get('comment', '').strip()

                if not rating or not rating.isdigit() or int(rating) not in range(1, 6):
                    flash("Please provide a valid rating (1-5)", 'error')
                    return redirect(f'/submit-feedback/{event_id}')

                try:
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            INSERT INTO Feedback (UserID, EventID, Rating, Comment)
                            VALUES (%s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE 
                            Rating = VALUES(Rating), Comment = VALUES(Comment)
                        """, (session['user_id'], event_id, rating, comment))
                        conn.commit()
                        flash("Feedback submitted successfully!", 'success')
                        return redirect('/my-registrations')
                except mysql.connector.Error as err:
                    conn.rollback()
                    flash(f"Failed to save feedback: {err}", 'error')
                    return redirect(f'/submit-feedback/{event_id}')

            # GET request - show form
            cursor.execute("""
                SELECT Rating, Comment FROM Feedback 
                WHERE UserID = %s AND EventID = %s
            """, (session['user_id'], event_id))
            existing_feedback = cursor.fetchone()
        
            return render_template(
                'feedback_form.html',
                event=event_data,
                existing_feedback=existing_feedback,
                deadline=feedback_deadline.strftime('%Y-%m-%d %H:%M:%S')
            )

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", 'error')
        return redirect('/my-registrations')
    except Exception as e:
        flash(f"Unexpected error: {str(e)}", 'error')
        return redirect('/my-registrations')
    finally:
        if conn.is_connected():
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