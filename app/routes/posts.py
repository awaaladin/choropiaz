from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, session, current_app # Added current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, desc
import os
import json
import requests
import logging # Import logging
# Remove this line from Flask app:
# from rest_framework.authtoken.views import obtain_auth_token

# Assuming 'db' and 'mail' are imported and configured in app.extensions
from app.extensions import db, mail
# Ensure all models are imported
from app.models.models import Post, Comment, Like, User, Category, Notification, Transaction, Profile, BankAccount
# Ensure all forms are imported
from app.forms import PostForm, ProfileForm, RegisterForm, SettingsForm, UpdateProfileForm, ReelForm, LoginForm, SendMoneyForm # Make sure SendMoneyForm is imported
from PIL import Image
from app.utils import merge_video_audio # Assuming merge_video_audio is in app.utils

# Configure logging for this blueprint
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Constants ---
UPLOAD_FOLDER = os.path.join('static', 'uploads')
PROFILE_UPLOAD_FOLDER = os.path.join('static', 'profile_pics')
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "webm"}
PROFILE_PIC_FOLDER = 'static/profile_pics'
# Changed to Django API base URL
DJANGO_API_BASE_URL = "https://gax-2.onrender.com/api"
DJANGO_AUTH_ENDPOINT = f"{DJANGO_API_BASE_URL}/login/"
DJANGO_DASHBOARD_ENDPOINT = f"{DJANGO_API_BASE_URL}/dashboard/"
DJANGO_WEB_APP_BASE_URL = "https://gax-2.onrender.com/accounts" # Base URL for Django web pages

# This token is for Flask app's *internal* use to call Django API,
# e.g., for system-level operations or if a user-specific token isn't available for a general request.
# It should be acquired via Django admin login.
FLASK_APP_DJANGO_API_TOKEN = None

# Ensure directories exist at project root, not inside app/
def ensure_directories_exist():
    app_root = os.getcwd()
    directories = [
        os.path.join(app_root, UPLOAD_FOLDER),
        os.path.join(app_root, PROFILE_UPLOAD_FOLDER)
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

# Call this function once when the application starts
ensure_directories_exist()

# --- Blueprints ---
views = Blueprint('views', __name__)
notifications = Blueprint('notifications', __name__) # Assuming notifications is a separate blueprint

def _make_django_api_request(endpoint, method='GET', data=None):
    """Makes an authenticated request to the Django API"""
    url = f"{DJANGO_API_BASE_URL}/{endpoint.lstrip('/')}"
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Authorization': 'Token e42238e2afb35366accc2b053fec9651fdd238d5'  # Use the actual token
    }
    
    logger.info(f"Making {method} request to: {url}")
    try:
        # Test connection first
        test_response = requests.head(
            DJANGO_API_BASE_URL,
            timeout=5,
            verify=True
        )
        logger.info(f"Connection test status: {test_response.status_code}")
        
        # Make the actual request
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=data,
            timeout=10,
            verify=True
        )
        
        logger.info(f"API Response Status: {response.status_code}")
        
        # Handle different status codes
        if response.status_code == 401:
            logger.error("Authentication failed")
            flash("Banking service authentication failed", "error")
            return None
        elif response.status_code == 404:
            logger.error(f"Endpoint not found: {url}")
            flash("Banking service endpoint not available", "error")
            return None
            
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        flash("Unable to connect to banking service", "error")
        return None

def check_api_health():
    """Checks if the Django API is accessible"""
    try:
        response = _make_django_api_request('dashboard/')
        return response is not None
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return False


def get_bank_dashboard_data():
    """Fetches dashboard data from Django API for the current Flask user."""
    if not current_user.is_authenticated:
        return None
    return _make_django_api_request('dashboard/', use_user_token=True)


# --- Helper Functions (moved to top for clarity and proper scope) ---

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
    os.makedirs(uploads_dir, exist_ok=True) # Ensure directory exists
    file_path = os.path.join(uploads_dir, filename)
    file_obj.save(file_path)
    return f"uploads/{filename}"

def save_picture(form_picture):
    """Saves an uploaded profile picture, resizing it."""
    random_hex = os.urandom(8).hex()
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_filename = random_hex + f_ext
    abs_path = os.path.join(os.getcwd(), PROFILE_PIC_FOLDER)
    os.makedirs(abs_path, exist_ok=True) # Ensure directory exists
    picture_path = os.path.join(abs_path, picture_filename)
    output_size = (250, 250)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_filename

def get_top_weekly_posts():
    """Fetches top posts from the last week, categorized."""
    one_week_ago = datetime.utcnow() - timedelta(weeks=1) # Use utcnow() for consistency
    top_posts = Post.query.filter(Post.timestamp >= one_week_ago).order_by(Post.views.desc()).limit(10).all()
    posts_by_category = {'Goods': [], 'Services': [], 'Info': []}
    for post in top_posts:
        category_name = post.category.value if hasattr(post, 'category') and post.category else ''
        if category_name == Category.GOODS.value:
            posts_by_category['Goods'].append(post)
        elif category_name == Category.SERVICES.value:
            posts_by_category['Services'].append(post)
        elif category_name == Category.INFO.value:
            posts_by_category['Info'].append(post)
    return posts_by_category

