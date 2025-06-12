import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///socialnet.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Django API credentials
    DJANGO_ADMIN_USERNAME = os.environ.get('DJANGO_ADMIN_USERNAME', 'admin')
    DJANGO_ADMIN_PASSWORD = os.environ.get('DJANGO_ADMIN_PASSWORD', 'your-secure-password')
    DJANGO_API_TOKEN = os.environ.get('DJANGO_API_TOKEN')  # Add this if you have a permanent token
    
    # Google OAuth settings (if you're using them)
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', 'your-google-client-id-from-config')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', 'your-google-client-secret-from-config')