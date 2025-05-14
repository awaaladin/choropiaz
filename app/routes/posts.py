from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
import os
from app import db
from app.models.models import Post, Comment, Like, User, Category
from app.forms import PostForm, ProfileForm, RegisterForm, SettingsForm, UpdateProfileForm, ReelForm
from PIL import Image
from flask_socketio import SocketIO, emit
from app.extensions import socketio



views = Blueprint('views', __name__)

# --- Constants ---
UPLOAD_FOLDER = os.path.join("static", "uploads")
PROFILE_UPLOAD_FOLDER = os.path.join("static", "profile_pics")
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "webm"}
PROFILE_PIC_FOLDER = 'static/profile_pics'

if not os.path.exists(PROFILE_PIC_FOLDER):
    os.makedirs(PROFILE_PIC_FOLDER)




@socketio.on('connect')
def handle_connect():
    # Emit latest notifications to the connected user
    notifications = get_user_notifications(current_user.id)
    emit('notifications', notifications)

def send_daily_notification(user_id, message):
    socketio.emit('new_notification', {'message': message}, room=user_id)




def save_picture(form_picture):
    # Secure the filename (sanitize any unsafe characters)
    random_hex = os.urandom(8).hex()
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_filename = random_hex + f_ext

    # Path to save the picture
    picture_path = os.path.join(PROFILE_PIC_FOLDER, picture_filename)

    # Open the image using Pillow and resize it
    output_size = (125, 125)  # Resize to 125x125 (you can adjust as needed)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)

    return picture_filename

def get_user_data():
    # Example data retrieval (you would typically query the database)
    return {
        'email': 'user@example.com',
        'password': 'hashedpassword',
        'language': 'en',
        'notifications': True,
        'profile_picture': 'default.jpg'  # Assuming a default profile picture
    }

def update_user_data(updated_data):
    # Example data update (you would typically update the database here)
    print(f"Updating user data with: {updated_data}")
    # Save to database logic
    pass





# --- Utility Functions ---
def allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    return ext in ALLOWED_IMAGE_EXTENSIONS.union(ALLOWED_VIDEO_EXTENSIONS)

def get_media_type(filename):
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return "image"
    elif ext in ALLOWED_VIDEO_EXTENSIONS:
        return "video"
    return None

def get_top_weekly_posts():
    one_week_ago = datetime.now() - timedelta(weeks=1)
    top_posts = Post.query.filter(Post.timestamp >= one_week_ago).order_by(Post.views.desc()).limit(10).all()
    posts_by_category = {'Goods': [], 'Services': [], 'Info': []}
    for post in top_posts:
        category_name = post.category.name if post.category else ''
        if category_name == Category.GOODS.name:
            posts_by_category['Goods'].append(post)
        elif category_name == Category.SERVICES.name:
            posts_by_category['Services'].append(post)
        elif category_name == Category.INFO.name:
            posts_by_category['Info'].append(post)
    return posts_by_category

def get_trending_posts():
    one_week_ago = datetime.now() - timedelta(weeks=1)
    return Post.query.filter(Post.timestamp >= one_week_ago).order_by(Post.likes.desc()).limit(10).all()



def load_feed_data():
    form = PostForm()
    search_query = request.args.get('search')

    followed_posts_query = current_user.followed_posts().order_by(Post.timestamp.desc())
    user_posts_query = Post.query.filter_by(user_id=current_user.id).order_by(Post.timestamp.desc())

    if search_query:
        try:
            category_enum = Category[search_query.upper()]
            followed_posts_query = followed_posts_query.filter(Post.category == category_enum)
            user_posts_query = user_posts_query.filter(Post.category == category_enum)
        except KeyError:
            pass

    followed_posts = followed_posts_query.all()
    user_posts = user_posts_query.all()

    all_posts = followed_posts + user_posts
    all_posts = list(set(all_posts))  # Remove duplicates if needed
    all_posts.sort(key=lambda x: x.timestamp, reverse=True)
    if not all_posts:
        all_posts = Post.query.order_by(Post.timestamp.desc()).all()


    # If still no posts, show public posts
    if not all_posts:
        all_posts = Post.query.order_by(Post.timestamp.desc()).all()

    top_weekly_posts = get_top_weekly_posts()
    if not top_weekly_posts:
        top_weekly_posts = {
            'Goods': [],
            'Services': [],
            'Info': []
        }

    return form, all_posts, search_query, top_weekly_posts




