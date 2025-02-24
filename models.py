from flask_login import UserMixin
from . import db

class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True) # primary keys are required by SQLAlchemy
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(1000))
    name = db.Column(db.String(1000))
    is_verified = db.Column(db.Boolean, default=False)
    urole = db.Column(db.Integer, default=2)
