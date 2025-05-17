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

views = Blueprint('views', __name__)

# --- Constants ---
UPLOAD_FOLDER = os.path.join("static", "uploads")
PROFILE_UPLOAD_FOLDER = os.path.join("static", "profile_pics")
ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "mov", "avi", "webm"}
PROFILE_PIC_FOLDER = 'static/profile_pics'

def ensure_directories_exist():
    app_root = os.getcwd()
    directories = [
        os.path.join(app_root, 'app', UPLOAD_FOLDER),
        os.path.join(app_root, 'app', PROFILE_UPLOAD_FOLDER)
    ]
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
ensure_directories_exist()

def allowed_file(filename):
    if not filename:
        return False
    ext = filename.rsplit(".", 1)[-1].lower() if '.' in filename else ''
    return ext in ALLOWED_IMAGE_EXTENSIONS.union(ALLOWED_VIDEO_EXTENSIONS)

def save_media_file(file_obj):
    if not file_obj or file_obj.filename == '':
        return None
    random_hex = os.urandom(8).hex()
    _, f_ext = os.path.splitext(file_obj.filename)
    filename = random_hex + f_ext
    app_root = os.getcwd()
    uploads_dir = os.path.join(app_root, 'app', UPLOAD_FOLDER)
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    file_path = os.path.join(uploads_dir, filename)
    file_obj.save(file_path)
    return os.path.join(UPLOAD_FOLDER, filename)

def save_picture(form_picture):
    random_hex = os.urandom(8).hex()
    _, f_ext = os.path.splitext(form_picture.filename)
    picture_filename = random_hex + f_ext
    abs_path = os.path.join(os.getcwd(), 'app', PROFILE_PIC_FOLDER)
    if not os.path.exists(abs_path):
        os.makedirs(abs_path)
    picture_path = os.path.join(abs_path, picture_filename)
    output_size = (250, 250)
    i = Image.open(form_picture)
    i.thumbnail(output_size)
    i.save(picture_path)
    return picture_filename

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
    sort_by = request.args.get('sort', 'recent')
    posts_query = Post.query

    # Search filter
    if search_query:
        try:
            category_enum = Category[search_query.upper()]
            posts_query = posts_query.filter(Post.category == category_enum)
        except KeyError:
            posts_query = posts_query.filter(Post.content.ilike(f'%{search_query}%'))

    # Sorting
    if sort_by == 'likes':
        posts_query = posts_query.order_by(Post.likes.desc())
    elif sort_by == 'trending':
        posts = get_trending_posts()
    else:
        posts_query = posts_query.order_by(Post.timestamp.desc())

    if sort_by != 'trending':
        posts = posts_query.all()

    top_weekly_posts = get_top_weekly_posts()
    return form, posts, search_query, top_weekly_posts

# --- FEED ROUTES ---

@views.route('/', methods=['GET'])
@login_required
def home():
    form, posts, search_query, top_weekly_posts = load_feed_data()
    return render_template(
        'feed.html',
        posts=posts,
        search_query=search_query,
        top_weekly_posts=top_weekly_posts,
        form=form
    )

@views.route('/feed', methods=['GET'])
@login_required
def feed():
    form, posts, search_query, top_weekly_posts = load_feed_data()
    return render_template(
        'feed.html',
        posts=posts,
        search_query=search_query,
        top_weekly_posts=top_weekly_posts,
        form=form
    )

@views.route('/create_post', methods=['POST'])
@login_required
def create_post():
    caption = request.form.get('caption', '')
    category_str = request.form.get('category', '').upper()
    try:
        category_enum = Category[category_str]
    except (KeyError, AttributeError):
        return jsonify({'success': False, 'message': 'Invalid category'}), 400

    media_path = None
    media_type = None

    if 'image' in request.files and request.files['image'].filename:
        file = request.files['image']
        if allowed_file(file.filename):
            media_path = save_media_file(file)
            media_type = 'image'
    elif 'video' in request.files and request.files['video'].filename:
        file = request.files['video']
        if allowed_file(file.filename):
            media_path = save_media_file(file)
            media_type = 'video'

    new_post = Post(
        content=caption,
        category=category_enum,
        media_path=media_path,
        media_type=media_type,
        user_id=current_user.id,
        views=0,
        timestamp=datetime.utcnow()
    )
    try:
        db.session.add(new_post)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Post created!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@views.route('/like/<int:post_id>', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    like = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if like:
        db.session.delete(like)
        db.session.commit()
        return jsonify({'liked': False, 'likes_count': len(post.likes)})
    else:
        db.session.add(Like(user_id=current_user.id, post_id=post_id))
        db.session.commit()
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
        db.session.commit()
    return jsonify({'following': is_following})

@views.route('/comment/<int:post_id>', methods=['POST'])
@login_required
def comment_post(post_id):
    content = request.form.get('comment_content')
    if content:
        db.session.add(Comment(content=content, user_id=current_user.id, post_id=post_id))
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
    if post.media_path:
        try:
            file_path = os.path.join(os.getcwd(), 'app', post.media_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting media file: {e}")
    db.session.delete(post)
    db.session.commit()
    flash("Post deleted.", "success")
    return redirect(url_for('views.feed'))

# --- REELS ROUTES ---

@views.route('/reels/<int:reel_id>/like', methods=['POST'])
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
        return jsonify({'liked': True, 'likes_count': len(reel.likes)})

@views.route('/create_reel', methods=['GET', 'POST'])
@login_required
def create_reel():
    form = ReelForm()
    if form.validate_on_submit():
        video = form.video.data
        if video and allowed_file(video.filename):
            media_path = save_media_file(video)
            new_reel = Post(
                content=form.description.data or '',
                media_path=media_path,
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
            picture_filename = secure_filename(form.profile_picture.data.filename)
            form.profile_picture.data.save(os.path.join(PROFILE_UPLOAD_FOLDER, picture_filename))
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
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            unique_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
            profile_pic_dir = os.path.join(os.getcwd(), 'app', 'static', 'profile_pics')
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