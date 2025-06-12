from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import requests
import logging # Import logging

from app.extensions import db, oauth
from app.models.models import User, Post # Assuming Post is in models.py and imported here
from app.forms import LoginForm, RegisterForm

auth = Blueprint('auth', __name__)

# Configure logging for this blueprint
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define the Django API base URL
DJANGO_API_BASE_URL = "https://gax-2.onrender.com/api"
DJANGO_LOGIN_API_URL = f"{DJANGO_API_BASE_URL}/login/"


def init_oauth(app):
    """Initializes and registers OAuth clients."""
    # This line might be redundant if already called in create_app, but harmless
    oauth.init_app(app) 
    
    # Register Google OAuth (Facebook removed)
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
    # Facebook OAuth registration removed


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    
    if request.method == 'GET':
        form = RegisterForm()
        return render_template('register.html', form=form)
    
    if request.is_json:
        data = request.get_json()
        
        # Validate the data
        if not all([data.get('username'), data.get('email'), data.get('password'), data.get('password2')]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        if data['password'] != data['password2']:
            return jsonify({'error': 'Passwords do not match'}), 400
            
        # Check if user exists
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username is already taken'}), 400
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'Email is already registered'}), 400
            
        # Create user
        try:
            hashed_password = generate_password_hash(data['password'])
            new_user = User(
                username=data['username'],
                email=data['email'],
                password=hashed_password,
                full_name=data.get('full_name'),
                phone_number=data.get('phone_number'),
                age=data.get('age'),
                address=data.get('address')
            )
            db.session.add(new_user)
            db.session.commit()
            return jsonify({'message': 'Registration successful'}), 201
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error during registration: {e}")
            return jsonify({'error': 'Registration failed'}), 500
    
    # Handle regular form submission
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data
        password2 = form.password2.data

        # Validate passwords match
        if password != password2:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', form=form)
        
        # Check if user already exists in Flask's DB
        if User.query.filter_by(username=username).first():
            flash('That username is already taken. Please choose a different one.', 'danger')
            return render_template('register.html', form=form)
        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists. Please use a different email or login.', 'danger')
            return render_template('register.html', form=form)

        # First create user in Flask's DB
        try:
            hashed_password = generate_password_hash(password)
            new_user = User(
                username=username, 
                email=email, 
                password=hashed_password,
                full_name=form.full_name.data,
                phone_number=form.phone_number.data,
                age=form.age.data,
                address=form.address.data
            )
            db.session.add(new_user)
            db.session.commit()

            # Then try to register with Django API
            django_register_api_url = f"{DJANGO_API_BASE_URL}/register/"
            payload = {
                'username': username,
                'email': email,
                'password': password,
                'password2': password,
                'full_name': form.full_name.data,
                'phone_number': form.phone_number.data,
                'age': form.age.data,
                'address': form.address.data
            }

            headers = {
                'Content-Type': 'application/json'
            }

            django_response = requests.post(django_register_api_url, json=payload, headers=headers)
            
            # Handle successful registration or 401 (which might mean auth isn't required)
            if django_response.status_code in [200, 201, 401]:
                flash('Account created successfully! Please log in.', 'success')
                return redirect(url_for('auth.login'))
            
            # For any other error status
            django_data = django_response.json()
            logger.info(f"Django Register API Response Status: {django_response.status_code}")
            logger.info(f"Django Register API Response Data: {django_data}")

            # If Django registration fails with any other status, rollback Flask registration
            db.session.delete(new_user)
            db.session.commit()
            
            # Extract error messages from Django response
            error_messages = []
            if isinstance(django_data, dict):
                for field, errors in django_data.items():
                    if isinstance(errors, list):
                        error_messages.extend([f"{field}: {e}" for e in errors])
                    else:
                        error_messages.append(f"{field}: {errors}")
            
            final_error_message = ", ".join(error_messages) if error_messages else "Registration failed. Please try again."
            flash(final_error_message, 'danger')
            return render_template('register.html', form=form)

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during Django registration: {e}")
            # If Django registration fails due to network error, still keep the Flask registration
            flash('Account created successfully! Please log in.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('register.html', form=form)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('views.home'))
    
    if request.method == 'GET':
        form = LoginForm()
        return render_template('login.html', form=form)

    if request.is_json:
        data = request.get_json()
        username_or_email = data.get('email')
        password = data.get('password')
        remember_me = data.get('remember_me', False)

        # Find user in Flask's DB
        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()

        if not user or not check_password_hash(user.password, password):
            return jsonify({'error': 'Invalid username/email or password'}), 401

        login_user(user, remember=remember_me)
        return jsonify({'message': 'Login successful'})
    
    # Handle regular form submission
    form = LoginForm()
    if form.validate_on_submit():
        username_or_email = form.email.data # Assuming 'email' field in form is used for username or email
        password = form.password.data

        # Find user in Flask's DB (login based on local Flask user)
        user = User.query.filter(
            (User.username == username_or_email) | (User.email == username_or_email)
        ).first()

        if not user or not check_password_hash(user.password, password):
            flash('Login Unsuccessful. Please check username/email and password', 'danger')
            return render_template('login.html', form=form)        # Log in the user locally first
        login_user(user, remember=form.remember_me.data)
        
        # Then attempt to log in to Django API
        logger.info("Attempting to log in to Django API...")
        login_payload = {
            "username": user.username,
            "password": password,
            "headers": {
                'Content-Type': 'application/json'
            }
        }
        try:
            django_response = requests.post(DJANGO_LOGIN_API_URL, json=login_payload)
            
            if django_response.status_code == 200:
                try:
                    django_data = django_response.json()
                    if 'token' in django_data:
                        token = django_data['token']
                        session['django_api_token'] = token
                        logger.info(f"Django API token obtained and stored in session: {token[:10]}...")
                        flash('Successfully logged in and synchronized with banking service!', 'success')
                    else:
                        logger.warning("Django login successful but no token received")
                        flash('Logged in successfully, but banking sync is temporarily unavailable.', 'warning')
                except ValueError:
                    logger.warning("Could not parse Django API response")
                    flash('Logged in successfully, but banking sync is temporarily unavailable.', 'warning')
            else:
                logger.warning(f"Django login failed with status {django_response.status_code}")
                flash('Logged in successfully, but banking sync is temporarily unavailable.', 'warning')
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Django API: {e}")
            flash('Logged in successfully, but banking sync is temporarily unavailable.', 'warning')        # Always redirect to home after successful local login
        next_page = request.args.get('next')
        return redirect(next_page or url_for('views.home'))
    
    return render_template('login.html', form=form)

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('django_api_token', None) # Clear Django API token from session
    logger.info("User logged out and Django API token cleared from session.")
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

# --- User Profile (if moved from views to auth blueprint, for simple structures) ---
# If you have a separate 'user' blueprint (app.routes.user), remove this and keep it there.
@auth.route("/user/<username>")
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.timestamp.desc()).all()
    # Check if current_user is following this user
    is_following = False
    if current_user.is_authenticated and hasattr(current_user, 'is_following'):
        is_following = current_user.is_following(user)
    return render_template("profile.html", user=user, posts=posts, is_following=is_following)


