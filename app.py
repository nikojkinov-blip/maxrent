from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from database import db, Provider, MaxAccount
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rent.db'
app.config['TEMPLATES_AUTO_RELOAD'] = True
db.init_app(app)

# Настройки тарифов
TARIFFS = {
    '1_hour': {'price': 7, 'duration': 60, 'emoji': '⏳'},
    '2_hours': {'price': 14, 'duration': 120, 'emoji': '⌛'}
}

# Настройка планировщика
scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# Настройка Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'

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
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    accounts = MaxAccount.query.all()
    return render_template('dashboard.html', accounts=accounts)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not Provider.query.first():
            admin = Provider(
                username='admin',
                password='admin123',
                chat_id='ADMIN_CHAT_ID',
                is_admin=True,
                wallet_address='TWalletAddress'
            )
            db.session.add(admin)
            db.session.commit()
    app.run(host='0.0.0.0', port=10000, debug=True)
