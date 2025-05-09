from flask import Blueprint, render_template, redirect, url_for, request, flash, current_app, session
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, login_required, logout_user, current_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
import uuid
from datetime import datetime
from .models import Users
from . import db, mail

auth = Blueprint('auth', __name__)

def get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

@auth.route('/login')
def login():
    return render_template('login.html')

@auth.route('/login', methods=['POST'])
def login_post():
    # login code goes here
    email = request.form.get('email')
    password = request.form.get('password')
    remember = True if request.form.get('remember') else False

    user = Users.query.filter_by(email=email).first()

    # check if the user actually exists
    # take the user-supplied password, hash it, and compare it to the hashed password in the database
    if not user or not check_password_hash(user.password, password):
        flash('Please check your login details and try again.', "warning")
        return redirect(url_for('auth.login')) # if the user doesn't exist or password is wrong, reload the page

    if not user.is_verified:
        flash('You need to confirm your email before logging in.', 'warning')
        return redirect(url_for('auth.resend_confirmation'))

    # if the above check passes, then we know the user has the right credentials
    login_user(user, remember=remember)
    next_page = request.args.get('next')
    return redirect(next_page) if next_page else redirect(url_for('main.index'))

@auth.route('/resend_confirmation', methods=['GET', 'POST'])
def resend_confirmation():
    if request.method == 'POST':
        email = request.form.get('email')
        user = Users.query.filter_by(email=email).first()

        if user and not user.is_verified:
            token = get_serializer().dumps(email, salt=current_app.config['EMAIL_CONFIRMATION_SALT'])
            confirm_url = url_for('auth.confirm_email', token=token, _external=True)

            msg = Message('Resend Confirmation Email', sender=current_app.config['MAIL_USERNAME'], recipients=[email])
            msg.body = f'Please click the link to confirm your email: {confirm_url}'
            mail.send(msg)

            flash('A new confirmation email has been sent. Please check your inbox.', 'info')
        else:
            flash('If the email exists and is not confirmed, a new confirmation link has been sent.', 'info')

        return redirect(url_for('auth.login'))

    return render_template('resend_confirmation.html')

@auth.route('/signup')
def signup():
    return render_template("signup.html")

@auth.route('/signup', methods=['POST'])
def signup_post():
    # Define user adds and validation
    email = request.form.get('email')
    name = request.form.get('name')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    rdate = datetime.now()
    
    if password != confirm_password:
        flash('Passwords do not match!')
        return redirect(url_for('auth.signup'))

    user = Users.query.filter_by(email=email).first() # if this returns a user, then the email already exists in database

    if user: # if a user is found, we want to redirect back to signup page so user can try again
        flash('Email address already exists', "warning")
        return redirect(url_for('auth.signup'))

    # create a new user with the form data. Hash the password so the plaintext version isn't saved.
    new_user = Users(email=email, name=name, password=generate_password_hash(password, method='pbkdf2:sha256'), is_verified=False, rdate=rdate)

    # add the new user to the database
    db.session.add(new_user)
    db.session.commit()
    
    # Add e-mail confirmation
    token = get_serializer().dumps(email, salt=current_app.config['EMAIL_CONFIRMATION_SALT'])
    confirm_url = url_for('auth.confirm_email', token=token, _external=True)

    # Odeslání potvrzovacího e-mailu
    msg = Message('Confirm Your Email', sender=current_app.config['MAIL_USERNAME'], recipients=[email])
    msg.body = f'Please click the link to confirm your email: {confirm_url}'
    mail.send(msg)

    flash('A confirmation email has been sent. Please check your inbox.', 'info')
    return redirect(url_for('auth.login'))

@auth.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = get_serializer().loads(token, salt=current_app.config['EMAIL_CONFIRMATION_SALT'], max_age=3600)
    except:
        flash('The confirmation link is invalid or has expired.', 'danger')
        return redirect(url_for('auth.signup'))

    user = Users.query.filter_by(email=email).first()
    if not user:
        flash('Invalid confirmation request.', 'danger')
        return redirect(url_for('auth.signup'))

    if user.is_verified:
        flash('Your account is already confirmed. You can log in.', 'info')
    else:
        user.is_verified = True
        db.session.commit()
        flash('Your account has been confirmed! You can now log in.', 'success')

    return redirect(url_for('auth.login'))

@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

# Password reset request
@auth.route('/reset_password', methods=['GET','POST'])
def reset_request():
    if request.method == 'POST':
        email = request.form.get('email')
        user = Users.query.filter_by(email=email).first()

        if user:
            token = get_serializer().dumps(email, salt=current_app.config['PASSWORD_RESET_SALT'])
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            
            msg = Message('Password Reset Request', sender=current_app.config['MAIL_USERNAME'], recipients=[email])
            msg.body = f'To reset your password, click the following link: {reset_url}'
            mail.send(msg)

            flash("A password reset link has been sent. Check your e-mail.", 'info')
            return redirect(url_for('auth.login'))                      
        else:
            flash('The email does not exists', 'danger')
            return redirect(url_for('auth.reset_request'))

    return render_template('reset_request.html')

# Password reset form
@auth.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = get_serializer().loads(token, salt=current_app.config['PASSWORD_RESET_SALT'], max_age=3600)
    except:
        flash('Invalid or expired token', 'danger')
        return redirect(url_for('auth.reset_request'))

    user = Users.query.filter_by(email=email).first()
    if not user:
        flash('Invalid email address', 'danger')
        return redirect(url_for('auth.reset_request'))

    if request.method == 'POST':
        new_password = request.form.get('new_pass')
        confirm_password = request.form.get('confirm_pass')

        if new_password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('auth.reset_password', token=token))

        print(token)
        print(email)
        print(new_password)
        user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
        db.session.commit()

        flash('Your password has been updated! You can now log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html')

# Change password
@auth.route('/change_password', methods=['POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if new_password != confirm_password:
            flash('Passwords do not match!', 'danger')
            return redirect(url_for('auth.change_password'))

        if not check_password_hash(current_user.password, current_password):
            flash('Current password is incorrect!', 'danger')
            return redirect(url_for('auth.change_password'))

        current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
        db.session.commit()

        flash('Your password has been updated!', 'success')
        return redirect(url_for('main.profile'))

    return render_template('profile.html')