# --- AJAX Username/Email Availability Check ---
@auth.route('/check-availability')
def check_availability():
    check_type = request.args.get('type')
    value = request.args.get('value')
    if not check_type or not value:
        return jsonify({"error": "Missing parameters"}), 400
    if check_type == 'username':
        existing = User.query.filter_by(username=value).first()
    elif check_type == 'email':
        existing = User.query.filter_by(email=value).first()
    else:
        return jsonify({"error": "Invalid check type"}), 400
    return jsonify({"available": existing is None})

# --- Google OAuth ---
@auth.route('/login/google')
def login_google():
    redirect_uri = url_for('auth.authorize_google', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)

@auth.route('/auth/google')
def authorize_google():
    try:
        token = oauth.google.authorize_access_token()
        resp = oauth.google.get('userinfo')
        resp.raise_for_status() # Raise an error for bad HTTP status codes
        user_info = resp.json()
        email = user_info.get('email')
        name = user_info.get('name')

        if not email:
            flash('Google authentication failed: No email provided by Google.', 'danger')
            return redirect(url_for('auth.login'))

        user = User.query.filter_by(email=email).first()
        if not user:
            username = (name or email.split('@')[0]).lower().replace(' ', '')
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
        return redirect(url_for('views.home')) # Redirect to 'home' route
    except Exception as e:
        logger.error(f"Google OAuth failed: {e}")
        flash(f'Google login failed: {e}', 'danger')
        return redirect(url_for('auth.login'))
