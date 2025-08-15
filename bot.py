from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from database import db, Provider, MaxAccount
from datetime import datetime, timedelta
from flask import Flask
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rent.db'
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
db.init_app(app)

bot = Bot(token=os.getenv('BOT_TOKEN'))
dp = Dispatcher(bot, storage=MemoryStorage())

ADMIN_IDS = [int(os.getenv('ADMIN_CHAT_ID'))]
TARIFFS = {
    '1_hour': {'price': 7, 'duration': 60, 'emoji': '⏳'},
    '2_hours': {'price': 14, 'duration': 120, 'emoji': '⌛'}
}

class Form(StatesGroup):
    waiting_for_account = State()
    waiting_for_tariff = State()
    waiting_for_wallet = State()

def main_menu():
    return ReplyKeyboardMarkup(resize_keyboard=True).add(
        KeyboardButton("📤 Сдать аккаунт"),
        KeyboardButton("💰 Баланс"),
        KeyboardButton("💳 Кошелек")
    )

def tariff_buttons():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("⏳ 1 час - 7 USDT", callback_data="tariff_1_hour"))
    markup.add(InlineKeyboardButton("⌛ 2 часа - 14 USDT", callback_data="tariff_2_hours"))
    return markup

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    with app.app_context():
        provider = Provider.query.filter_by(chat_id=str(message.chat.id)).first()
        if not provider:
            provider = Provider(chat_id=str(message.chat.id))
            db.session.add(provider)
            db.session.commit()
    
    await message.answer(
        "👋 <b>Добро пожаловать в MaxRent!</b>\n\n"
        "🔹 Сдавайте аккаунты Max в аренду\n"
        "🔹 Получайте выплаты в USDT\n\n"
        "Выберите действие:",
        reply_markup=main_menu(),
        parse_mode='HTML'
    )

@dp.message_handler(text="📤 Сдать аккаунт")
async def add_account(message: types.Message):
    await Form.waiting_for_account.set()
    await message.answer("Отправьте логин и пароль от аккаунта Max через пробел:")

@dp.message_handler(state=Form.waiting_for_account)
async def process_account(message: types.Message, state: FSMContext):
    if len(message.text.split()) != 2:
        await message.answer("❌ Неверный формат. Отправьте логин и пароль через пробел:")
        return
    
    login, password = message.text.split()
    async with state.proxy() as data:
        data['login'] = login
        data['password'] = password
    
    await message.answer("Выберите тариф для этого аккаунта:", reply_markup=tariff_buttons())
    await Form.waiting_for_tariff.set()

@dp.callback_query_handler(lambda c: c.data.startswith('tariff_'), state=Form.waiting_for_tariff)
async def process_tariff(callback: types.CallbackQuery, state: FSMContext):
    tariff = callback.data.split('_')[1] + '_' + callback.data.split('_')[2]
    
    async with state.proxy() as data:
        login = data['login']
        password = data['password']
    
    with app.app_context():
        provider = Provider.query.filter_by(chat_id=str(callback.message.chat.id)).first()
        
        account = MaxAccount(
            login=login,
            password=password,
            provider_id=provider.id,
            tariff=tariff
        )
        db.session.add(account)
        db.session.commit()
    
    await callback.message.edit_text(
        f"✅ <b>Аккаунт добавлен!</b>\n\n"
        f"👤 Логин: <code>{login}</code>\n"
        f"🔐 Пароль: <code>{password}</code>\n"
        f"⏱ Тариф: {tariff.replace('_', ' ')}\n"
        f"💵 Цена аренды: {TARIFFS[tariff]['price']} USDT",
        parse_mode='HTML'
    )
    await state.finish()

@dp.message_handler(text="💰 Баланс")
async def show_balance(message: types.Message):
    with app.app_context():
        provider = Provider.query.filter_by(chat_id=str(message.chat.id)).first()
        if provider.wallet_address:
            wallet_info = f"\n💳 Кошелек: <code>{provider.wallet_address}</code>"
        else:
            wallet_info = "\n⚠ Кошелек не привязан. Используйте кнопку '💳 Кошелек'"
        
        await message.answer(
            f"💰 <b>Ваш баланс:</b> {provider.balance} USDT{wallet_info}\n\n"
            f"Выплаты производятся автоматически при достижении 50 USDT",
            parse_mode='HTML',
            reply_markup=main_menu()
        )

@dp.message_handler(text="💳 Кошелек")
async def ask_wallet(message: types.Message):
    await message.answer("Отправьте ваш USDT TRC20 кошелек для выплат (начинается с 'T'):")
    await Form.waiting_for_wallet.set()

@dp.message_handler(state=Form.waiting_for_wallet)
async def save_wallet(message: types.Message, state: FSMContext):
    wallet = message.text.strip()
    if not wallet.startswith('T') or len(wallet) < 25:
        await message.answer("❌ Неверный формат кошелька USDT TRC20. Попробуйте еще раз:")
        return
    
    with app.app_context():
        provider = Provider.query.filter_by(chat_id=str(message.chat.id)).first()
        provider.wallet_address = wallet
        db.session.commit()
    
    await message.answer(
        f"✅ Кошелек успешно привязан:\n<code>{wallet}</code>\n\n"
        f"Теперь вы можете получать выплаты на этот адрес",
        parse_mode='HTML',
        reply_markup=main_menu()
    )
    await state.finish()

@dp.message_handler(commands=['rent'])
async def rent_menu(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("🚫 Доступ запрещен")
    
    with app.app_context():
        accounts = MaxAccount.query.filter_by(is_rented=False).all()
    
    if not accounts:
        return await message.answer("😔 Нет доступных аккаунтов")
    
    text = "🔄 <b>Доступные аккаунты:</b>\n"
    for acc in accounts[:5]:
        text += f"\n👤 <code>{acc.login}</code> - {TARIFFS[acc.tariff]['price']} USDT (/rent_{acc.id})"
    
    await message.answer(text, parse_mode='HTML')

@dp.message_handler(lambda msg: msg.text.startswith('/rent_'))
async def process_rent(message: types.Message):
    if message.from_user.id not in ADMIN_IDS:
        return await message.answer("🚫 Доступ запрещен")
    
    try:
        account_id = int(message.text.split('_')[1])
    except:
        return await message.answer("❌ Неверный формат команды")
    
    with app.app_context():
        account = MaxAccount.query.get(account_id)
        if not account:
            return await message.answer("❌ Аккаунт не найден")
        
        if account.is_rented:
            return await message.answer("❌ Аккаунт уже арендован")
        
        account.is_rented = True
        account.rented_until = datetime.now() + timedelta(minutes=TARIFFS[account.tariff]['duration'])
        db.session.commit()
        
        await message.answer(
            f"✅ <b>Аккаунт арендован!</b>\n\n"
            f"👤 Логин: <code>{account.login}</code>\n"
            f"🔐 Пароль: <code>{account.password}</code>\n"
            f"⏱ Тариф: {account.tariff.replace('_', ' ')}\n"
            f"⏳ До: {account.rented_until.strftime('%H:%M')}",
            parse_mode='HTML'
        )

async def main():
    with app.app_context():
        db.create_all()
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())