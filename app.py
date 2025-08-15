from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, current_user
from database import db, Provider, MaxAccount
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

app = Flask(__name__)
app.secret_key = 'super-secret-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rent.db'
app.config['TEMPLATES_AUTO_RELOAD'] = True
db.init_app(app)

TARIFFS = {
    '1_hour': {'price': 7, 'duration': 60, 'emoji': '⏳'},
    '2_hours': {'price': 14, 'duration': 120, 'emoji': '⌛'}
}

scheduler = BackgroundScheduler()

def check_rentals():
    with app.app_context():
        expired = MaxAccount.query.filter(
            MaxAccount.is_rented == True,
            MaxAccount.rented_until < datetime.now()
        ).all()
        
        for acc in expired:
            acc.is_rented = False
            provider = Provider.query.get(acc.provider_id)
            provider.balance += TARIFFS[acc.tariff]['price']
            db.session.commit()

scheduler.add_job(func=check_rentals, trigger='interval', minutes=1)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Provider.query.get(int(user_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Provider.query.filter_by(username=request.form['username']).first()
        if user and user.password == request.form['password']:
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Неверные данные!', 'danger')
    return render_template('login.html')

@app.route('/')
@login_required
def dashboard():
    accounts = MaxAccount.query.all()
    free_accounts = MaxAccount.query.filter_by(is_rented=False).count()
    rented_accounts = MaxAccount.query.filter_by(is_rented=True).count()
    return render_template('dashboard.html',
                         accounts=accounts,
                         free_accounts=free_accounts,
                         rented_accounts=rented_accounts,
                         tariffs=TARIFFS,
                         current_time=datetime.now())

@app.route('/rent/<int:account_id>/<tariff>')
@login_required
def rent_account(account_id, tariff):
    if tariff not in TARIFFS:
        flash('Неверный тариф!', 'danger')
        return redirect(url_for('dashboard'))
    
    account = MaxAccount.query.get(account_id)
    if not account.is_rented:
        account.is_rented = True
        account.tariff = tariff
        account.rented_until = datetime.now() + timedelta(minutes=TARIFFS[tariff]['duration'])
        db.session.commit()
        
        return jsonify({
            'login': account.login,
            'password': account.password,
            'tariff': tariff.replace('_', ' '),
            'until': account.rented_until.strftime('%H:%M'),
            'price': TARIFFS[tariff]['price']
        })
    
    flash('Аккаунт уже арендован!', 'warning')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
    with app.app_context():
        db.create_all()
        if not Provider.query.first():
            admin = Provider(
                username='admin',
                password='admin123',
                chat_id='ADMIN_CHAT_ID',
                is_admin=True,
                wallet_address='TАдресКошелька'
            )
            db.session.add(admin)
            db.session.commit()
    app.run(debug=True)
