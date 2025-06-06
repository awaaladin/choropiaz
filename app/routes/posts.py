from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify, session, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import or_, and_, desc
import os
import json
import requests
import logging
from PIL import Image

from app.extensions import db, mail
from app.models.models import Post, Comment, Like, User, Category, Notification, Transaction, Profile, BankAccount
from app.forms import PostForm, ProfileForm, RegisterForm, SettingsForm, UpdateProfileForm, ReelForm, LoginForm, SendMoneyForm
from app.utils import merge_video_audio

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Constants ---
UPLOAD_FOLDER = os.path.join('static', 'uploads')
PROFILE_UPLOAD_FOLDER = os.path.join('static', 'profile_pics')
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "webm"}
PROFILE_PIC_FOLDER = 'static/profile_pics'
DJANGO_WEB_APP_BASE_URL = os.environ.get('DJANGO_WEB_APP_BASE_URL', 'http://localhost:8000')

# Blueprints
views = Blueprint('views', __name__)
notifications = Blueprint('notifications', __name__)

# --- Helper Functions for Django API ---
FLASK_APP_DJANGO_API_TOKEN = None

def get_django_admin_api_token():
    global FLASK_APP_DJANGO_API_TOKEN
    if FLASK_APP_DJANGO_API_TOKEN:
        return FLASK_APP_DJANGO_API_TOKEN

    django_admin_username = current_app.config.get("DJANGO_ADMIN_USERNAME")
    django_admin_password = current_app.config.get("DJANGO_ADMIN_PASSWORD")

    if not django_admin_username or not django_admin_password:
        logger.error("Django admin credentials not configured.")
        return None

    try:
        response = requests.post(f"{DJANGO_WEB_APP_BASE_URL}/api/login/", json={
            "username": django_admin_username,
            "password": django_admin_password
        })
        response.raise_for_status()
        FLASK_APP_DJANGO_API_TOKEN = response.json().get("token")
        return FLASK_APP_DJANGO_API_TOKEN
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching Django admin API token: {e}")
        return None

def _make_django_api_request(endpoint, method='GET', data=None, use_user_token=True):
    url = f"{DJANGO_WEB_APP_BASE_URL}/api/{endpoint}"
    headers = {'Content-Type': 'application/json'}

    auth_token = None
    if use_user_token and current_user.is_authenticated:
        auth_token = session.get('django_api_token')
        if not auth_token:
            auth_token = get_django_admin_api_token()
    else:
        auth_token = get_django_admin_api_token()

    if auth_token:
        headers['Authorization'] = f"Token {auth_token}"
    else:
        logger.error(f"No Django API token available for request to {endpoint}.")
        flash("Could not perform banking operation: authentication with banking service failed.", "danger")
        return None

    try:
        if method == 'POST':
            response = requests.post(url, headers=headers, json=data)
        elif method == 'PUT':
            response = requests.put(url, headers=headers, json=data)
        elif method == 'DELETE':
            response = requests.delete(url, headers=headers)
        else:
            response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP Error making request to Django API ({url}): {e}")
        if hasattr(e, 'response') and e.response is not None:
            error_detail = e.response.json().get('detail', e.response.text)
            logger.error(f"Django API response error: {error_detail}")
            flash(f"Banking API Error: {error_detail}", 'error')
            if "Authentication credentials were not provided." in error_detail or "Invalid token" in error_detail:
                if use_user_token and 'django_api_token' in session:
                    session.pop('django_api_token')
                    flash("Your banking session expired. Please log in again to the banking app.", "warning")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"General Request Error making request to Django API ({url}): {e}")
        flash('Could not connect to the banking service. Please try again later.', 'error')
        return None

# --- General Helper Functions ---
def allowed_file(filename, allowed_extensions):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_media_file(file_obj, upload_folder):
    if not file_obj or file_obj.filename == '':
        return None
    random_hex = os.urandom(8).hex()
    _, f_ext = os.path.splitext(file_obj.filename)
    filename = random_hex + f_ext
    full_upload_dir = os.path.join(os.getcwd(), upload_folder)
    os.makedirs(full_upload_dir, exist_ok=True)
    file_path = os.path.join(full_upload_dir, filename)
    file_obj.save(file_path)
    return os.path.join(upload_folder, filename).replace('\\', '/')

