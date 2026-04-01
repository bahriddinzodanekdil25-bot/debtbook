import asyncio
import logging
import os
import aiosqlite
import aiohttp
from datetime import date, datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SMSC_LOGIN = os.getenv("SMSC_LOGIN", "")
SMSC_PASSWORD = os.getenv("SMSC_PASSWORD", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = "debtors.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS debtors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                product TEXT NOT NULL,
                amount REAL NOT NULL,
                due_date TEXT NOT NULL,
                notified INTEGER DEFAULT 0,
                paid INTEGER DEFAULT 0
            )
        """)
        await db.commit()

async def add_debtor(name, phone, product, amount, due_date):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO debtors (name, phone, product, amount, due_date) VALUES (?, ?, ?, ?, ?)",
            (name, phone, product, amount, due_date)
        )
        await db.commit()

async def get_all_debtors():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM debtors WHERE paid = 0 ORDER BY due_date") as cursor:
            return await cursor.fetchall()

async def get_due_today():
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM debtors WHERE due_date = ? AND paid = 0 AND notified = 0", (today,)
        ) as cursor:
            return await cursor.fetchall()

async def mark_notified(debtor_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE debtors SET notified = 1 WHERE id = ?", (debtor_id,))
        await db.commit()

async def mark_paid(debtor_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE debtors SET paid = 1 WHERE id = ?", (debtor_id,))
        await db.commit()

async def send_sms(phone: str, message: str) -> bool:
    phone = phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    url = "https://smsc.ru/sys/send.php"
    params = {
        "login": SMSC_LOGIN,
        "psw": SMSC_PASSWORD,
        "phones": phone,
        "mes": message,
        "charset": "utf-8",
        "fmt": 3
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                result = await response.json(content_type=None)
                if "error" in result:
                    print(f"SMS error: {result}")
                    return False
                return True
    except Exception as e:
        print(f"SMS exception: {e}")
        return False

async def check_due_debts(bot: Bot):
    debtors = await get_due_today()
    for debtor in debtors:
        msg = (
            f"Здравствуйте, {debtor['name']}! "
            f"Напоминаем о долге: {debtor['amount']} сом за {debtor['product']}. "
            f"Пожалуйста, оплатите сегодня. Спасибо!"
        )
        sms_sent = await send_sms(debtor['phone'], msg)
        await mark_notified(debtor['id'])
        status = "✅ SMS отправлено" if sms_sent else "❌ SMS не отправлено"
        await bot.send_message(
            ADMIN_ID,
            f"📋 Уведомление:\n👤 {debtor['name']}\n📱 {debtor['phone']}\n"
            f"🛒 {debtor['product']} — {debtor['amount']} сом\n{status}"
        )

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить должника")],
        [KeyboardButton(text="📋 Список должников")],
        [KeyboardButton(text="✅ Закрыть долг")],
    ],
    resize_keyboard=True
)

class AddDebtorForm(StatesGroup):
    name = State()
    phone = State()
    product = State()
    amount = State()
    due_date = State()

class CloseDebtForm(StatesGroup):
    debtor_id = State()

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Добро пожаловать в *Книгу долгов*!\n\nВыберите действие 👇",
        reply_markup=main_keyboard, parse_mode="Markdown"
    )

@router.message(F.text == "➕ Добавить должника")
async def start_add(message: Message, state: FSMContext):
    await state.set_state(AddDebtorForm.name)
    await message.answer("👤 Введите имя должника:")

@router.message(AddDebtorForm.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddDebtorForm.phone)
    await message.answer("📱 Введите номер телефона (например: +996700123456):")

@router.message(AddDebtorForm.phone)
async def get_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(AddDebtorForm.product)
    await message.answer("🛒 Что взял в долг?")

@router.message(AddDebtorForm.product)
async def get_product(message: Message, state: FSMContext):
    await state.update_data(product=message.text)
    await state.set_state(AddDebtorForm.amount)
    await message.answer("💰 Сумма долга (только цифры):")

@router.message(AddDebtorForm.amount)
async def get_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", "."))
        await state.update_data(amount=amount)
        await state.set_state(AddDebtorForm.due_date)
        await message.answer("📅 Дата возврата (формат: ДД.ММ.ГГГГ, например 15.04.2026):")
    except ValueError:
        await message.answer("❌ Введите только число! Например: 5000")

@router.message(AddDebtorForm.due_date)
async def get_due_date(message: Message, state: FSMContext):
    try:
        due_date = datetime.strptime(message.text, "%d.%m.%Y").date().isoformat()
        data = await state.get_data()
        await state.clear()
        await add_debtor(data['name'], data['phone'], data['product'], data['amount'], due_date)
        await message.answer(
            f"✅ *Должник добавлен!*\n\n"
            f"👤 {data['name']}\n📱 {data['phone']}\n"
            f"🛒 {data['product']}\n💰 {data['amount']} сом\n📅 Срок: {message.text}",
            parse_mode="Markdown"
        )
    except ValueError:
        await message.answer("❌ Неверный формат! Введите: ДД.ММ.ГГГГ")

@router.message(F.text == "📋 Список должников")
async def list_debtors(message: Message):
    debtors = await get_all_debtors()
    if not debtors:
        await message.answer("✅ Должников нет!")
        return
    text = "📋 *Список должников:*\n\n"
    for d in debtors:
        text += f"🔹 ID:{d['id']} *{d['name']}*\n   📱 {d['phone']}\n   🛒 {d['product']} — {d['amount']} сом\n   📅 {d['due_date']}\n\n"
    await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "✅ Закрыть долг")
async def start_close(message: Message, state: FSMContext):
    await state.set_state(CloseDebtForm.debtor_id)
    await message.answer("Введите ID должника из списка:")

@router.message(CloseDebtForm.debtor_id)
async def close_debt(message: Message, state: FSMContext):
    await state.clear()
    try:
        debtor_id = int(message.text)
        await mark_paid(debtor_id)
        await message.answer(f"✅ Долг #{debtor_id} закрыт!")
    except ValueError:
        await message.answer("❌ Введите только номер ID!")

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await init_db()
    scheduler = AsyncIOScheduler(timezone="Asia/Bishkek")
    scheduler.add_job(check_due_debts, "cron", hour=9, minute=0, args=[bot])
    scheduler.start()
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
