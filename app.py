import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from database import db, Provider, MaxAccount
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///rent.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Инициализация планировщика
scheduler = BackgroundScheduler(daemon=True)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@login_manager.user_loader
def load_user(user_id):
    return Provider.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Provider.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Неверные учетные данные')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    accounts = MaxAccount.query.filter_by(provider_id=current_user.id).all()
    return render_template('dashboard.html', accounts=accounts)

def create_tables():
    with app.app_context():
        db.create_all()
        if not Provider.query.first():
            admin = Provider(
                username='admin',
                password='admin123',
                is_admin=True,
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()

if __name__ == '__main__':
    create_tables()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
