from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app.routes import posts

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    from app.routes import posts  # import routes after app is ready
    # app.register_blueprint(views.bp)

    return app