def save_picture(form_picture):
    random_hex = os.urandom(8).hex()
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_filename = random_hex + f_ext
    abs_path = os.path.join(os.getcwd(), PROFILE_PIC_FOLDER)
    os.makedirs(abs_path, exist_ok=True)
    picture_path = os.path.join(abs_path, picture_filename)
    output_size = (250, 250)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_filename

def get_bank_dashboard_data():
    if not current_user.is_authenticated:
        return None
    return _make_django_api_request('accounts/dashboard/', use_user_token=True)

def load_feed_data(sort_by='recent', search_query=None):
    posts_query = Post.query

    if search_query:
        search_pattern = f'%{search_query}%'
        posts_query = posts_query.join(User).filter(
            or_(
                Post.caption.ilike(search_pattern),
                User.username.ilike(search_pattern),
                Post.category.ilike(search_pattern)
            )
        )

    if sort_by == 'likes':
        posts_query = posts_query.outerjoin(Like).group_by(Post.id).order_by(desc(db.func.count(Like.id)))
    elif sort_by == 'trending':
        one_day_ago = datetime.utcnow() - timedelta(days=1)
        posts_query = posts_query.outerjoin(Like).filter(Like.timestamp >= one_day_ago).group_by(Post.id).order_by(desc(db.func.count(Like.id)))
    else:
        posts_query = posts_query.order_by(desc(Post.timestamp))

    posts = posts_query.all()
    return posts

def get_top_weekly_posts():
    one_week_ago = datetime.utcnow() - timedelta(weeks=1)
    recent_posts = Post.query.filter(Post.timestamp >= one_week_ago).all()

    top_weekly_posts = {}
    for cat_enum in Category:
        category_posts = [p for p in recent_posts if p.category == cat_enum.value]
        category_posts.sort(key=lambda p: len(p.likes), reverse=True)
        top_weekly_posts[cat_enum.value] = category_posts[:3]
    return top_weekly_posts

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
        link = url_for('views.view_post', post_id=post_id)
    elif type == 'follow' and sender_id:
        sender_user = User.query.get(sender_id)
        if sender_user:
            link = url_for('views.user_profile', username=sender_user.username) # Changed to views.user_profile

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
    return notification

def process_mentions(content, post_id, sender_id):
    if not content:
        return
    words = content.split()
    for word in words:
        if word.startswith('@'):
            username = word[1:].strip(".,!?;:")
            mentioned_user = User.query.filter_by(username=username).first()
            if mentioned_user and mentioned_user.id != sender_id:
                send_notification(
                    recipient_id=mentioned_user.id,
                    type='mention',
                    sender_id=sender_id,
                    post_id=post_id,
                    preview_text=content[:100] + '...' if len(content) > 100 else content
                )

# --- VIEWS/ROUTES ---

@views.route('/')
@views.route('/home')
@views.route('/feed')
@login_required
def home():
    form = PostForm()
    sort_by = request.args.get('sort', 'recent')
    search_query = request.args.get('search')
    
    posts = load_feed_data(sort_by, search_query)
    bank_data = get_bank_dashboard_data()
    top_weekly_posts = get_top_weekly_posts()

    return render_template(
        'feed.html',
        posts=posts,
        form=form,
        sort=sort_by,
        bank_data=bank_data,
        DJANGO_WEB_APP_BASE_URL=DJANGO_WEB_APP_BASE_URL,
        search_query=search_query,
        top_weekly_posts=top_weekly_posts,
        STRIPE_PUBLIC_KEY=current_app.config.get("STRIPE_PUBLIC_KEY", "")
    )

