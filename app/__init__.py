from flask import Flask, render_template, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect, CSRFError, generate_csrf

# Initialize extensions
db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
migrate = Migrate()  # ✅ You missed this line in your version

def create_app():
    app = Flask(__name__, static_folder='static')

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite3'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config.from_object('config.Config')
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)  # ✅ Use migrate.init_app, not just Migrate(app, db)

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

    return app
