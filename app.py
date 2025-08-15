import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from database import db, Provider, MaxAccount
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# ================================================
# НАСТРОЙКА ПРИЛОЖЕНИЯ
# ================================================
app = Flask(__name__, template_folder='templates')

# Безопасность
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['SESSION_COOKIE_SECURE'] = True  # Только HTTPS
app.config['REMEMBER_COOKIE_SECURE'] = True

# База данных
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///prod.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Инициализация расширений
db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# ================================================
# КОНСТАНТЫ И СЕРВИСЫ
# ================================================
TARIFFS = {
    '1_hour': {'price': 7, 'duration': 60},
    '2_hours': {'price': 14, 'duration': 120}
}

scheduler = BackgroundScheduler(daemon=True)
scheduler.start()
atexit.register(scheduler.shutdown)

# ================================================
# АВТОРИЗАЦИЯ
# ================================================
@login_manager.user_loader
def load_user(user_id):
    return Provider.query.get(int(user_id))

def create_first_admin():
    with app.app_context():
        if not Provider.query.filter_by(is_admin=True).first():
            admin = Provider(
                username=os.environ.get('ADMIN_LOGIN', 'admin'),
                password=os.environ.get('ADMIN_PASSWORD', 'admin123'),
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()

# ================================================
# РОУТИНГ
# ================================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        user = Provider.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user, remember=True)
            return redirect(url_for('dashboard'))
        flash('Неверные учетные данные', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    accounts = MaxAccount.query.order_by(MaxAccount.id.desc()).limit(50).all()
    return render_template('dashboard.html', 
                        accounts=accounts,
                        tariffs=TARIFFS,
                        current_time=datetime.utcnow())

# ================================================
# ЗАПУСК
# ================================================
def initialize_app():
    with app.app_context():
        db.create_all()
        create_first_admin()
        
        # Ежеминутная проверка аренды
        scheduler.add_job(
            func=check_rental_expiry,
            trigger='interval',
            minutes=1
        )

def check_rental_expiry():
    with app.app_context():
        expired = MaxAccount.query.filter(
            MaxAccount.is_rented == True,
            MaxAccount.rented_until < datetime.utcnow()
        ).all()
        
        for acc in expired:
            acc.is_rented = False
            db.session.commit()

if __name__ == '__main__':
    initialize_app()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
