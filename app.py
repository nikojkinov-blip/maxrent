import os
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, login_user, login_required, current_user, logout_user, UserMixin
from database import db, Provider, MaxAccount
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import logging

app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')

# Конфигурация БД
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:////tmp/rent.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Инициализация расширений
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Настройки тарифов
TARIFFS = {
    '1_hour': {'price': 7, 'duration': 60, 'emoji': '⏳'},
    '2_hours': {'price': 14, 'duration': 120, 'emoji': '⌛'}
}

# Планировщик задач
scheduler = BackgroundScheduler()
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

# Логирование
logging.basicConfig(level=logging.DEBUG)
app.logger.setLevel(logging.DEBUG)

@login_manager.user_loader
def load_user(user_id):
    return Provider.query.get(int(user_id))

def create_admin():
    with app.app_context():
        if not Provider.query.filter_by(username='admin').first():
            admin = Provider(
                username='admin',
                password=generate_password_hash('admin123'),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()
            app.logger.info('Admin user created')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = Provider.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Неверные учетные данные')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    accounts = MaxAccount.query.filter_by(provider_id=current_user.id).all()
    free_accounts = len([a for a in accounts if not a.is_rented])
    rented_accounts = len(accounts) - free_accounts
    
    return render_template('dashboard.html', 
                         accounts=accounts,
                         free_accounts=free_accounts,
                         rented_accounts=rented_accounts,
                         tariffs=TARIFFS,
                         current_user=current_user)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/test404')
def test_404():
    abort(404)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
