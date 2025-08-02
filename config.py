DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Flydeepthi@1',
    'database': 'EventRegistrationDB'
}

# --- Email Configuration for Flask-Mail (using Gmail) ---
# IMPORTANT: Use an App Password if you have 2-Factor Authentication enabled (recommended).
# Your regular Google account password will likely NOT work here if 2FA is on.
MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587          # Use port 587 for TLS
MAIL_USE_TLS = True      # Enable TLS
MAIL_USE_SSL = False     # Disable SSL when using TLS on port 587
MAIL_USERNAME = 'bhavanabc05@gmail.com' # <-- Use your Gmail address here
MAIL_PASSWORD = 'tcss ykfz mkys pleh'   # <-- REPLACE THIS with the 16-character App Password you generated
MAIL_DEFAULT_SENDER = 'Your Event App <bhavanabc05@gmail.com>' # <-- Use your Gmail and desired display name
# --------------------------------------------------------
