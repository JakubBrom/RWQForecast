from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from dotenv import load_dotenv
from flask_mail import Mail
import os

load_dotenv()

# init SQLAlchemy so we can use it later in our models
db = SQLAlchemy()
# init Mail so we can use it later in our app
mail = Mail()

def create_app():
    app = Flask(__name__)

    DB_USER=os.getenv('DB_USER')
    DB_PASSWORD=os.getenv('DB_PASSWORD')
    DB_HOST=os.getenv('DB_HOST')
    DB_PORT=os.getenv('DB_PORT')
    DB_NAME=os.getenv('DB_NAME')

    app.config['SQLALCHEMY_DATABASE_URI'] = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['SECURITY_SALT'] = os.getenv('SECURITY_SALT')
    app.config['PASSWORD_RESET_SALT'] = os.getenv('PASSWORD_RESET_SALT')
    app.config['EMAIL_CONFIRMATION_SALT'] = os.getenv('EMAIL_CONFIRMATION_SALT')
    
    # e-mail settings
    app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
    app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT'))
    app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS') == 'True'
    app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL') == 'True'
    app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
    app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
    app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')
    
    mail = Mail(app)      
    
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    from .models import Users

    @login_manager.user_loader
    def load_user(user_id):
        # since the user_id is just the primary key of our user table, use it in the query for the user
        return Users.query.get(int(user_id))

    # blueprint for auth routes in our app
    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    # blueprint for non-auth parts of app
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app