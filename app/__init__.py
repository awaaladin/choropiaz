from flask import Flask, render_template, redirect, url_for, flash
from flask_wtf.csrf import CSRFError, generate_csrf
from datetime import datetime
from flask_socketio import emit, join_room, leave_room
from flask_login import current_user

# Import all extensions from app.extensions
from app.extensions import db, login_manager, csrf, migrate, mail, socketio, oauth

def create_app():
    app = Flask(__name__, static_folder='static')

    # Load configuration
    app.config.from_object('config.Config')
    
    # CRITICAL: Ensure these are set, either here or in your config.py
    app.config.setdefault('SECRET_KEY', 'your_super_secret_key_change_this_in_production')
    app.config.setdefault('SQLALCHEMY_DATABASE_URI', 'sqlite:///db.sqlite3')
    app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
    app.config.setdefault('TEMPLATES_AUTO_RELOAD', True)

    # Optional: OAuth credentials (ensure these are in your config.Config or .env)
    app.config.setdefault('GOOGLE_CLIENT_ID', 'your-google-client-id')
    app.config.setdefault('GOOGLE_CLIENT_SECRET', 'your-google-client-secret')
    app.config.setdefault('FACEBOOK_APP_ID', 'your-facebook-app-id')
    app.config.setdefault('FACEBOOK_APP_SECRET', 'your-facebook-app-secret')

    # Initialize Flask extensions with the app instance
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app)
    oauth.init_app(app)

    # Configure Flask-Login's login view (CRITICAL FIX FOR 404 ON /login)
    login_manager.login_view = 'auth.login'

    # Import and initialize OAuth configuration from auth blueprint
    from app.routes.auth import init_oauth
    init_oauth(app)

    # Import and register your blueprints
    from app.routes.auth import auth as auth_bp
    from app.routes.user import user as users_bp # Assuming you have a user blueprint
    from app.routes.posts import views as views_bp
    from app.routes.posts import notifications as notifications_bp
    from app.routes.messages import messages as messages_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(users_bp)
    app.register_blueprint(views_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(messages_bp)


    # User loader for Flask-Login (required)
    @login_manager.user_loader
    def load_user(user_id):
        from app.models.models import User
        return User.query.get(int(user_id))

    # Context processor for CSRF token
    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=generate_csrf())

    # CSRF error handler
    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        flash("CSRF token missing or incorrect. Please try again.", "danger")
        return redirect(url_for('views.home'))

    # Register 'timeago' filter for Jinja
    def timeago(dt):
        now = datetime.utcnow()
        diff = now - dt
        seconds = diff.total_seconds()
        if seconds < 60:
            return f"{int(seconds)} seconds ago"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds // 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        else:
            return dt.strftime('%Y-%m-%d')
    app.jinja_env.filters['timeago'] = timeago

    # --- Socket.IO event handlers ---
    @socketio.on('connect')
    def handle_connect():
        if current_user.is_authenticated:
            join_room(f'user_{current_user.id}')
            if hasattr(current_user, 'conversation_participants'):
                for participant in getattr(current_user, 'conversation_participants', []):
                    join_room(f'conversation_{participant.conversation_id}')

    @socketio.on('disconnect')
    def handle_disconnect():
        if current_user.is_authenticated:
            leave_room(f'user_{current_user.id}')
            if hasattr(current_user, 'conversation_participants'):
                for participant in getattr(current_user, 'conversation_participants', []):
                    leave_room(f'conversation_{participant.conversation_id}')

    @socketio.on('new_message')
    def handle_new_message(data):
        emit('message_received', data, room=f'conversation_{data["conversation_id"]}')

    @socketio.on('message_read')
    def handle_message_read(data):
        emit('message_status_update', data, room=f'conversation_{data["conversation_id"]}')

    return app