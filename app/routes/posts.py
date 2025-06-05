from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, session
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, desc
import os
import json
import requests
# Assuming 'db' and 'mail' are imported and configured in app.extensions
from app.extensions import db, mail 
from app.models.models import Post, Comment, Like, User, Category, Notification
from app.forms import PostForm, ProfileForm, RegisterForm, SettingsForm, UpdateProfileForm, ReelForm
from PIL import Image
from app.utils import merge_video_audio # Assuming merge_video_audio is in app.utils

# --- Constants ---
UPLOAD_FOLDER = os.path.join('static', 'uploads')
PROFILE_UPLOAD_FOLDER = os.path.join('static', 'profile_pics')
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "webm"}
PROFILE_PIC_FOLDER = 'static/profile_pics'
# Changed to Django API base URL
DJANGO_API_BASE_URL = "https://gax-2.onrender.com/api" 

# Ensure directories exist at project root, not inside app/
def ensure_directories_exist():
    app_root = os.getcwd()
    directories = [
        os.path.join(app_root, UPLOAD_FOLDER),
        os.path.join(app_root, PROFILE_UPLOAD_FOLDER)
    ]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)

ensure_directories_exist()

views = Blueprint('views', __name__)
notifications = Blueprint('notifications', __name__) # Define the notifications blueprint

# --- Helper Functions ---

