from extensions import db
from flask_login import UserMixin


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    entries = db.relationship('Entry', backref='user', lazy=True)

    def __repr__(self):
        return f"<User {self.username}>"


class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(20), nullable=False)  # ISO date
    meal = db.Column(db.String(20), nullable=False)
    food_estimate = db.Column(db.String(200))
    calories = db.Column(db.Integer)
    notes = db.Column(db.Text)
    image_filename = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

    def __repr__(self):
        return f"<Entry {self.date} {self.meal} {self.calories}>"
