from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from app_pkg import db, login
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    permissions = db.Column(db.Integer)
    items = db.relationship('Item', backref='requestor', lazy='dynamic')
    comments = db.relationship('Comment', backref='requestor', lazy='dynamic')
    drawings = db.relationship('Drawing', backref='requestor', lazy='dynamic')
    descriptions = db.relationship('Description', backref='requestor', lazy='dynamic')

    def __repr__(self):
        return '<User {}>'.format(self.username)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    comments = db.relationship('Comment', backref='item', lazy='dynamic')

    def __repr__(self):
        return '<Item {}>'.format(self.name)

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(64))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'))
    
    def __repr__(self):
        return '<Comment {}>'.format(self.text)

class Drawing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(32), index=True, unique=True)
    image_data = db.Column(db.String(1024))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __repr__(self):
        return '<{} : created by {}>'.format(self.name, self.user_id)

class DrawingNode(db.Model):
    drawing_id = db.Column(db.Integer, db.ForeignKey('drawing.id'), primary_key=True)
    prev_desc_id = db.Column(db.Integer, db.ForeignKey('description.id'))
    next_desc_id = db.Column(db.Integer, db.ForeignKey('description.id'))

class Description(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(64))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __repr__(self):
        return '<{} ({})>'.format(self.text, self.user_id)

class DescriptionNode(db.Model):
    desc_id = db.Column(db.Integer, db.ForeignKey('description.id'), primary_key=True)
    prev_drawing_id = db.Column(db.Integer, db.ForeignKey('drawing.id'))
    next_drawing_id = db.Column(db.Integer, db.ForeignKey('drawing.id'))

@login.user_loader
def load_user(id):
    return User.query.get(int(id))
