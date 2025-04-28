DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'bhavana@123',
    'database': 'EventRegistrationDB'
}

# --- Email Configuration for Flask-Mail ---
# IMPORTANT: Replace these with your actual email provider settings.
# Using environment variables is recommended for production secrets!
MAIL_SERVER = 'your_mail_server' # e.g., 'smtp.gmail.com'
MAIL_PORT = 587 # Common ports: 587 (TLS), 465 (SSL)
MAIL_USE_TLS = True # Set to False if using SSL (port 465)
MAIL_USE_SSL = False # Set to True if using SSL (port 465)
MAIL_USERNAME = 'your_email@example.com' # Your email address
MAIL_PASSWORD = 'your_email_password'   # Your email password
MAIL_DEFAULT_SENDER = 'your_email@example.com' # Or the name you want to display <your_email@example.com>
# -----------------------------------------