@views.route('/create_post', methods=['POST'])
@login_required
def create_post():
    form = PostForm()

    if form.validate_on_submit():
        caption = form.content.data
        category_str = form.category.data
        media_file = form.media.data
        media_type_from_form = form.media_type.data
        price = form.price.data if form.is_purchasable.data else None
        is_purchasable = form.is_purchasable.data

        media_path = None
        media_type = None

        if media_file:
            if media_type_from_form == 'image' and allowed_file(media_file.filename, ALLOWED_IMAGE_EXTENSIONS):
                media_path = save_media_file(media_file, UPLOAD_FOLDER)
                media_type = 'image'
            elif media_type_from_form == 'video' and allowed_file(media_file.filename, ALLOWED_VIDEO_EXTENSIONS):
                media_path = save_media_file(media_file, UPLOAD_FOLDER)
                media_type = 'video'
            else:
                flash('Invalid media file type or extension!', 'danger')
                return redirect(url_for('views.home'))
        
        try:
            category_enum = Category[category_str.upper()]
        except KeyError:
            flash('Invalid category selected.', 'danger')
            return redirect(url_for('views.home'))

        new_post = Post(
            user_id=current_user.id,
            caption=caption,
            category=category_enum.value,
            media_path=media_path,
            media_type=media_type,
            price=price,
            is_purchasable=is_purchasable,
            timestamp=datetime.utcnow()
        )
        try:
            db.session.add(new_post)
            db.session.commit()
            process_mentions(caption, new_post.id, current_user.id)
            flash('Post created successfully! 🎉', 'success')
            return jsonify({'success': True, 'message': 'Post created successfully!'})
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating post: {e}")
            flash(f'An error occurred while creating the post: {e}', 'error')
            return jsonify({'success': False, 'message': 'An error occurred while creating the post.'}), 500
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", 'danger')
        return jsonify({'success': False, 'message': 'Form validation failed.'}), 400


@views.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()

    if like:
        db.session.delete(like)
        liked = False
        message = f"{current_user.username} unliked your post."
    else:
        new_like = Like(user_id=current_user.id, post_id=post_id)
        db.session.add(new_like)
        liked = True
        message = f"{current_user.username} liked your post."
        
        if current_user.id != post.user_id:
            send_notification(
                recipient_id=post.user_id,
                type='like',
                sender_id=current_user.id,
                post_id=post.id,
                preview_text=post.caption[:50]
            )

    db.session.commit()
    return jsonify({'liked': liked, 'likes_count': len(post.likes)})


@views.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def comment_post(post_id):
    post = Post.query.get_or_404(post_id)
    comment_content = request.form.get('comment_content')

    if not comment_content:
        flash('Comment cannot be empty.', 'danger')
        return redirect(url_for('views.home'))

    new_comment = Comment(
        content=comment_content,
        user_id=current_user.id,
        post_id=post_id
    )
    db.session.add(new_comment)
    
    if current_user.id != post.user_id:
        send_notification(
            recipient_id=post.user_id,
            type='comment',
            sender_id=current_user.id,
            post_id=post.id,
            preview_text=comment_content[:50]
        )
    process_mentions(comment_content, post_id, current_user.id)

    db.session.commit()
    flash('Comment added successfully!', 'success')
    return redirect(url_for('views.home'))

@views.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        flash('You do not have permission to delete this post.', 'danger')
        return redirect(url_for('views.home'))

    if post.media_path:
        full_path = os.path.join(os.getcwd(), 'static', post.media_path)
        if os.path.exists(full_path):
            os.remove(full_path)
        else:
            logger.warning(f"Media file not found for deletion: {full_path}")

    db.session.delete(post)
    db.session.commit()
    flash('Post deleted successfully.', 'success')
    return redirect(url_for('views.home'))


@views.route('/reels')
@login_required
def reels():
    reel_form = ReelForm()
    reels = Post.query.filter(Post.media_type == 'video').order_by(desc(Post.timestamp)).all()
    
    return render_template('reels.html', reels=reels, reel_form=reel_form)


