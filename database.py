from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta

db = SQLAlchemy()

class Provider(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.String(50), unique=True, nullable=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)
    wallet_address = db.Column(db.String(120))
    balance = db.Column(db.Float, default=0.0)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)  # Обязательное поле для Flask-Login
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Рекомендуемое поле

    # Метод для Flask-Login
    def get_id(self):
        return str(self.id)

class MaxAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(120), nullable=False)
    tariff = db.Column(db.String(20), default='1_hour')
    is_rented = db.Column(db.Boolean, default=False)
    rented_until = db.Column(db.DateTime)
    provider_id = db.Column(db.Integer, db.ForeignKey('provider.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)  # Рекомендуемое поле

    # Связь с провайдером
    provider = db.relationship('Provider', backref='accounts')
