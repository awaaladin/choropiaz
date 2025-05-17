from flask import Flask
from app.extensions import db, socketio, csrf, oauth

def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = 'your_secret_key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Optional: OAuth credentials
    app.config['GOOGLE_CLIENT_ID'] = 'your-google-client-id'
    app.config['GOOGLE_CLIENT_SECRET'] = 'your-google-client-secret'
    app.config['FACEBOOK_APP_ID'] = 'your-facebook-app-id'
    app.config['FACEBOOK_APP_SECRET'] = 'your-facebook-app-secret'

    db.init_app(app)
    socketio.init_app(app)
    csrf.init_app(app)
    oauth.init_app(app)

    from app.routes.posts import views
    from app.routes.auth import auth, init_oauth

    init_oauth(app)
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(views)

    return app