def allowed_file(filename, allowed_extensions):
    """Checks if a filename has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_media_file(file_obj):
    """Saves an uploaded media file to the UPLOAD_FOLDER."""
    if not file_obj or file_obj.filename == '':
        return None
    random_hex = os.urandom(8).hex()
    _, f_ext = os.path.splitext(file_obj.filename)
    filename = random_hex + f_ext
    uploads_dir = os.path.join(os.getcwd(), UPLOAD_FOLDER)
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    file_path = os.path.join(uploads_dir, filename)
    file_obj.save(file_path)
    return f"uploads/{filename}"

def save_picture(form_picture):
    """Saves an uploaded profile picture, resizing it."""
    random_hex = os.urandom(8).hex()
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_filename = random_hex + f_ext
    abs_path = os.path.join(os.getcwd(), PROFILE_PIC_FOLDER)
    if not os.path.exists(abs_path):
        os.makedirs(abs_path)
    picture_path = os.path.join(abs_path, picture_filename)
    output_size = (250, 250)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_filename

def get_top_weekly_posts():
    """Fetches top posts from the last week, categorized."""
    one_week_ago = datetime.now() - timedelta(weeks=1)
    top_posts = Post.query.filter(Post.timestamp >= one_week_ago).order_by(Post.views.desc()).limit(10).all()
    posts_by_category = {'Goods': [], 'Services': [], 'Info': []}
    for post in top_posts:
        category_name = post.category.value if post.category else '' # Use .value for Enum
        if category_name == Category.GOODS.value:
            posts_by_category['Goods'].append(post)
        elif category_name == Category.SERVICES.value:
            posts_by_category['Services'].append(post)
        elif category_name == Category.INFO.value:
            posts_by_category['Info'].append(post)
    return posts_by_category

def get_trending_posts():
    """Fetches trending posts (by likes) from the last week."""
    one_week_ago = datetime.now() - timedelta(weeks=1)
    return Post.query.filter(Post.timestamp >= one_week_ago).order_by(Post.likes.desc()).limit(10).all()

# Helper function to make requests to the Django API
def _make_django_api_request(endpoint, method='GET', data=None):
    """
    Makes an authenticated API request to the Django banking application.
    Retrieves the authentication token from the Flask session.
    """
    url = f"{DJANGO_API_BASE_URL}/{endpoint}"
    headers = {'Content-Type': 'application/json'}
    
    # Get the Django token from the Flask session
    django_token = session.get('django_token')
    if django_token:
        headers['Authorization'] = f"Token {django_token}"
    else:
        print("Warning: No Django token found in session. API request might fail if authentication is required.")
        flash("Banking features require you to be logged into the banking service.", "warning")
        return None # Return None immediately if no token and it's a secured endpoint

    try:
        if method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=data)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers)
        else: # Default to GET
            response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error making request to Django API ({url}): {e}")
        if hasattr(e, 'response') and e.response is not None:
            error_detail = e.response.json().get('detail', e.response.text)
            print(f"Django API response error: {error_detail}")
            flash(f"Banking API Error: {error_detail}", 'error')
            # If authentication fails, clear the token from session
            if "Authentication credentials were not provided." in error_detail or "Invalid token" in error_detail:
                session.pop('django_token', None)
                flash("Your banking session expired. Please log in again to the banking app.", "warning")
        return None
    except requests.exceptions.RequestException as e:
        print(f"General Request Error making request to Django API ({url}): {e}")
        flash('Could not connect to the banking service. Please try again later.', 'error')
        return None

def get_bank_dashboard_data():
    """Fetches dashboard data from Django API for the current Flask user."""
    # Ensure current_user is authenticated before attempting to fetch bank data
    if not current_user.is_authenticated:
        return None
    return _make_django_api_request('dashboard/')

def load_feed_data():
    """Loads data for the main feed, including posts and trending content."""
    form = PostForm()
    search_query = request.args.get('search')
    sort_by = request.args.get('sort', 'recent')
    posts_query = Post.query

    if search_query:
        # Search by caption or category
        posts_query = posts_query.filter(
            or_(
                Post.caption.ilike(f'%{search_query}%'),
                Post.category.ilike(f'%{search_query}%')
            )
        )

    if sort_by == 'recent':
        posts_query = posts_query.order_by(Post.timestamp.desc())
    elif sort_by == 'likes':
        # Order by likes count, requires a join or subquery
        posts_query = posts_query.outerjoin(Like).group_by(Post).order_by(db.func.count(Like.id).desc(), Post.timestamp.desc())
    elif sort_by == 'trending':
        # Placeholder for trending: could be combination of likes, comments, recency
        posts_query = posts_query.order_by(Post.timestamp.desc()) # Default to recent for now

    posts = posts_query.all()
    
    top_weekly_posts = get_top_weekly_posts()
    return form, posts, search_query, top_weekly_posts

# --- Notification Helper Functions ---

NOTIFICATION_TYPES = {
    'like': 'liked your post',
    'comment': 'commented on your post',
    'follow': 'started following you',
    'mention': 'mentioned you in a post',
    'system': 'system notification',
    'welcome': 'welcome notification'
}

def send_notification(recipient_id, type, sender_id=None, post_id=None, comment_id=None, preview_text=None):
    """Sends a notification to a user and optionally an email."""
    if sender_id == recipient_id:
        return None # Don't send notification to self
    
    message = NOTIFICATION_TYPES.get(type, '')
    link = None
    if post_id:
        link = f"/post/{post_id}"
    elif type == 'follow' and sender_id:
        sender_user = User.query.get(sender_id)
        if sender_user:
            link = f"/user/{sender_user.username}"
    
    notification = Notification(
        recipient_id=recipient_id,
        sender_id=sender_id,
        type=type,
        message=message,
        post_id=post_id,
        comment_id=comment_id,
        preview_text=preview_text,
        link=link,
        timestamp=datetime.utcnow(),
        is_read=False,
        is_seen=False
    )
    db.session.add(notification)
    db.session.commit()
    
    recipient = User.query.get(recipient_id)
    # Assuming 'notification_preferences' is a JSON field or similar on User model
    if recipient and getattr(recipient, 'notification_preferences', {}).get('email', False):
        send_email_notification(notification)
    return notification

def send_email_notification(notification):
    """Sends an email notification (requires Flask-Mail setup)."""
    recipient = User.query.get(notification.recipient_id)
    if not recipient or not recipient.email:
        return
    
    sender = User.query.get(notification.sender_id) if notification.sender_id else None
    sender_name = sender.username if sender else 'System'
    
    subject = f"New notification from YourApp"
    body = f"Hello {recipient.username},\n\n"
    if notification.type == 'like':
        post = Post.query.get(notification.post_id)
        body += f"{sender_name} liked your post: '{post.caption[:50]}...'\n" # Use post.caption
    elif notification.type == 'comment':
        post = Post.query.get(notification.post_id)
        body += f"{sender_name} commented on your post: '{post.caption[:50]}...'\n" # Use post.caption
    elif notification.type == 'follow':
        body += f"{sender_name} started following you.\n"
    elif notification.type == 'mention':
        body += f"{sender_name} mentioned you in a post: '{notification.preview_text}'\n"
    else:
        body += f"{notification.message}\n"
    
    body += f"\nCheck it out: http://yourdomain.com{notification.link}" if notification.link else ""
    body += "\n\nBest regards,\nYourApp Team"
    
    try:
        msg = Message(
            subject=subject,
            sender='noreply@yourdomain.com', # Replace with your actual sender email
            recipients=[recipient.email]
        )
        msg.body = body
        mail.send(msg)
    except Exception as e:
        print(f"Failed to send email notification: {str(e)}")

def process_mentions(content, post_id, sender_id):
    """Processes content to find mentions (@username) and send notifications."""
    if not content:
        return
    words = content.split()
    for word in words:
        if word.startswith('@'):
            username = word[1:].strip(".,!?;:") # Clean username from punctuation
            mentioned_user = User.query.filter_by(username=username).first()
            if mentioned_user:
                send_notification(
                    recipient_id=mentioned_user.id,
                    type='mention',
                    sender_id=sender_id,
                    post_id=post_id,
                    preview_text=content[:100] + '...' if len(content) > 100 else content
                )

def notification_exists(recipient_id, type, sender_id=None, post_id=None, timeframe_seconds=60):
    """Checks if a similar notification exists within a timeframe to prevent spam."""
    time_threshold = datetime.utcnow() - timedelta(seconds=timeframe_seconds)
    query_filters = [
        Notification.recipient_id == recipient_id,
        Notification.type == type,
        Notification.timestamp > time_threshold
    ]
    if sender_id:
        query_filters.append(Notification.sender_id == sender_id)
    if post_id:
        query_filters.append(Notification.post_id == post_id)
    return Notification.query.filter(and_(*query_filters)).first() is not None


# --- VIEWS/ROUTES ---

@views.route('/')
@login_required
def home():
    form, posts, search_query, top_weekly_posts = load_feed_data()
    bank_data = get_bank_dashboard_data() # No need to pass current_user.id explicitly here
    
    return render_template(
        'feed.html',
        posts=posts,
        search_query=search_query,
        top_weekly_posts=top_weekly_posts,
        form=form,
        bank_data=bank_data
    )

@views.route('/feed', methods=['GET'])
@login_required
def feed():
    # This route can just redirect to home or serve the same content as home
    # For simplicity, let's redirect to home
    return redirect(url_for('views.home'))

@views.route('/create_post', methods=['POST'])
@login_required
def create_post():
    caption = request.form.get('caption')
    category_str = request.form.get('category', '').upper()
    image_file = request.files.get('image')
    video_file = request.files.get('video')

    if not caption:
        flash('Caption is required!', 'danger')
        return redirect(url_for('views.home'))

    media_path = None
    media_type = None

    try:
        category_enum = Category[category_str] 
    except KeyError:
        flash('Invalid category selected.', 'danger')
        return redirect(url_for('views.home'))

    if image_file and image_file.filename != '':
        if allowed_file(image_file.filename, ALLOWED_IMAGE_EXTENSIONS):
            media_path = save_media_file(image_file)
            media_type = 'image'
        else:
            flash('Invalid image file type!', 'danger')
            return redirect(url_for('views.home'))
    elif video_file and video_file.filename != '':
        if allowed_file(video_file.filename, ALLOWED_VIDEO_EXTENSIONS):
            media_path = save_media_file(video_file)
            media_type = 'video'
        else:
            flash('Invalid video file type!', 'danger')
            return redirect(url_for('views.home'))

    new_post = Post(user_id=current_user.id, caption=caption, category=category_enum, media_path=media_path, media_type=media_type, timestamp=datetime.utcnow())
    try:
        db.session.add(new_post)
        db.session.commit()
        process_mentions(caption, new_post.id, current_user.id) # Call process_mentions
        flash('Post created successfully!', 'success')
        return jsonify({'success': True, 'message': 'Post created successfully!'})
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred while creating the post: {e}', 'error')
        return jsonify({'success': False, 'message': 'An error occurred while creating the post.'}), 500


@views.route('/post/<int:post_id>')
@login_required
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('view_post.html', post=post)

@views.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)

    if post.user_id != current_user.id:
        abort(403) 

    password = request.form.get('password')
    if not check_password_hash(current_user.password_hash, password): 
        flash('Incorrect password.', 'danger')
        return redirect(url_for('views.home')) 

    # Delete associated media file
    # Ensure correct path for deletion
    if post.media_path:
        full_media_path = os.path.join(os.getcwd(), 'static', post.media_path)
        if os.path.exists(full_media_path):
            try:
                os.remove(full_media_path)
            except Exception as e:
                print(f"Error deleting media file {full_media_path}: {e}")
                flash(f"Error deleting media file: {e}", 'warning')

    db.session.delete(post)
    db.session.commit()
    flash('Post deleted successfully!', 'success')
    return redirect(url_for('views.home'))

@views.route('/like/<int:post_id>', methods=['POST','GET']) # Added GET for direct testing if needed
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if like:
        db.session.delete(like)
        db.session.commit()
        return jsonify({'liked': False, 'likes_count': len(post.likes)})
    else:
        new_like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(new_like)
        db.session.commit()
        # Send notification to post owner
        if post.user_id != current_user.id:
            send_notification(
                recipient_id=post.user_id,
                type='like',
                sender_id=current_user.id,
                post_id=post.id
            )
        return jsonify({'liked': True, 'likes_count': len(post.likes)})

@views.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow_user(user_id):
    user = User.query.get_or_404(user_id)
    is_following = False
    if user != current_user:
        if current_user.is_following(user):
            current_user.unfollow(user)
            is_following = False
        else:
            current_user.follow(user)
            is_following = True
            # Send notification to followed user
            send_notification(
                recipient_id=user.id,
                type='follow',
                sender_id=current_user.id
            )
        db.session.commit()
    return jsonify({'following': is_following})

@views.route('/comment/<int:post_id>', methods=['POST','GET']) # Added GET for direct testing if needed
@login_required
def comment_post(post_id):
    content = request.form.get('comment_content')
    if content:
        new_comment = Comment(content=content, user_id=current_user.id, post_id=post_id, timestamp=datetime.utcnow())
        db.session.add(new_comment)
        db.session.commit()
        # Send notification to post owner
        post = Post.query.get(post_id)
        if post and post.user_id != current_user.id:
            send_notification(
                recipient_id=post.user_id,
                type='comment',
                sender_id=current_user.id,
                post_id=post.id
            )
        # Process mentions in comment
        process_mentions(content, post_id, current_user.id)
        flash('Comment added!', 'success')
    return redirect(url_for('views.home')) # Redirect to home after comment

@views.route('/reels/<int:reel_id>/like', methods=['POST','GET'])
@login_required
def like_reel(reel_id):
    reel = Post.query.get_or_404(reel_id)
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=reel_id).first()
    if existing_like:
        db.session.delete(existing_like)
        db.session.commit()
        return jsonify({'liked': False, 'likes_count': len(reel.likes)})
    else:
        new_like = Like(user_id=current_user.id, post_id=reel_id)
        db.session.add(new_like)
        db.session.commit()
        # Send notification to reel owner
        if reel.user_id != current_user.id:
            send_notification(
                recipient_id=reel.user_id,
                type='like',
                sender_id=current_user.id,
                post_id=reel.id
            )
        return jsonify({'liked': True, 'likes_count': len(reel.likes)})

@views.route('/create_reel', methods=['GET', 'POST'])
@login_required
def create_reel():
    form = ReelForm()
    if form.validate_on_submit():
        video = form.video.data
        audio = getattr(form, 'audio', None)
        audio_file = audio.data if audio else None
        if video and allowed_file(video.filename, ALLOWED_VIDEO_EXTENSIONS): # Use allowed_file with extensions
            media_path = save_media_file(video)
            final_media_path = media_path
            # If audio is uploaded, merge it with video
            if audio_file and audio_file.filename:
                audio_path = save_media_file(audio_file)
                # Compose output path
                base, ext = os.path.splitext(media_path)
                output_path = base + '_with_audio' + ext
                video_abs = os.path.join(os.getcwd(), 'static', media_path)
                audio_abs = os.path.join(os.getcwd(), 'static', audio_path)
                output_abs = os.path.join(os.getcwd(), 'static', output_path)
                merged = merge_video_audio(video_abs, audio_abs, output_abs)
                if merged:
                    final_media_path = output_path
                else:
                    flash('Failed to merge audio with video. Using original video.', 'warning')
            new_reel = Post(
                caption=form.description.data or '', 
                media_path=final_media_path,
                media_type='video',
                user_id=current_user.id,
                category=Category.INFO, 
                views=0,
                timestamp=datetime.utcnow()
            )
            db.session.add(new_reel)
            db.session.commit()
            flash('Reel created successfully!', 'success')
            return redirect(url_for('views.reels'))
        else:
            flash('Please upload a valid video file', 'error')
    return render_template('create_reel.html', form=form)

@views.route('/reels')
@login_required
def reels():
    reels = Post.query.filter_by(media_type='video').order_by(Post.timestamp.desc()).all()
    return render_template('reels.html', reels=reels)

# --- PROFILE & SETTINGS ROUTES ---

@views.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    if form.validate_on_submit():
        if form.profile_picture.data:
            picture_filename = save_picture(form.profile_picture.data)
            current_user.profile_picture = picture_filename
            db.session.commit()
            flash('Profile updated!', 'success')
        return redirect(url_for('views.profile'))
    return render_template('profile.html', form=form, user=current_user)

@views.route('/update_profile', methods=['GET', 'POST'])
@login_required
def update_profile():
    form = UpdateProfileForm()
    if request.method == 'POST' and form.validate_on_submit():
        if form.profile_picture.data:
            picture_filename = save_picture(form.profile_picture.data)
            current_user.profile_picture = picture_filename
        current_user.username = form.username.data
        current_user.bio = form.bio.data
        current_user.age = form.age.data
        current_user.work = form.work.data
        db.session.commit()
        return redirect(url_for('views.profile'))
    form.username.data = current_user.username
    form.bio.data = current_user.bio
    form.age.data = current_user.age
    form.work.data = current_user.work
    return render_template('update_profile.html', form=form)

@views.route('/update_profile_picture', methods=['POST'])
@login_required
def update_profile_picture():
    if 'profile_picture' not in request.files:
        flash('No file part', 'error')
        return redirect(url_for('views.profile'))
    file = request.files['profile_picture']
    if file.filename == '':
        flash('No selected file', 'error')
        return redirect(url_for('views.profile'))
    if file and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS): # Use allowed_file with extensions
        try:
            filename = secure_filename(file.filename)
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            profile_pic_dir = os.path.join(os.getcwd(), PROFILE_PIC_FOLDER)
            if not os.path.exists(profile_pic_dir):
                os.makedirs(profile_pic_dir)
            file_path = os.path.join(profile_pic_dir, unique_filename)
            file.save(file_path)
            current_user.profile_picture = unique_filename
            db.session.commit()
            flash('Profile picture updated successfully!', 'success')
        except Exception as e:
            flash(f'Error updating profile picture: {str(e)}', 'error')
    else:
        flash('Invalid file format. Please use JPG, PNG, or GIF files.', 'error')
    return redirect(url_for('views.profile'))

@views.route('/user/<username>')
@login_required
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.timestamp.desc()).all()
    is_following = False
    if current_user.is_authenticated:
        is_following = current_user.is_following(user) if hasattr(current_user, 'is_following') else False
    return render_template('profile.html', user=user, posts=posts, is_following=is_following)

@views.route('/search_users')
@login_required
def search_users():
    query = request.args.get('q', '').strip()
    users = User.query.filter(User.username.ilike(f'%{query}%')).all() if query else []
    return render_template('search_users.html', users=users, query=query)

@views.route('/settings', methods=['GET', 'POST'])
def settings():
    form = SettingsForm()
    user_data = {
        'email': current_user.email if current_user.is_authenticated else '',
        'password': '',
        'language': 'en',
        'notifications': True,
        'profile_picture': current_user.profile_picture if current_user.is_authenticated else 'default.jpg'
    }
    if form.validate_on_submit():
        # Implement your update logic here
        flash('Settings updated!', 'success')
        return redirect(url_for('views.settings'))
    return render_template('settings.html', form=form, user_data=user_data)

# --- NOTIFICATIONS ROUTES ---

@notifications.route('/notifications')
@login_required
def view_notifications():
    all_notifications = Notification.query.filter_by(
        recipient_id=current_user.id
    ).order_by(desc(Notification.timestamp)).all()
    mentions_notifications = [n for n in all_notifications if n.type == 'mention']
    activity_notifications = [n for n in all_notifications if n.type in ['like', 'comment', 'follow']]
    for notification in all_notifications:
        if not notification.is_seen:
            notification.is_seen = True
    db.session.commit()
    return render_template('notification.html',
                          notifications=all_notifications,
                          mentions_notifications=mentions_notifications,
                          activity_notifications=activity_notifications)

@notifications.route('/mark_notification_read/<int:notification_id>', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    notification = Notification.query.get_or_404(notification_id)
    if notification.recipient_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    notification.is_read = True
    db.session.commit()
    return jsonify({'success': True})

@notifications.route('/mark_all_read', methods=['POST'])
@login_required
def mark_all_read():
    notifications_q = Notification.query.filter_by(
        recipient_id=current_user.id,
        is_read=False
    ).all()
    for notification in notifications_q:
        notification.is_read = True
    db.session.commit()
    return jsonify({'success': True})

@notifications.route('/notification_count')
@login_required
def get_notification_count():
    count = Notification.query.filter_by(
        recipient_id=current_user.id,
        is_read=False
    ).count()
    return jsonify({'count': count})

@notifications.route('/notification_preferences', methods=['GET', 'POST'])
@login_required
def notification_preferences():
    if request.method == 'POST':
        prefs = {
            'app': 'app_notifications' in request.form,
            'email': 'email_notifications' in request.form,
            'likes': 'like_notifications' in request.form,
            'comments': 'comment_notifications' in request.form,
            'follows': 'follow_notifications' in request.form,
            'mentions': 'mention_notifications' in request.form
        }
        current_user.notification_preferences = json.dumps(prefs)
        db.session.commit()
        return redirect(url_for('notifications.notification_preferences'))
    prefs = get_user_notification_preferences(current_user.id)
    return render_template('notification_preferences.html', preferences=prefs)

@notifications.route('/clear_notifications', methods=['POST'])
@login_required
def clear_notifications():
    Notification.query.filter_by(recipient_id=current_user.id).delete()
    db.session.commit()
    return jsonify({'success': True})

@notifications.route('/api/notifications/poll', methods=['GET'])
@login_required
def poll_notifications():
    since = request.args.get('since')
    if since:
        try:
            since_time = datetime.fromisoformat(since)
        except ValueError:
            since_time = datetime.utcnow() - timedelta(minutes=5)
    else:
        since_time = datetime.utcnow() - timedelta(minutes=5)
    new_notifications = Notification.query.filter(
        Notification.recipient_id == current_user.id,
        Notification.timestamp > since_time
    ).order_by(desc(Notification.timestamp)).all()
    result = []
    for notification in new_notifications:
        sender = User.query.get(notification.sender_id) if notification.sender_id else None
        result.append({
            'id': notification.id,
            'sender_id': notification.sender_id,
            'sender_name': sender.username if sender else 'System',
            'sender_avatar': url_for('static', filename=f'profile_pics/{sender.profile_picture}') if sender else None,
            'type': notification.type,
            'message': notification.message,
            'preview_text': notification.preview_text,
            'link': notification.link,
            'timestamp': notification.timestamp.isoformat(),
            'is_read': notification.is_read
        })
    return jsonify(result)



@views.route('/send_money', methods=['GET', 'POST'])
@login_required
def send_money():
    form = SendMoneyForm()
    if form.validate_on_submit():
        recipient_username = form.recipient_username.data
        amount = form.amount.data
        description = form.description.data

        recipient = User.query.filter_by(username=recipient_username).first()

        if not recipient:
            flash(f"User '{recipient_username}' not found.", 'danger')
            return render_template('send_money.html', form=form)

        if recipient.id == current_user.id:
            flash("You cannot send money to yourself.", 'danger')
            return render_template('send_money.html', form=form)

        # Ensure current_user has a profile and bank account linked
        if not current_user.profile or not current_user.bank_account:
            flash("Your account is not fully set up for transactions. Please contact support.", 'danger')
            return render_template('send_money.html', form=form)

        # Check sender's balance
        if current_user.profile.balance < amount:
            flash("Insufficient balance to complete the transfer.", 'danger')
            return render_template('send_money.html', form=form)

        try:
            # Implement the logic for sending money using your Django API
            token = get_django_api_token()
            if not token:
                flash("Could not authenticate with the banking system. Please try again later.", "danger")
                return render_template('send_money.html', form=form)

            headers = {"Authorization": f"Token {token}"}
            payload = {
                "sender_username": current_user.username,
                "recipient_username": recipient_username,
                "amount": str(amount), # Convert Decimal to string for JSON
                "details": description
            }
            transfer_response = requests.post(
                f"{DJANGO_API_BASE_URL}/transfer/",
                headers=headers,
                json=payload
            )
            transfer_response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)

            # Assuming the Django API handles the actual balance update and transaction logging
            # You might want to update the Flask user's balance from the Django response if available
            # Or refetch the user's profile to reflect the new balance.

            flash(f"Successfully sent ₦{amount} to {recipient_username}!", 'success')
            return redirect(url_for('views.home'))

        except requests.exceptions.RequestException as e:
            error_message = "An error occurred during transfer."
            if transfer_response and transfer_response.content:
                try:
                    error_details = transfer_response.json()
                    error_message = error_details.get("detail", error_message)
                    if isinstance(error_details, dict): # Check if error_details is a dictionary
                        for key, value in error_details.items():
                            if isinstance(value, list) and len(value) > 0:
                                error_message += f" {key}: {value[0]}"
                            else:
                                error_message += f" {key}: {value}"
                except json.JSONDecodeError:
                    error_message = f"An unknown error occurred: {transfer_response.text}"
            flash(f"Transfer failed: {error_message}", 'danger')
            return render_template('send_money.html', form=form)
        except Exception as e:
            flash(f"An unexpected error occurred: {e}", 'danger')
            return render_template('send_money.html', form=form)

    return render_template('send_money.html', form=form)

@views.route('/post/<int:post_id>')
@login_required
def post_detail(post_id):
    post = Post.query.get_or_404(post_id)
    return render_template('post_detail.html', post=post)