# app/extensions.py

from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO
from flask_wtf.csrf import CSRFProtect
from authlib.integrations.flask_client import OAuth

db = SQLAlchemy()
socketio = SocketIO()
csrf = CSRFProtect()
oauth = OAuth()
