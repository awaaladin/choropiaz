# app/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, FloatField, SelectField, IntegerField
from wtforms.validators import InputRequired, Email, DataRequired, Length, Optional, EqualTo
from flask_wtf.file import FileField, FileAllowed, FileRequired
from app.models.enums import Category
from wtforms.fields import EmailField
from wtforms import BooleanField


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember me')  # Add this line
    submit = SubmitField('Sign In')


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=2, max=20)])
    email = StringField('Email', validators=[InputRequired(), Email()])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8)])
    # Added password2 field for confirmation
    password2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    # Added fields to match Django API
    phone_number = StringField('Phone Number', validators=[InputRequired(), Length(min=10, max=15)])
    address = StringField('Address', validators=[Optional(), Length(max=255)])
    full_name = StringField('Full Name', validators=[Optional(), Length(max=100)])
    age = IntegerField('Age', validators=[Optional()]) # Age is optional in Django model, so Optional() here
    submit = SubmitField('Register')


class PostForm(FlaskForm):
    content = TextAreaField('Content', validators=[DataRequired()])

    # Import Category here to avoid circular import
    from app.models.models import Category  # Import inside the class to avoid circular import

    category = SelectField('Category', choices=[(category.name, category.value) for category in Category], validators=[DataRequired()])

    media = FileField('Upload Media', validators=[FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'mp4', 'mov', 'avi', 'webm'], 'Images or Videos only!')]) # Updated allowed extensions
    submit = SubmitField('Post')


class ProfileForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=2, max=20)])
    email = EmailField('Email', validators=[InputRequired(), Email()])
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=300)])
    age = IntegerField('Age', validators=[Optional()])
    work = StringField('Work', validators=[Optional(), Length(max=150)])
    full_name = StringField('Full Name', validators=[Optional(), Length(max=100)])
    # Assuming Category is an Enum in app.models.enums or models.py
    category = SelectField('Category', choices=[(tag.name, tag.value) for tag in Category], validators=[Optional()])

    submit = SubmitField('Update Profile')

class UpdateProfileForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=2, max=20)])
    email = EmailField('Email', validators=[InputRequired(), Email()])
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=300)])
    age = IntegerField('Age', validators=[Optional()])
    work = StringField('Work', validators=[Optional(), Length(max=150)])
    full_name = StringField('Full Name', validators=[Optional(), Length(max=100)])
    # Assuming Category is an Enum in app.models.enums or models.py
    category = SelectField('Category', choices=[(tag.name, tag.value) for tag in Category], validators=[Optional()])
    
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
    audio = FileField('Add Music (optional)', validators=[
        FileAllowed(['mp3', 'wav', 'aac', 'ogg'], 'Audio files only!')
    ])
    description = TextAreaField('Reel Description', validators=[
        Optional(),
        Length(max=300)
    ])
    submit = SubmitField('Post Reel')

class SendMoneyForm(FlaskForm):
    recipient_username = StringField('Recipient Username', validators=[DataRequired()])
    amount = FloatField('Amount', validators=[DataRequired()])
    # Optional: Add a validator for positive amount if needed
    # Optional: Add a field for a transaction message/note
    submit = SubmitField('Send Money')

class BankAccountForm(FlaskForm):
    bank_name = StringField('Bank Name', validators=[InputRequired(), Length(max=100)])
    account_number = StringField('Account Number', validators=[InputRequired(), Length(min=10, max=10)])
    account_name = StringField('Account Name', validators=[InputRequired(), Length(max=100)])
    submit = SubmitField('Add Bank Account')