@views.route('/', methods=['GET', 'POST'])
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))  
    form, posts, search_query, top_weekly_posts = load_feed_data()

    sort_by = request.args.get('sort', 'recent')
    if sort_by == 'likes':
        posts.sort(key=lambda x: x.likes, reverse=True)
    elif sort_by == 'trending':
        posts = get_trending_posts()
    else:
        posts.sort(key=lambda x: x.timestamp, reverse=True)

    return render_template(
        'feed.html',
        posts=posts,
        search_query=search_query,
        top_weekly_posts=top_weekly_posts,
        form=form,
        stories=top_weekly_posts
    )





from app.forms import PostForm  
@views.route('/feed', methods=['GET', 'POST'])
@login_required
def feed():
    form, posts, search_query, top_weekly_posts = load_feed_data()

    sort_by = request.args.get('sort', 'recent')
    if sort_by == 'likes':
        posts.sort(key=lambda x: x.likes, reverse=True)
    elif sort_by == 'trending':
        posts = get_trending_posts()  # this one might need special handling
    else:
        posts.sort(key=lambda x: x.timestamp, reverse=True)

    return render_template(
        'feed.html',
        posts=posts,
        search_query=search_query,
        top_weekly_posts=top_weekly_posts,
        form=form,
        stories=top_weekly_posts
    )


@views.route('/all-posts')
def all_posts_feed():
    posts = Post.query.order_by(Post.timestamp.desc()).all()
    return render_template('feed.html', posts=posts)


@views.route('/create_post', methods=['POST'])
@login_required
def create_post():
    if request.method == 'POST':
        caption = request.form['caption']
        category_str = request.form.get('category')

        try:
            category_enum = Category[category_str.lower()]
        except (KeyError, AttributeError):
            flash("Please select a valid category.", "danger")
            return redirect(url_for('views.feed'))

        media_path, media_type = None, None
        for field in ['image', 'video']:
            file = request.files.get(field)
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                media_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(media_path)
                media_type = get_media_type(filename)
                break

        new_post = Post(
            content=caption,
            category=category_enum,
            media_path=media_path,
            media_type=media_type,
            user_id=current_user.id,
            views=0
        )
        db.session.add(new_post)
        db.session.commit()

        flash("Post created successfully!", "success")
        return redirect(url_for('views.feed'))
    # return redirect(url_for('views.feed'))
    return 'Post created', 200

@views.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if like:
        db.session.delete(like)
    else:
        db.session.add(Like(user_id=current_user.id, post_id=post_id))
    db.session.commit()
    return redirect(url_for('views.feed'))

@views.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def comment_post(post_id):
    content = request.form.get('comment_content')
    if content:
        db.session.add(Comment(content=content, user_id=current_user.id, post_id=post_id))
        db.session.commit()
    return redirect(url_for('views.feed'))

