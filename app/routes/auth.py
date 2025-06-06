from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import requests
import logging

from app.extensions import db, oauth
from app.models.models import User
from app.forms import LoginForm, RegisterForm

auth = Blueprint('auth', __name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the Django API login URL
DJANGO_API_BASE_URL = "https://gax-2.onrender.com/api" # Ensure this is your actual Django API base URL
DJANGO_LOGIN_API_URL = f"{DJANGO_API_BASE_URL}/login/"
DJANGO_REGISTER_API_URL = f"{DJANGO_API_BASE_URL}/register/" # Assuming a Django register endpoint

def init_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=app.config['GOOGLE_CLIENT_ID'],
        client_secret=app.config['GOOGLE_CLIENT_SECRET'],
        access_token_url='https://oauth2.googleapis.com/token',
        authorize_url='https://accounts.google.com/o/oauth2/auth',
        api_base_url='https://www.googleapis.com/oauth2/v1/',
        userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
        client_kwargs={'scope': 'openid email profile'},
    )
   

@auth.route('/auth/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = generate_password_hash(form.password.data)
        
        # *** MODIFICATION START: Register user with Django API ***
        django_registration_data = {
            'username': form.username.data,
            'email': form.email.data,
            'password': form.password.data # Django will hash this
        }
        try:
            # Send registration data to Django bank app
            django_response = requests.post(DJANGO_REGISTER_API_URL, json=django_registration_data)
            django_response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
            flash('Successfully registered with bank service.', 'success')
            
            # If Django registration is successful, then register locally in Flask
            user = User(username=form.username.data, email=form.email.data, password=hashed_password)
            db.session.add(user)
            db.session.commit()
            flash('Your Choropia account has been created! You can now log in.', 'success')
            return redirect(url_for('auth.login'))

        except requests.exceptions.RequestException as e:
            logger.error(f"Error registering with Django bank API: {e}")
            flash(f'Registration with bank service failed: {e}', 'danger')
            # You might want to handle specific Django API error messages here
            if django_response.status_code == 400: # Example for Django validation errors
                error_details = django_response.json()
                for field, errors in error_details.items():
                    flash(f'{field}: {", ".join(errors)}', 'danger')
            return render_template('register.html', form=form)
        # *** MODIFICATION END ***

    return render_template('register.html', form=form)

@auth.route('/auth/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user, remember=form.remember_me.data)
            flash('Logged in successfully to Choropia!', 'success')
            
            # *** MODIFICATION START: Authenticate with Django API and store token ***
            django_login_data = {
                'email': form.email.data, # Or 'username': user.username.data if Django uses username
                'password': form.password.data
            }
            try:
                # Send login data to Django bank app
                django_response = requests.post(DJANGO_LOGIN_API_URL, json=django_login_data)
                django_response.raise_for_status() # Raise an exception for HTTP errors (4xx or 5xx)
                
                django_token = django_response.json().get('token') # Get token from Django response
                if django_token:
                    session['django_api_token'] = django_token
                    flash('Successfully authenticated with bank service.', 'info')
                else:
                    flash('Authenticated with bank service, but no token received. API calls might fail.', 'warning')

            except requests.exceptions.RequestException as e:
                logger.error(f"Error logging into Django bank API: {e}")
                flash(f'Failed to authenticate with bank service: {e}', 'danger')
            # *** MODIFICATION END ***

            next_page = request.args.get('next')
            return redirect(next_page or url_for('views.home'))
        else:
            flash('Login Unsuccessful. Please check email and password', 'danger')
    return render_template('login.html', form=form)

@auth.route('/auth/logout')
@login_required
def logout():
    logout_user()
    if 'django_api_token' in session:
        session.pop('django_api_token', None) # Clear Django token on logout
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth.route('/auth/google')
def login_google():
    redirect_uri = url_for('auth.authorize_google', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@auth.route('/auth/google/callback')
def authorize_google():
    try:
        token = oauth.google.authorize_access_token()
        resp = oauth.google.get('userinfo')
        resp.raise_for_status()
        user_info = resp.json()
        email = user_info.get('email')
        name = user_info.get('name')
        if not email:
            flash('Google authentication failed.', 'danger')
            return redirect(url_for('auth.login'))
        
        user = User.query.filter_by(email=email).first()
        if not user:
            username = email.split('@')[0].lower().replace('.', '')
            base_username = username
            count = 1
            while User.query.filter_by(username=username).first():
                username = f"{base_username}{count}"
                count += 1
            
            random_password = secrets.token_urlsafe(16)
            hashed_password = generate_password_hash(random_password)
            user = User(username=username, email=email, password=hashed_password, full_name=name)
            db.session.add(user)
            db.session.commit()
            
        login_user(user, remember=True)
        flash('Logged in with Google!', 'success')
        
        # *** MODIFICATION START: Handle Google OAuth for Django API ***
        # If your Django bank API also supports Google OAuth, you'd typically send the Google access_token
        # or an ID Token to a Django endpoint for token exchange.
        # This example assumes Django provides a dedicated endpoint for Google token exchange.
        # You'll need to adapt this based on your Django bank's OAuth implementation.
        if 'access_token' in token:
            try:
                django_google_auth_data = {
                    'access_token': token['access_token'],
                    # 'id_token': token.get('id_token') # If Django supports ID Tokens
                }
                # Assuming a Django API endpoint that exchanges Google token for Django's own token
                django_auth_response = requests.post(f"{DJANGO_API_BASE_URL}/social/google/", json=django_google_auth_data)
                django_auth_response.raise_for_status()
                django_token = django_auth_response.json().get('token')
                if django_token:
                    session['django_api_token'] = django_token
                    flash('Authenticated bank service via Google.', 'info')
                else:
                    flash('Bank service authentication via Google failed (no token received).', 'warning')
            except requests.exceptions.RequestException as e:
                logger.error(f"Error authenticating Django bank API with Google token: {e}")
                flash(f'Failed to connect bank service via Google: {e}', 'danger')
        # *** MODIFICATION END ***

        return redirect(url_for('views.home'))
    except Exception as e:
        logger.error(f"Google OAuth error: {e}")
        flash('Google authentication failed.', 'danger')
        return redirect(url_for('auth.login'))