def get_trending_posts():
    """Fetches trending posts (by likes) from the last week."""
    one_week_ago = datetime.utcnow() - timedelta(weeks=1) # Use utcnow()
    return Post.query.filter(Post.timestamp >= one_week_ago).order_by(Post.likes.desc()).limit(10).all()

def load_feed_data():
    """Loads data for the main feed, including posts and trending content."""
    form = PostForm()
    search_query = request.args.get('search')
    sort_by = request.args.get('sort', 'recent')
    posts_query = Post.query

    if search_query:
        posts_query = posts_query.filter(
            or_(
                Post.caption.ilike(f'%{search_query}%'),
                Post.category.ilike(f'%{search_query}%')
            )
        )

    if sort_by == 'recent':
        posts_query = posts_query.order_by(Post.timestamp.desc())
    elif sort_by == 'likes':
        posts_query = posts_query.outerjoin(Like).group_by(Post).order_by(db.func.count(Like.id).desc(), Post.timestamp.desc())
    elif sort_by == 'trending':
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
    if sender_id == recipient_id:
        return None
    
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
    if recipient and hasattr(recipient, 'notification_preferences') and isinstance(recipient.notification_preferences, str):
        try:
            prefs = json.loads(recipient.notification_preferences)
            if prefs.get('email', False):
                send_email_notification(notification)
        except json.JSONDecodeError:
            logger.warning(f"Could not decode notification_preferences for user {recipient_id}")
    elif recipient and hasattr(recipient, 'notification_preferences') and isinstance(recipient.notification_preferences, dict):
        if recipient.notification_preferences.get('email', False):
            send_email_notification(notification)
    return notification

def send_email_notification(notification):
    recipient = User.query.get(notification.recipient_id)
    if not recipient or not recipient.email:
        return
    
    sender = User.query.get(notification.sender_id) if notification.sender_id else None
    sender_name = sender.username if sender else 'System'
    
    subject = f"New notification from YourApp"
    body = f"Hello {recipient.username},\n\n"
    if notification.type == 'like':
        post = Post.query.get(notification.post_id)
        if post: body += f"{sender_name} liked your post: '{post.caption[:50]}...'\n"
    elif notification.type == 'comment':
        post = Post.query.get(notification.post_id)
        if post: body += f"{sender_name} commented on your post: '{post.caption[:50]}...'\n"
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
        logger.error(f"Failed to send email notification: {str(e)}")

def process_mentions(content, post_id, sender_id):
    if not content:
        return
    words = content.split()
    for word in words:
        if word.startswith('@'):
            username = word[1:].strip(".,!?;:")
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

def get_user_notification_preferences(user_id):
    user = User.query.get(user_id)
    if not user:
        return {}
    default_prefs = {
        'app': True, 'email': False, 'likes': True, 'comments': True, 'follows': True, 'mentions': True
    }
    if hasattr(user, 'notification_preferences') and user.notification_preferences:
        if isinstance(user.notification_preferences, str):
            try:
                user_prefs = json.loads(user.notification_preferences)
            except json.JSONDecodeError:
                user_prefs = {}
        else:
            user_prefs = user.notification_preferences
        default_prefs.update(user_prefs)
    return default_prefs


def check_api_health():
    """
    Checks if the Django API is accessible and responding with detailed logging.
    Returns: bool
    """
    # Try the profile endpoint as it's guaranteed to exist
    health_endpoints = [
        '/profile/',  # Use ProfileView endpoint
        '/dashboard/',  # Use DashboardView endpoint
    ]
    
    logger.info(f"Attempting to connect to base URL: {DJANGO_API_BASE_URL}")
    
    try:
        # First test basic connectivity to the base domain
        test_response = requests.head(
            "https://gax-2.onrender.com",
            timeout=5,
            verify=True,
            allow_redirects=True
        )
        logger.info(f"Basic connectivity test status code: {test_response.status_code}")
        
        # Try each possible endpoint
        for endpoint in health_endpoints:
            url = f"{DJANGO_API_BASE_URL}{endpoint}"
            logger.info(f"Trying API endpoint: {url}")
            
            try:
                response = requests.get(
                    url,
                    timeout=5,
                    verify=True,
                    headers={
                        'Accept': 'application/json',
                        'User-Agent': 'CHORORPIA/1.0',
                        'Authorization': f'Token {get_django_admin_api_token()}'
                    }
                )
                
                logger.info(f"Response from {endpoint}: Status={response.status_code}")
                
                if response.status_code in [200, 401, 403]:  # Accept auth-related responses as valid
                    logger.info("API endpoint responding")
                    return True
            except requests.exceptions.RequestException as e:
                logger.warning(f"Failed to connect to {endpoint}: {str(e)}")
                continue
        
        logger.error("No working API endpoint found")
        return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to base URL: {str(e)}")
        return False