@views.route('/create_reel', methods=['POST'])
@login_required
def create_reel():
    reel_form = ReelForm()
    if reel_form.validate_on_submit():
        video_file = reel_form.video.data
        audio_file = reel_form.audio.data

        video_path_relative = save_media_file(video_file, UPLOAD_FOLDER)
        final_media_path_relative = video_path_relative

        if audio_file and allowed_file(audio_file.filename, {'mp3', 'wav', 'aac', 'ogg'}):
            audio_path_relative = save_media_file(audio_file, UPLOAD_FOLDER)
            
            video_abs = os.path.join(os.getcwd(), 'static', video_path_relative)
            audio_abs = os.path.join(os.getcwd(), 'static', audio_path_relative)
            output_filename = f"merged_{os.path.splitext(os.path.basename(video_path_relative))[0]}.mp4"
            output_abs = os.path.join(os.getcwd(), 'static', UPLOAD_FOLDER, output_filename)
            
            merged = merge_video_audio(video_abs, audio_abs, output_abs)
            
            if merged:
                final_media_path_relative = os.path.join(UPLOAD_FOLDER, output_filename).replace('\\', '/')
                os.remove(video_abs)
                os.remove(audio_abs)
                flash('Reel created and audio merged successfully!', 'success')
            else:
                flash('Failed to merge audio with video. Using original video.', 'warning')
        else:
            flash('Reel created successfully!', 'success')

        new_reel_post = Post(
            caption=reel_form.description.data or "New Reel",
            user_id=current_user.id,
            media_path=final_media_path_relative,
            media_type='video',
            category=Category.INFO.value, # Default for reels
            timestamp=datetime.utcnow()
        )
        db.session.add(new_reel_post)
        db.session.commit()
        return redirect(url_for('views.reels'))
    else:
        for field, errors in reel_form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(reel_form, field).label.text}: {error}", 'danger')
        flash('Error creating reel. Please check your inputs.', 'danger')
    return redirect(url_for('views.reels'))


@views.route('/search_users', methods=['GET'])
@login_required
def search_users():
    query = request.args.get('query', '').strip()
    users = []
    if query:
        users = User.query.filter(
            or_(
                User.username.ilike(f'%{query}%'),
                User.bio.ilike(f'%{query}%')
            )
        ).all()
    return render_template('search_users.html', users=users, query=query)


@views.route('/view_post/<int:post_id>')
@login_required
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    post.views = (post.views or 0) + 1
    db.session.commit()
    return render_template('view_post.html', post=post)


@views.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    form = SettingsForm(obj=current_user)
    if form.validate_on_submit():
        current_user.email = form.email.data
        current_user.language = form.language.data
        current_user.notification_preferences = json.dumps({'email': form.notifications.data == 'yes'}) # Update preferences
        db.session.commit()
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('views.settings'))
    return render_template('settings.html', form=form)

@views.route('/send_money', methods=['POST'])
@login_required
def send_money():
    form = SendMoneyForm()
    if form.validate_on_submit():
        recipient_username = form.recipient_username.data
        amount = form.amount.data
        description = form.description.data

        recipient = User.query.filter_by(username=recipient_username).first()
        if not recipient:
            flash('Recipient user not found.', 'danger')
            return redirect(url_for('views.home')) # Redirect to home or a specific error page

        if current_user.id == recipient.id:
            flash('You cannot send money to yourself.', 'danger')
            return redirect(url_for('views.home'))

        # Assuming the Django API handles the actual transaction logic and balance deduction/addition
        django_payload = {
            'sender_id': current_user.id, # Flask user ID
            'recipient_id': recipient.id, # Flask recipient user ID
            'amount': float(amount),
            'description': description
        }
        
        response = _make_django_api_request('banking/transfer/', method='POST', data=django_payload, use_user_token=True)

        if response and response.get('status') == 'success':
            # Create a local transaction record for auditing/display
            transaction = Transaction(
                user_id=current_user.id,
                amount=amount,
                transaction_type='transfer_sent',
                description=f"Sent to {recipient_username}: {description}",
                timestamp=datetime.utcnow(),
                status='completed'
            )
            db.session.add(transaction)

            recipient_transaction = Transaction(
                user_id=recipient.id,
                amount=amount,
                transaction_type='transfer_received',
                description=f"Received from {current_user.username}: {description}",
                timestamp=datetime.utcnow(),
                status='completed'
            )
            db.session.add(recipient_transaction)
            db.session.commit() # Commit both transactions

            flash('Money sent successfully!', 'success')
        elif response:
            flash(f"Failed to send money: {response.get('message', 'Unknown error from banking service')}", 'danger')
        else:
            flash('Failed to send money due to a banking service error.', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f"Error in {getattr(form, field).label.text}: {error}", 'danger')
    return redirect(url_for('views.home'))

# --- Profile Views (moved here as per request) ---

