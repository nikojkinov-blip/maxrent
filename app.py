import os
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, current_user, logout_user, UserMixin
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# Инициализация приложения
app = Flask(__name__, template_folder='templates')
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///rent.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Модели базы данных
class Provider(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True)  # Обязательное поле для Flask-Login
    is_admin = db.Column(db.Boolean, default=False)
    chat_id = db.Column(db.String(50), nullable=True)
    balance = db.Column(db.Float, default=0.0)
    wallet_address = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_id(self):
        return str(self.id)

class MaxAccount(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    login = db.Column(db.String(120), nullable=False)
    password = db.Column(db.String(120), nullable=False)
    price = db.Column(db.Float, default=7.0)
    is_rented = db.Column(db.Boolean, default=False)
    rented_until = db.Column(db.DateTime)
    provider_id = db.Column(db.Integer, db.ForeignKey('provider.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Настройки тарифов
TARIFFS = {
    '1_hour': {'price': 7, 'duration': 60, 'emoji': '⏳'},
    '2_hours': {'price': 14, 'duration': 120, 'emoji': '⌛'}
}

# Планировщик задач
scheduler = BackgroundScheduler(daemon=True)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

@login_manager.user_loader
def load_user(user_id):
    return Provider.query.get(int(user_id))

def create_admin():
    with app.app_context():
        if not Provider.query.filter_by(is_admin=True).first():
            admin = Provider(
                username=os.environ.get('ADMIN_USERNAME', 'admin'),
                password=os.environ.get('ADMIN_PASSWORD', 'admin123'),
                is_admin=True,
                is_active=True
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
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        user = Provider.query.filter_by(username=request.form['username']).first()
        
        if user and user.password == request.form['password']:
            if not user.is_active:
                flash('Аккаунт деактивирован', 'danger')
                return redirect(url_for('login'))
                
            login_user(user, remember=True)
            return redirect(url_for('dashboard'))
        
        flash('Неверные учетные данные', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    accounts = MaxAccount.query.order_by(MaxAccount.id.desc()).limit(50).all()
    return render_template('dashboard.html',
                         accounts=accounts,
                         tariffs=TARIFFS,
                         current_time=datetime.utcnow())

@app.route('/rent/<int:account_id>/<tariff>')
@login_required
def rent_account(account_id, tariff):
    if tariff not in TARIFFS:
        flash('Неверный тариф', 'danger')
        return redirect(url_for('dashboard'))
    
    account = MaxAccount.query.get_or_404(account_id)
    if not account.is_rented:
        account.is_rented = True
        account.rented_until = datetime.utcnow() + timedelta(minutes=TARIFFS[tariff]['duration'])
        db.session.commit()
        return jsonify({
            'login': account.login,
            'password': account.password,
            'until': account.rented_until.strftime('%Y-%m-%d %H:%M')
        })
    flash('Аккаунт уже арендован', 'warning')
    return redirect(url_for('dashboard'))

def check_expired_rentals():
    with app.app_context():
        expired = MaxAccount.query.filter(
            MaxAccount.is_rented == True,
            MaxAccount.rented_until < datetime.utcnow()
        ).all()
        for acc in expired:
            acc.is_rented = False
            db.session.commit()

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_admin()
        scheduler.add_job(
            check_expired_rentals,
            'interval',
            minutes=1,
            id='rental_checker'
        )
    
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)
