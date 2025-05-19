from datetime import datetime
from flask_login import UserMixin
from app.extensions import db
from sqlalchemy import Enum
import enum
import json

# --- Category Enum ---
class Category(enum.Enum):
    GOODS = 'Goods'
    SERVICES = 'Services'
    INFO = 'Info'

# Followers association table
followers = db.Table(
    'followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

# --- User Model ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    profile_picture = db.Column(db.String(255), default='default.png')
    bio = db.Column(db.String(300), nullable=True)
    age = db.Column(db.Integer, nullable=True)
    work = db.Column(db.String(150), nullable=True)
    category = db.Column(db.String(100))  # For search/filtering
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    # Notification preferences (JSON string)
    notification_preferences = db.Column(
        db.String(500),
        default='{"app":true,"email":false,"likes":true,"comments":true,"follows":true,"mentions":true}'
    )

    # Relationships
    posts = db.relationship('Post', backref='user', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='user', lazy=True, cascade="all, delete-orphan")
    likes = db.relationship('Like', backref='user', lazy=True, cascade="all, delete-orphan")

    # Followers logic
    followed = db.relationship(
        'User',
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers_list', lazy='dynamic'),
        lazy='dynamic'
    )

    # Notifications relationships - sent and received
    sent_notifications = db.relationship('Notification', backref='sender',
                                         foreign_keys='Notification.sender_id', lazy=True)
    received_notifications = db.relationship('Notification', backref='recipient',
                                            foreign_keys='Notification.recipient_id', lazy=True)

    # Messaging relationships
    conversation_participants = db.relationship(
        'ConversationParticipant',
        back_populates='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    messages = db.relationship(
        'Message',
        back_populates='user',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )

    def get_notification_count(self):
        from app.models.models import Notification
        return Notification.query.filter_by(recipient_id=self.id, is_read=False).count()

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)
            # Create notification
            from app.routes.posts import send_notification
            send_notification(recipient_id=user.id, type='follow', sender_id=self.id)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0

    def get_notification_preferences(self):
        if not self.notification_preferences:
            return {"app": True, "email": False, "likes": True, "comments": True, "follows": True, "mentions": True}
        try:
            return json.loads(self.notification_preferences)
        except:
            return {"app": True, "email": False, "likes": True, "comments": True, "follows": True, "mentions": True}

    # --- Messaging methods ---
    def get_conversations(self):
        participant_entries = ConversationParticipant.query.filter_by(user_id=self.id).all()
        conversation_ids = [p.conversation_id for p in participant_entries]
        return Conversation.query.filter(Conversation.id.in_(conversation_ids)).order_by(Conversation.updated_at.desc()).all()

    def get_unread_message_count(self):
        count = 0
        for participant in self.conversation_participants:
            if participant.has_unread():
                count += 1
        return count

# --- Post Model ---
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500), nullable=True)
    media_path = db.Column(db.String(255), nullable=True)
    media_type = db.Column(db.String(20), nullable=True)
    category = db.Column(Enum(Category, values_callable=lambda obj: [e.value for e in obj], native_enum=False), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    views = db.Column(db.Integer, default=0)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    price = db.Column(db.Float, nullable=True)
    is_purchasable = db.Column(db.Boolean, default=False)

    # Relationships
    comments = db.relationship('Comment', backref='post', lazy=True, cascade="all, delete-orphan")
    likes = db.relationship('Like', backref='post', lazy=True, cascade="all, delete-orphan")
    notifications = db.relationship('Notification', backref='post', lazy=True,
                                    foreign_keys='Notification.post_id', cascade="all, delete-orphan")

    def get_media_url(self):
        return self.media_path if self.media_path else 'default.jpg'

    def __repr__(self):
        return f'<Post {self.id} by {self.user.username}>'

# --- Comment Model ---
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(200), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    notifications = db.relationship('Notification', backref='comment', lazy=True,
                                    foreign_keys='Notification.comment_id', cascade="all, delete-orphan")

    def save(self):
        db.session.add(self)
        db.session.commit()
        # Create notification
        from app.routes.posts import send_notification, process_mentions
        post = Post.query.get(self.post_id)
        if post and post.user_id != self.user_id:
            send_notification(
                recipient_id=post.user_id,
                type='comment',
                sender_id=self.user_id,
                post_id=self.post_id,
                comment_id=self.id
            )
        process_mentions(self.content, self.post_id, self.user_id)

# --- Like Model ---
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    def save(self):
        db.session.add(self)
        db.session.commit()
        # Create notification
        from app.routes.posts import send_notification
        post = Post.query.get(self.post_id)
        if post and post.user_id != self.user_id:
            send_notification(
                recipient_id=post.user_id,
                type='like',
                sender_id=self.user_id,
                post_id=self.post_id
            )

# --- Notification Model ---
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    type = db.Column(db.String(20), nullable=False)  # like, comment, follow, mention, system
    message = db.Column(db.String(200), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    preview_text = db.Column(db.String(200), nullable=True)
    link = db.Column(db.String(200), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    is_seen = db.Column(db.Boolean, default=False)

    def to_dict(self):
        sender = User.query.get(self.sender_id) if self.sender_id else None
        return {
            'id': self.id,
            'type': self.type,
            'message': self.message,
            'sender_name': sender.username if sender else 'System',
            'sender_avatar': f'/static/profile_pics/{sender.profile_picture}' if sender else '/static/profile_pics/default.jpg',
            'preview_text': self.preview_text,
            'link': self.link,
            'timestamp': self.timestamp.isoformat(),
            'is_read': self.is_read
        }

# ----- DATABASE MODELS FOR MESSAGING -----
class Conversation(db.Model):
    __tablename__ = 'conversations'
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    messages = db.relationship('Message', back_populates='conversation', lazy='dynamic', cascade='all, delete-orphan')
    participants = db.relationship('ConversationParticipant', back_populates='conversation',
                                  lazy='dynamic', cascade='all, delete-orphan')

    def add_participant(self, user_id):
        participant = ConversationParticipant(user_id=user_id, conversation_id=self.id)
        db.session.add(participant)
        return participant

    @property
    def last_message(self):
        return self.messages.order_by(Message.created_at.desc()).first()

    def is_participant(self, user_id):
        return ConversationParticipant.query.filter_by(
            conversation_id=self.id, user_id=user_id).first() is not None

class ConversationParticipant(db.Model):
    __tablename__ = 'conversation_participants'
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    last_read_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    conversation = db.relationship('Conversation', back_populates='participants')
    user = db.relationship('User', back_populates='conversation_participants')

    def mark_as_read(self):
        self.last_read_at = datetime.utcnow()
        db.session.commit()

    def has_unread(self):
        if not self.last_read_at:
            return self.conversation.messages.filter(Message.user_id != self.user_id).count() > 0
        return self.conversation.messages.filter(
            Message.created_at > self.last_read_at,
            Message.user_id != self.user_id
        ).count() > 0

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    conversation = db.relationship('Conversation', back_populates='messages')
    user = db.relationship('User', back_populates='messages')

    def mark_as_read(self):
        if not self.read_at:
            self.read_at = datetime.utcnow()
            db.session.commit()