@views.route('/profile')
@login_required
def profile():
    # This route will display the current user's profile
    form = ProfileForm() # You might use this for profile picture upload directly on the profile page
    
    # Check if a profile already exists, create one if not (from models.py modification)
    if not current_user.profile:
        new_profile = Profile(user_id=current_user.id)
        db.session.add(new_profile)
        db.session.commit()
        db.session.refresh(current_user) # Refresh the current_user object to reflect the new profile relationship

    # Fetch posts specific to the current user
    posts = Post.query.filter_by(user_id=current_user.id).order_by(Post.timestamp.desc()).all()
    
    # is_following should always be False for the current_user's own profile
    is_following = False

    return render_template('profile.html', user=current_user, posts=posts, is_following=is_following, form=form)


@views.route('/user/<username>')
@login_required
def user_profile(username):
    # This route will display other users' profiles
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(user_id=user.id).order_by(Post.timestamp.desc()).all()
    
    is_following = False
    if current_user.is_authenticated and hasattr(current_user, 'is_following'):
        is_following = current_user.is_following(user)

    return render_template('profile.html', user=user, posts=posts, is_following=is_following)


@views.route('/update_profile', methods=['GET', 'POST'])
@login_required
def update_profile():
    form = UpdateProfileForm()
    # Ensure profile exists for the current user
    if not current_user.profile:
        new_profile = Profile(user_id=current_user.id)
        db.session.add(new_profile)
        db.session.commit()
        db.session.refresh(current_user) # Refresh to load the new profile

    if request.method == 'POST' and form.validate_on_submit():
        if form.profile_picture.data:
            picture_filename = save_picture(form.profile_picture.data)
            current_user.profile_picture = picture_filename
        
        current_user.username = form.username.data
        current_user.bio = form.bio.data
        current_user.age = form.age.data
        current_user.work = form.work.data
        
        # Update profile specific fields if they exist in the form and profile model
        if hasattr(form, 'phone_number') and form.phone_number.data is not None and hasattr(current_user.profile, 'phone_number'):
            current_user.profile.phone_number = form.phone_number.data
        if hasattr(form, 'address') and form.address.data is not None and hasattr(current_user.profile, 'address'):
            current_user.profile.address = form.address.data
        if hasattr(form, 'date_of_birth') and form.date_of_birth.data is not None and hasattr(current_user.profile, 'date_of_birth'):
            current_user.profile.date_of_birth = form.date_of_birth.data

        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('views.profile'))

    # Populate form fields for GET request
    form.username.data = current_user.username
    form.bio.data = current_user.bio
    form.age.data = current_user.age
    form.work.data = current_user.work
    
    if current_user.profile:
        if hasattr(form, 'phone_number') and hasattr(current_user.profile, 'phone_number'):
            form.phone_number.data = current_user.profile.phone_number
        if hasattr(form, 'address') and hasattr(current_user.profile, 'address'):
            form.address.data = current_user.profile.address
        if hasattr(form, 'date_of_birth') and hasattr(current_user.profile, 'date_of_birth'):
            form.date_of_birth.data = current_user.profile.date_of_birth

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


@views.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow_user(user_id):
    user_to_follow = User.query.get_or_404(user_id)
    
    if user_to_follow == current_user:
        flash("You cannot follow yourself.", "danger")
        return jsonify({'following': current_user.is_following(user_to_follow)})

    if current_user.is_following(user_to_follow):
        current_user.unfollow(user_to_follow)
        is_following = False
        flash(f"You unfollowed {user_to_follow.username}.", "info")
    else:
        current_user.follow(user_to_follow)
        is_following = True
        send_notification(
            recipient_id=user_to_follow.id,
            type='follow',
            sender_id=current_user.id
        )
        flash(f"You are now following {user_to_follow.username}.", "success")
        
    db.session.commit()
    return jsonify({'following': is_following})


# --- Notifications Blueprint Routes ---

@notifications.route('/notifications')
@login_required
def view_notifications():
    user_notifications = Notification.query.filter_by(recipient_id=current_user.id).order_by(desc(Notification.timestamp)).all()
    for notification in user_notifications:
        if not notification.is_read: # Use is_read from model
            notification.is_read = True
    db.session.commit()
    return render_template('notifications.html', notifications=user_notifications)

@notifications.route('/api/notifications/count', methods=['GET'])
@login_required
def get_notification_count():
    unread_count = Notification.query.filter_by(recipient_id=current_user.id, is_read=False).count()
    return jsonify({'count': unread_count})

@notifications.route('/api/notifications/clear', methods=['POST'])
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