import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, current_user, logout_user
from database import db, Provider, MaxAccount
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# Инициализация приложения
app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', 'default-secret-key')

# Конфигурация БД
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///rent.db')
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

@login_manager.user_loader
def load_user(user_id):
    return Provider.query.get(int(user_id))

def create_admin():
    with app.app_context():
        if not Provider.query.first():
            admin = Provider(
                username='admin',
                password='admin123',
                is_admin=True
            )
            db.session.add(admin)
            db.session.commit()

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        return f"Ошибка загрузки шаблона: {str(e)}", 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Provider.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Неверные учетные данные')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    accounts = MaxAccount.query.all()
    return render_template('dashboard.html', 
                         accounts=accounts,
                         tariffs=TARIFFS)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin()
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
