from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, session # Import session
from flask_login import login_user, current_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import requests # Import requests for API calls

from app.extensions import db, oauth
from app.models.models import User, Post # Assuming Post is in models.py and imported here
from app.forms import LoginForm, RegisterForm

auth = Blueprint('auth', __name__)

# Define the Django API login URL
DJANGO_LOGIN_API_URL = "https://gax-2.onrender.com/api/login/"

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
    oauth.register(
        name='facebook',
        client_id=app.config['FACEBOOK_APP_ID'],
        client_secret=app.config['FACEBOOK_APP_SECRET'],
        access_token_url='https://graph.facebook.com/v19.0/oauth/access_token',
        authorize_url='https://www.facebook.com/v19.0/dialog/oauth',
        api_base_url='https://graph.facebook.com/v19.0/',
        client_kwargs={'scope': 'email'},
    )

# --- Registration ---
@auth.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('views.home')) # Changed from views.feed to views.home for consistency
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data

        if User.query.filter_by(username=username).first():
            flash('That username is already taken. Please choose a different one.', 'danger')
            return render_template('register.html', form=form)
        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists. Please use a different email or login.', 'danger')
            return render_template('register.html', form=form)

        hashed_password = generate_password_hash(password)
        # Ensure 'password_hash' is the correct attribute for storing hashed passwords in your User model
        new_user = User(username=username, email=email, password_hash=hashed_password) 
        db.session.add(new_user)
        db.session.commit()
        flash('Your account has been created! You can now login.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('register.html', form=form)

# --- Login ---
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('views.home')) # Changed from views.feed to views.home for consistency
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        # Assuming your User model uses 'password_hash' for hashed passwords
        if user and check_password_hash(user.password_hash, form.password.data): 
            login_user(user, remember=getattr(form, 'remember', False))
            
            # --- NEW: Attempt to log in to Django API and get token ---
            try:
                django_login_data = {
                    'username': user.username, # Use Flask user's username for Django login
                    'password': form.password.data # Send the plain password to Django for token
                }
                django_response = requests.post(DJANGO_LOGIN_API_URL, json=django_login_data)
                django_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                
                django_api_data = django_response.json()
                if 'token' in django_api_data:
                    session['django_token'] = django_api_data['token']
                    print(f"Django Token obtained: {django_api_data['token']}") # For debugging
                    flash('Successfully logged into banking service!', 'info')
                else:
                    flash('Logged into Flask, but could not get Django API token. Banking features may be limited.', 'warning')
                    print(f"Django login response: {django_api_data}")

            except requests.exceptions.RequestException as e:
                flash('Logged into Flask, but failed to connect to Django banking API. Banking features may be limited.', 'warning')
                print(f"Error logging into Django API: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"Django API error response: {e.response.text}")
            # --- End Django API login attempt ---

            next_page = request.args.get('next')
            flash('Login successful!', 'success')
            return redirect(next_page or url_for('views.home')) # Changed from views.feed to views.home for consistency
        else:
            flash('Login unsuccessful. Please check email and password.', 'danger')
    return render_template('login.html', form=form)

# --- Logout ---
@auth.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('django_token', None) # Clear Django token from session on logout
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))

# --- User Profile ---
@auth.route("/user/<username>")
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.timestamp.desc()).all()
    return render_template("profile.html", user=user, posts=posts)

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
    token = oauth.google.authorize_access_token()
    resp = oauth.google.get('userinfo')
    user_info = resp.json()
    email = user_info.get('email')
    name = user_info.get('name')
    if not email:
        flash('Google authentication failed.', 'danger')
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
        user = User(username=username, email=email, password_hash=hashed_password, oauth_provider='google') # Use password_hash
        db.session.add(user)
        db.session.commit()
    login_user(user, remember=True)
    flash('Logged in with Google!', 'success')
    return redirect(url_for('views.home')) # Changed from views.feed to views.home for consistency

# --- Facebook OAuth ---
@auth.route('/login/facebook')
def login_facebook():
    redirect_uri = url_for('auth.authorize_facebook', _external=True)
    return oauth.facebook.authorize_redirect(redirect_uri)

@auth.route('/auth/facebook')
def authorize_facebook():
    token = oauth.facebook.authorize_access_token()
    resp = oauth.facebook.get('me?fields=id,name,email')
    user_info = resp.json()
    email = user_info.get('email')
    name = user_info.get('name')
    if not email:
        flash('Facebook authentication failed.', 'danger')
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
        user = User(username=username, email=email, password_hash=hashed_password, oauth_provider='facebook') # Use password_hash
        db.session.add(user)
        db.session.commit()
    login_user(user, remember=True)
    flash('Logged in with Facebook!', 'success')
    return redirect(url_for('views.home')) # Changed from views.feed to views.home for consistency
