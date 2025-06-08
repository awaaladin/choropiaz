import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key' # CHANGE THIS IN PRODUCTION!
    SQLALCHEMY_DATABASE_URI = 'sqlite:///socialnet.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Ensure these match what's expected in app/__init__.py for OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', 'your-google-client-id-from-config')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', 'your-google-client-secret-from-config')
    
    # FACEBOOK APP_ID and APP_SECRET removed
    # FACEBOOK_APP_ID = os.environ.get('FACEBOOK_APP_ID', 'your-facebook-app-id-from-config')
    # FACEBOOK_APP_SECRET = os.environ.get('FACEBOOK_APP_SECRET', 'your-facebook-app-secret-from-config')

    # Django API credentials for internal server-to-server calls (e.g., for send_money)
    # Store these securely, preferably in environment variables.
    # Replace with actual Django admin username and password for your banking app.
    DJANGO_ADMIN_USERNAME = os.environ.get('DJANGO_ADMIN_USERNAME', 'admin') # IMPORTANT: Replace with your Django admin username
    DJANGO_ADMIN_PASSWORD = os.environ.get('DJANGO_ADMIN_PASSWORD', 'adminpassword') # IMPORTANT: Replace with your Django admin password