@views.route('/view_post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    post.views += 1
    db.session.commit()
    return redirect(url_for('views.feed'))

@views.route('/delete_post/<int:post_id>', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user != current_user:
        abort(403)

    password = request.form.get('password')
    if not check_password_hash(current_user.password, password):
        flash("Incorrect password.", "danger")
        return redirect(url_for('views.feed'))

    if datetime.utcnow() - post.timestamp > timedelta(days=3):
        flash("Cannot delete post older than 3 days.", "warning")
        return redirect(url_for('views.feed'))

    db.session.delete(post)
    db.session.commit()
    flash("Post deleted.", "success")
    return redirect(url_for('views.feed'))

@views.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    if form.validate_on_submit():
        if form.profile_picture.data:
            picture_filename = secure_filename(form.profile_picture.data.filename)
            form.profile_picture.data.save(os.path.join(PROFILE_UPLOAD_FOLDER, picture_filename))
            current_user.profile_picture = picture_filename
            db.session.commit()
            flash('Profile updated!', 'success')
        return redirect(url_for('views.profile'))
    return render_template('profile.html', form=form, user=current_user)

@views.route('/user/<int:user_id>')
@login_required
def user_profile(user_id):
    user = User.query.get_or_404(user_id)
    return render_template('user_profile.html', user=user)


@views.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow_user(user_id):
    user = User.query.get_or_404(user_id)
    if user != current_user:
        current_user.follow(user)
        db.session.commit()
    return redirect(request.referrer or url_for('views.feed'))

@views.route('/search_users')
@login_required
def search_users():
    query = request.args.get('q', '').strip()
    users = User.query.filter(User.username.ilike(f'%{query}%')).all() if query else []
    return render_template('search_users.html', users=users, query=query)


from app.forms import UpdateProfileForm  

@views.route('/update_profile', methods=['GET', 'POST'])
@login_required
def update_profile():
    form = UpdateProfileForm()

    if request.method == 'POST' and form.validate_on_submit():
        # Update profile picture if a new one is uploaded
        if form.profile_picture.data:
            picture_filename = save_picture(form.profile_picture.data)
            current_user.profile_picture = picture_filename

        # Update the username, bio, age, and work fields
        current_user.username = form.username.data
        current_user.bio = form.bio.data
        current_user.age = form.age.data  # Update age
        current_user.work = form.work.data  # Update work
        
        # Commit the changes to the database
        db.session.commit()

        # Redirect to the profile page
        return redirect(url_for('views.profile'))

    # Prefill the form with current user's data
    form.username.data = current_user.username
    form.bio.data = current_user.bio
    form.age.data = current_user.age  # Prefill age
    form.work.data = current_user.work  # Prefill work

    return render_template('update_profile.html', form=form)




@views.route('/settings', methods=['GET', 'POST'])
def settings():
    form = SettingsForm()
    
    # Simulating a user data fetch for the sake of this example
    user_data = get_user_data()  # This function would get the current user data from the database
    
    if form.validate_on_submit():
        # Process form data (e.g., change email, password, etc.)
        updated_data = {
            'email': form.email.data,
            'password': form.password.data,
            'language': form.language.data,
            'notifications': form.notifications.data
        }
        update_user_data(updated_data)  # This function would update user data in the database
        return redirect(url_for('settings'))  # Reload settings page after update

    return render_template('settings.html', form=form, user_data=user_data)

@views.route('/reels')
@login_required
def reels():
    # Query posts with video media type
    reels = Post.query.filter_by(media_type='video').order_by(Post.timestamp.desc()).all()
    return render_template('reels.html', reels=reels)


@views.route('/reels/<int:reel_id>/like', methods=['POST'])
@login_required
def like_reel(reel_id):
    reel = Post.query.get_or_404(reel_id)
    
    # Check if user has already liked the reel
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=reel_id).first()
    
    if existing_like:
        # Unlike the reel
        db.session.delete(existing_like)
        db.session.commit()
        return jsonify({'liked': False, 'likes_count': len(reel.likes)})
    else:
        # Like the reel
        new_like = Like(user_id=current_user.id, post_id=reel_id)
        db.session.add(new_like)
        db.session.commit()
        return jsonify({'liked': True, 'likes_count': len(reel.likes)})


@views.route('/create_reel', methods=['GET', 'POST'])
@login_required
def create_reel():
    form = ReelForm()
    if form.validate_on_submit():
        # Handle video upload
        video = form.video.data
        filename = secure_filename(video.filename)
        video_path = os.path.join(UPLOAD_FOLDER, filename)
        video.save(video_path)

        # Create a new reel post
        new_reel = Post(
            content=form.description.data or '',
            media_path=video_path,
            media_type='video',
            user_id=current_user.id,
            category=Category.INFO,  # Default category for reels
            views=0
        )
        
        db.session.add(new_reel)
        db.session.commit()

        flash('Reel created successfully!', 'success')
        return redirect(url_for('views.reels'))

    return render_template('create_reel.html', form=form)


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@views.route('/update_profile_picture', methods=['POST'])
@login_required
def update_profile_picture():
    if 'profile_picture' not in request.files:
        flash('No file part')
        return redirect(url_for('views.profile'))

    file = request.files['profile_picture']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('views.profile'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join('app/static/profile_pics', filename)
        file.save(file_path)

        current_user.profile_picture = filename  # Assuming you have this field
        db.session.commit()
        flash('Profile picture updated!')
    else:
        flash('Invalid file format.')

    return redirect(url_for('views.profile'))




