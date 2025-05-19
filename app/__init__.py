from flask import Flask, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, CSRFError, generate_csrf
from app.extensions import socketio
from app.extensions import mail
from app.routes.messages import messages as messages_bp
from app.extensions import db, login_manager, csrf, migrate, mail, socketio


# Initialize extensions
# db = SQLAlchemy()
# login_manager = LoginManager()
# login_manager.login_view = 'auth.login'  
# csrf = CSRFProtect()
# migrate = Migrate()  

def create_app():
    app = Flask(__name__, static_folder='static')

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config.from_object('config.Config')
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    # Initialize extensions with app
    db.init_app(app)
    app.register_blueprint(messages_bp)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)  
    socketio.init_app(app)

    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=generate_csrf())

    @app.errorhandler(CSRFError)
    def handle_csrf_error(error):
        flash("CSRF token missing or incorrect. Please try again.", "danger")
        return redirect(url_for('views.home'))

    # Register blueprints
    from app.routes.auth import auth as auth_bp
    from app.routes.user import user as users_bp
    from app.routes.posts import views as views_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(views_bp)

    @login_manager.user_loader
    def load_user(user_id):
        from app.models.models import User
        return User.query.get(int(user_id))

    # --- Socket.IO event handlers ---
    from flask_socketio import emit, join_room, leave_room
    from flask_login import current_user

    @socketio.on('connect')
    def handle_connect():
        if current_user.is_authenticated:
            join_room(f'user_{current_user.id}')
            for participant in getattr(current_user, 'conversation_participants', []):
                join_room(f'conversation_{participant.conversation_id}')

    @socketio.on('disconnect')
    def handle_disconnect():
        if current_user.is_authenticated:
            leave_room(f'user_{current_user.id}')
            for participant in getattr(current_user, 'conversation_participants', []):
                leave_room(f'conversation_{participant.conversation_id}')

    @socketio.on('new_message')
    def handle_new_message(data):
        emit('message_received', data, room=f'conversation_{data["conversation_id"]}')

    @socketio.on('message_read')
    def handle_message_read(data):
        emit('message_status_update', data, room=f'conversation_{data["conversation_id"]}')

    return app