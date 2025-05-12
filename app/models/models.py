from datetime import datetime
from flask_login import UserMixin
from app import db
from sqlalchemy import Enum
from app.models.enums import Category  # Correct the import to point to the enums module

# Define the followers table
followers = db.Table(
    'followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

# User model
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)

    profile_picture = db.Column(db.String(255), default='default.png')
    age = db.Column(db.Integer)
    work = db.Column(db.String(150))
    bio = db.Column(db.String(300))
    category = db.Column(db.String(100))  # For search/filtering

    # One-to-many: User → Post
    posts = db.relationship('Post', backref='user', lazy=True)

    # Followers logic
    followed = db.relationship(
        'User',
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'),
        lazy='dynamic'
    )

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0

    def followed_posts(self):
        return Post.query.join(
            followers, (followers.c.followed_id == Post.user_id)
        ).filter(
            followers.c.follower_id == self.id
        ).order_by(Post.timestamp.desc())


# Post model
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    category = db.Column(
        Enum(Category, values_callable=lambda obj: [e.value for e in obj], native_enum=False),
        nullable=False
    )
    media_path = db.Column(db.String(255))
    media_type = db.Column(db.String(10)) 

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # Likes and Comments
    likes = db.relationship('Like', backref='post', lazy=True)
    comments = db.relationship('Comment', backref='post', lazy=True)
    views = db.Column(db.Integer, default=0)

    price = db.Column(db.Float, nullable=True)
    is_purchasable = db.Column(db.Boolean, default=False)
    
    
    
    def get_media_url(self):
        return self.media_path if self.media_path else 'default.jpg'



    def __repr__(self):
        return f'<Post {self.id} by {self.user.username}>'



# Like model
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))
    user = db.relationship('User', backref='likes')


# Comment model
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'))
