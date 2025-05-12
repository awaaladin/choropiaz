from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, FloatField, SelectField
from wtforms.validators import InputRequired, Email, DataRequired, Length, Optional
from flask_wtf.file import FileField, FileAllowed,FileRequired
from app.models.enums import Category
from wtforms import StringField, IntegerField
from wtforms import   BooleanField
from wtforms.fields import EmailField  




class LoginForm(FlaskForm):
    email = StringField('Email', validators=[InputRequired(), Email()])
    password = PasswordField('Password', validators=[InputRequired()])

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired()])
    email = StringField('Email', validators=[InputRequired(), Email()])
    password = PasswordField('Password', validators=[InputRequired()])
    profile_picture = FileField('Profile Picture', validators=[FileAllowed(['jpg', 'png', 'jpeg', 'gif'])])
    submit = SubmitField('Register')


class PostForm(FlaskForm):
    content = TextAreaField('Content', validators=[DataRequired()])
    
    # Import Category here to avoid circular import
    from app.models.models import Category  # Import inside the class to avoid circular import

    category = SelectField('Category', choices=[(category.name, category.value) for category in Category], validators=[DataRequired()])
    
    media = FileField('Upload Media', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'mp4', 'mov', 'avi', 'webm'])])
    media_type = SelectField('Media Type', choices=[('image', 'Image'), ('video', 'Video')], validators=[DataRequired()])
    submit = SubmitField('Post')
    price = FloatField('Price (optional)', validators=[Optional()])
    is_purchasable = BooleanField('Available for Purchase')



class ProfileForm(FlaskForm):
    profile_picture = FileField('Profile Picture', validators=[FileAllowed(['jpg', 'png', 'jpeg', 'gif'])])
    submit = SubmitField('Update')


class UpdateProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=2, max=20)])
    
    bio = StringField('Bio', validators=[Length(max=150)])
    
    age = IntegerField('Age', validators=[DataRequired()])
    
    work = StringField('Work', validators=[Length(max=100)])
    
    profile_picture = FileField('Update Profile Picture', validators=[
        FileRequired(), 
        FileAllowed(['jpg', 'png', 'jpeg'], 'Images only!')
    ])
    
    submit = SubmitField('Update Profile')


class SettingsForm(FlaskForm):
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=8)])
    language = SelectField('Language', choices=[('en', 'English'), ('es', 'Spanish'), ('fr', 'French'), ('de', 'German')])
    notifications = SelectField('Email Notifications', choices=[('yes', 'Yes'), ('no', 'No')], default='yes')
    submit = SubmitField('Update Settings')

class ReelForm(FlaskForm):
    video = FileField('Upload Reel', validators=[
        FileRequired(), 
        FileAllowed(['mp4', 'mov', 'avi', 'webm'], 'Video files only!')
    ])
    description = TextAreaField('Reel Description', validators=[
        Optional(), 
        Length(max=300)
    ])
    submit = SubmitField('Post Reel')



