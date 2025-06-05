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
    # Assuming you have a config.py with a Config class.
    # If not, ensure these config variables are set directly or from environment variables.
    app.config.from_object('config.Config')
    
    # CRITICAL: Ensure these are set, either here or in your config.py
    # Change 'your_super_secret_key_change_this_in_production' to a strong, unique key!
    app.config.setdefault('SECRET_KEY', 'your_super_secret_key_change_this_in_production') 
    app.config.setdefault('SQLALCHEMY_DATABASE_URI', 'sqlite:///db.sqlite3')
    app.config.setdefault('SQLALCHEMY_TRACK_MODIFICATIONS', False)
    app.config.setdefault('TEMPLATES_AUTO_RELOAD', True)

    # Optional: OAuth credentials (ensure these are in your config.Config or .env)
    # Replace these placeholders with your actual client IDs and secrets
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
    oauth.init_app(app) # Initialize Flask-Dance OAuth extension

    # Import and initialize OAuth configuration from auth blueprint
    # This must be called AFTER oauth.init_app(app)
    from app.routes.auth import init_oauth
    init_oauth(app) # Call the function to register OAuth clients (Google, Facebook)

    # Import and register your blueprints
    # Ensure these imports match your file structure (e.g., app.routes.auth, app.routes.posts)
    from app.routes.auth import auth as auth_bp
    from app.routes.user import user as users_bp # Assuming you have a user blueprint
    from app.routes.posts import views as views_bp
    from app.routes.posts import notifications as notifications_bp # If notifications are a separate blueprint
    from app.routes.messages import messages as messages_bp # Assuming you have a messages blueprint

    app.register_blueprint(auth_bp, url_prefix='/auth') # Register auth blueprint, often with a prefix
    app.register_blueprint(users_bp) # Register user blueprint
    app.register_blueprint(views_bp) # Crucial: This registers the 'views' blueprint containing 'send_money'
    app.register_blueprint(notifications_bp) # Register notifications blueprint
    app.register_blueprint(messages_bp) # Register messages blueprint


    # User loader for Flask-Login (required)
    @login_manager.user_loader
    def load_user(user_id):
        from app.models.models import User # Import User model here to avoid circular imports
        return User.query.get(int(user_id))

    # Context processor for CSRF token (useful for Jinja templates)
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
            days = int(seconds // 86400)
            return f"{days} day{'s' if days != 1 else ''} ago"
        elif seconds < 604800:
            days = int(seconds // 86400)
            return f"{days} day{'s' if days != 1 else ''} ago" # This was a duplicate, kept for now.
        else:
            return dt.strftime('%Y-%m-%d')
    app.jinja_env.filters['timeago'] = timeago

    # --- Socket.IO event handlers ---
    # Ensure these are defined inside create_app() or in a separate file imported by create_app()
    @socketio.on('connect')
    def handle_connect():
        if current_user.is_authenticated:
            join_room(f'user_{current_user.id}')
            # Safely check for 'conversation_participants' attribute before iterating
            if hasattr(current_user, 'conversation_participants'):
                for participant in getattr(current_user, 'conversation_participants', []):
                    join_room(f'conversation_{participant.conversation_id}')

    @socketio.on('disconnect')
    def handle_disconnect():
        if current_user.is_authenticated:
            leave_room(f'user_{current_user.id}')
            # Safely check for 'conversation_participants' attribute before iterating
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