# Helper to get Django admin API token

def get_django_admin_api_token():
    # Try to get from Flask config first
    token = current_app.config.get('DJANGO_API_TOKEN')
    if token:
        return token
    # Fallback to environment variable
    return os.environ.get('DJANGO_API_TOKEN', 'e42238e2afb35366accc2b053fec9651fdd238d5')


@views.route('/')
@views.route('/home')
@views.route('/feed')
@login_required
def home():
    form, posts, search_query, top_weekly_posts = load_feed_data()
    
    # Check API health before attempting to get bank data
    api_available = check_api_health()
    bank_data = None
    
    if api_available:
        try:
            bank_data = get_bank_dashboard_data()
        except Exception as e:
            logger.error(f"Failed to fetch bank data: {str(e)}")
            flash("Banking features are temporarily unavailable", "info")
    
    return render_template(
        'feed.html',
        posts=posts,
        search_query=search_query,
        top_weekly_posts=top_weekly_posts,
        form=form,
        bank_data=bank_data,
        banking_available=(bank_data is not None)
    )


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
        process_mentions(caption, new_post.id, current_user.id)
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
    if not check_password_hash(current_user.password, password): # Assuming 'password' attribute stores hash
        flash('Incorrect password.', 'danger')
        return redirect(url_for('views.home'))

    if post.media_path:
        full_media_path = os.path.join(os.getcwd(), 'static', post.media_path)
        if os.path.exists(full_media_path):
            try:
                os.remove(full_media_path)
            except Exception as e:
                logger.error(f"Error deleting media file {full_media_path}: {e}")
                flash(f"Error deleting media file: {e}", 'warning')

    db.session.delete(post)
    db.session.commit()
    flash('Post deleted successfully!', 'success')
    return redirect(url_for('views.home'))

@views.route('/like/<int:post_id>', methods=['POST','GET'])
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
            send_notification(
                recipient_id=user.id,
                type='follow',
                sender_id=current_user.id
            )
        db.session.commit()
    return jsonify({'following': is_following})

@views.route('/comment/<int:post_id>', methods=['POST','GET'])
@login_required
def comment_post(post_id):
    content = request.form.get('comment_content')
    if content:
        new_comment = Comment(content=content, user_id=current_user.id, post_id=post_id, timestamp=datetime.utcnow())
        db.session.add(new_comment)
        db.session.commit()
        post = Post.query.get(post_id)
        if post and post.user_id != current_user.id:
            send_notification(
                recipient_id=post.user_id,
                type='comment',
                sender_id=current_user.id,
                post_id=post.id
            )
        process_mentions(content, post_id, current_user.id)
        flash('Comment added!', 'success')
    return redirect(url_for('views.home'))

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
        if video and allowed_file(video.filename, ALLOWED_VIDEO_EXTENSIONS):
            media_path = save_media_file(video)
            final_media_path = media_path
            if audio_file and audio_file.filename:
                audio_path = save_media_file(audio_file)
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
                category=Category.INFO, # Assuming INFO is a valid Category enum member
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
    if file and allowed_file(file.filename, ALLOWED_IMAGE_EXTENSIONS):
        try:
            filename = secure_filename(file.filename)
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            profile_pic_dir = os.path.join(os.getcwd(), PROFILE_PIC_FOLDER)
            os.makedirs(profile_pic_dir, exist_ok=True)
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
    if current_user.is_authenticated and hasattr(current_user, 'is_following'):
        is_following = current_user.is_following(user)
    return render_template('profile.html', user=user, posts=posts, is_following=is_following)

@views.route('/search_users')
@login_required
def search_users():
    query = request.args.get('q', '').strip()
    users = User.query.filter(User.username.ilike(f'%{query}%')).all() if query else []
    return render_template('search_users.html', users=users, query=query)

@views.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    form = SettingsForm()
    user_data = {
        'email': current_user.email,
        'password': '',
        'language': 'en',
        'notifications': True,
        'profile_picture': current_user.profile_picture
    }
    if form.validate_on_submit():
        flash('Settings updated!', 'success')
        return redirect(url_for('views.settings'))
    return render_template('settings.html', form=form, user_data=user_data)


# --- NOTIFICATIONS ROUTES (part of 'notifications' blueprint) ---

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
            'timestamp': notification.timestamp.isoformat()
        })
    return jsonify(result)


@views.route('/send-money', methods=['GET', 'POST'])
@login_required
def send_money():
    form = SendMoneyForm()
    if form.validate_on_submit():
        recipient_username = form.recipient_username.data
        amount = form.amount.data
        
        # Add your money transfer logic here
        try:
            # Implement your money transfer functionality
            flash('Money sent successfully!', 'success')
            return redirect(url_for('views.home'))
        except Exception as e:
            flash(f'Error sending money: {str(e)}', 'error')
            
    return render_template('send_money.html', form=form)

