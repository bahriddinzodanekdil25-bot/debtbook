import asyncio
import logging
import os
import aiosqlite
import aiohttp
import uuid
from datetime import date, datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SMSC_LOGIN = os.getenv("SMSC_LOGIN", "")
SMSC_PASSWORD = os.getenv("SMSC_PASSWORD", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
DB_PATH = "debtors.db"

# ========== ТЕКСТЫ НА 2 ЯЗЫКАХ ==========
TEXTS = {
    "ru": {
        "welcome": "👋 Добро пожаловать в <b>Книгу долгов</b>!\n\nВыберите действие 👇",
        "add": "➕ Добавить должника",
        "list": "📋 Список должников",
        "close": "✅ Закрыть долг",
        "stats": "📊 Статистика",
        "ask_name": "👤 Введите имя должника:",
        "ask_phone": "📱 Введите номер телефона:\n(например: +79001234567)",
        "ask_product": "🛒 Что взял в долг?",
        "ask_amount": "💰 Сумма долга (только цифры):",
        "ask_currency": "💱 Выберите валюту:",
        "ask_date": "📅 Дата возврата (формат: ДД.ММ.ГГГГ)\nНапример: 15.04.2026",
        "added": "✅ <b>Должник добавлен!</b>",
        "no_debtors": "✅ Должников нет! Все долги погашены.",
        "closed": "✅ Долг закрыт!",
        "ask_id": "Введите ID должника из списка:",
        "wrong_number": "❌ Введите только число! Например: 5000",
        "wrong_date": "❌ Неверный формат! Введите: ДД.ММ.ГГГГ",
        "wrong_id": "❌ Введите только номер ID!",
        "debt_link": "🔗 <b>Ссылка для должника готова!</b>\n\nОтправьте эту ссылку должнику:\n",
        "debt_reminder": "📋 <b>Напоминание о долге</b>\n\n",
        "sms_sent": "✅ SMS отправлено",
        "sms_fail": "❌ SMS не отправлено",
        "tg_sent": "✅ Уведомление в Telegram отправлено",
        "rub": "₽ Рубли",
        "smn": "смн Сомони",
    },
    "tj": {
        "welcome": "👋 Хуш омадед ба <b>Китоби қарзҳо</b>!\n\nАмалро интихоб кунед 👇",
        "add": "➕ Қарздор илова кунед",
        "list": "📋 Рӯйхати қарздорон",
        "close": "✅ Қарзро пӯшед",
        "stats": "📊 Омор",
        "ask_name": "👤 Номи қарздорро ворид кунед:",
        "ask_phone": "📱 Рақами телефонро ворид кунед:\n(масалан: +992901234567)",
        "ask_product": "🛒 Чӣ қарз гирифт?",
        "ask_amount": "💰 Маблағи қарз (танҳо рақам):",
        "ask_currency": "💱 Асъорро интихоб кунед:",
        "ask_date": "📅 Санаи бозгашт (формат: РР.МА.СССС)\nМасалан: 15.04.2026",
        "added": "✅ <b>Қарздор илова шуд!</b>",
        "no_debtors": "✅ Қарздор нест! Ҳама қарзҳо пардохт шуданд.",
        "closed": "✅ Қарз пӯшида шуд!",
        "ask_id": "ID-и қарздорро аз рӯйхат ворид кунед:",
        "wrong_number": "❌ Танҳо рақам ворид кунед! Масалан: 5000",
        "wrong_date": "❌ Формат нодуруст! Ворид кунед: РР.МА.СССС",
        "wrong_id": "❌ Танҳо рақами ID ворид кунед!",
        "debt_link": "🔗 <b>Пайванд барои қарздор омода аст!</b>\n\nИн пайвандро ба қарздор фиристед:\n",
        "debt_reminder": "📋 <b>Хотиррасонии қарз</b>\n\n",
        "sms_sent": "✅ SMS фиристода шуд",
        "sms_fail": "❌ SMS фиристода нашуд",
        "tg_sent": "✅ Огоҳӣ дар Telegram фиристода шуд",
        "rub": "₽ Рубл",
        "smn": "смн Сомонӣ",
    }
}

# ========== БАЗА ДАННЫХ ==========
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS debtors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                product TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL DEFAULT '₽',
                due_date TEXT NOT NULL,
                token TEXT UNIQUE,
                debtor_tg_id INTEGER DEFAULT 0,
                notified INTEGER DEFAULT 0,
                paid INTEGER DEFAULT 0
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                tg_id INTEGER PRIMARY KEY,
                lang TEXT DEFAULT 'ru'
            )
        """)
        await db.commit()

async def set_lang(tg_id, lang):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO users (tg_id, lang) VALUES (?, ?)", (tg_id, lang))
        await db.commit()

async def get_lang(tg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT lang FROM users WHERE tg_id = ?", (tg_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else "ru"

async def add_debtor(name, phone, product, amount, currency, due_date):
    token = str(uuid.uuid4())[:8]
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO debtors (name, phone, product, amount, currency, due_date, token) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, phone, product, amount, currency, due_date, token)
        )
        await db.commit()
    return token

async def get_all_debtors():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM debtors WHERE paid = 0 ORDER BY due_date") as cursor:
            return await cursor.fetchall()

async def get_debtor_by_token(token):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM debtors WHERE token = ?", (token,)) as cursor:
            return await cursor.fetchone()

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

async def set_debtor_tg(token, tg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE debtors SET debtor_tg_id = ? WHERE token = ?", (tg_id, token))
        await db.commit()

async def get_stats():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM debtors WHERE paid = 0") as c:
            active = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM debtors WHERE paid = 1") as c:
            closed = (await c.fetchone())[0]
        async with db.execute("SELECT SUM(amount) FROM debtors WHERE paid = 0") as c:
            total = (await c.fetchone())[0] or 0
    return active, closed, total

# ========== SMS ==========
async def send_sms(phone: str, message: str) -> bool:
    phone = phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")
    url = "https://smsc.ru/sys/send.php"
    params = {"login": SMSC_LOGIN, "psw": SMSC_PASSWORD, "phones": phone, "mes": message, "charset": "utf-8", "fmt": 3}
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

# ========== ПЛАНИРОВЩИК ==========
async def check_due_debts(bot: Bot):
    debtors = await get_due_today()
    for debtor in debtors:
        msg_ru = (
            f"Здравствуйте, {debtor['name']}! "
            f"Напоминаем о долге: {debtor['amount']} {debtor['currency']} за {debtor['product']}. "
            f"Срок оплаты сегодня. Спасибо!"
        )
        tg_sent = False
        sms_sent = False

        if debtor['debtor_tg_id']:
            try:
                await bot.send_message(
                    debtor['debtor_tg_id'],
                    f"⏰ <b>Напоминание о долге!</b>\n\n"
                    f"👤 {debtor['name']}\n"
                    f"🛒 {debtor['product']}\n"
                    f"💰 {debtor['amount']} {debtor['currency']}\n"
                    f"📅 Срок: сегодня!\n\n"
                    f"Пожалуйста, оплатите вовремя 🙏",
                    parse_mode="HTML"
                )
                tg_sent = True
            except:
                pass

        if not tg_sent:
            sms_sent = await send_sms(debtor['phone'], msg_ru)

        await mark_notified(debtor['id'])

        status = ""
        if tg_sent:
            status = "✅ Уведомление в Telegram отправлено"
        elif sms_sent:
            status = "✅ SMS отправлено"
        else:
            status = "❌ Не удалось отправить"

        await bot.send_message(
            ADMIN_ID,
            f"📋 <b>Уведомление отправлено:</b>\n"
            f"👤 {debtor['name']}\n"
            f"📱 {debtor['phone']}\n"
            f"🛒 {debtor['product']} — {debtor['amount']} {debtor['currency']}\n"
            f"{status}",
            parse_mode="HTML"
        )

# ========== КЛАВИАТУРЫ ==========
def main_keyboard(lang="ru"):
    t = TEXTS[lang]
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["add"])],
            [KeyboardButton(text=t["list"]), KeyboardButton(text=t["stats"])],
            [KeyboardButton(text=t["close"])],
        ],
        resize_keyboard=True
    )

def lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇹🇯 Тоҷикӣ", callback_data="lang_tj"),
        ]
    ])

def currency_keyboard(lang="ru"):
    t = TEXTS[lang]
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t["rub"], callback_data="cur_₽"),
            InlineKeyboardButton(text=t["smn"], callback_data="cur_смн"),
        ]
    ])

# ========== FSM ==========
class AddDebtorForm(StatesGroup):
    name = State()
    phone = State()
    product = State()
    amount = State()
    currency = State()
    due_date = State()

class CloseDebtForm(StatesGroup):
    debtor_id = State()

class LangSelect(StatesGroup):
    waiting = State()

# ========== ХЭНДЛЕРЫ ==========
router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    args = message.text.split()
    if len(args) > 1:
        token = args[1]
        debtor = await get_debtor_by_token(token)
        if debtor:
            await set_debtor_tg(token, message.from_user.id)
            await message.answer(
                f"👋 Здравствуйте, <b>{debtor['name']}</b>!\n\n"
                f"📋 <b>Информация о вашем долге:</b>\n\n"
                f"🛒 Товар: {debtor['product']}\n"
                f"💰 Сумма: {debtor['amount']} {debtor['currency']}\n"
                f"📅 Срок оплаты: {debtor['due_date']}\n\n"
                f"✅ Вы подписаны на напоминания. Мы напомним вам в день срока!",
                parse_mode="HTML"
            )
            return

    await message.answer(
        "🌍 Выберите язык / Забонро интихоб кунед:",
        reply_markup=lang_keyboard()
    )

@router.callback_query(F.data.startswith("lang_"))
async def set_language(callback: CallbackQuery):
    lang = callback.data.split("_")[1]
    await set_lang(callback.from_user.id, lang)
    t = TEXTS[lang]
    await callback.message.answer(t["welcome"], reply_markup=main_keyboard(lang), parse_mode="HTML")
    await callback.answer()

@router.message(F.text.in_(["➕ Добавить должника", "➕ Қарздор илова кунед"]))
async def start_add(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.set_state(AddDebtorForm.name)
    await state.update_data(lang=lang)
    await message.answer(TEXTS[lang]["ask_name"])

@router.message(AddDebtorForm.name)
async def get_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.update_data(name=message.text)
    await state.set_state(AddDebtorForm.phone)
    await message.answer(TEXTS[lang]["ask_phone"])

@router.message(AddDebtorForm.phone)
async def get_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.update_data(phone=message.text)
    await state.set_state(AddDebtorForm.product)
    await message.answer(TEXTS[lang]["ask_product"])

@router.message(AddDebtorForm.product)
async def get_product(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.update_data(product=message.text)
    await state.set_state(AddDebtorForm.amount)
    await message.answer(TEXTS[lang]["ask_amount"])

@router.message(AddDebtorForm.amount)
async def get_amount(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    try:
        amount = float(message.text.replace(",", "."))
        await state.update_data(amount=amount)
        await state.set_state(AddDebtorForm.currency)
        await message.answer(TEXTS[lang]["ask_currency"], reply_markup=currency_keyboard(lang))
    except ValueError:
        await message.answer(TEXTS[lang]["wrong_number"])

@router.callback_query(F.data.startswith("cur_"))
async def get_currency(callback: CallbackQuery, state: FSMContext):
    currency = callback.data.split("_")[1]
    data = await state.get_data()
    lang = data.get("lang", "ru")
    await state.update_data(currency=currency)
    await state.set_state(AddDebtorForm.due_date)
    await callback.message.answer(TEXTS[lang]["ask_date"])
    await callback.answer()

@router.message(AddDebtorForm.due_date)
async def get_due_date(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = data.get("lang", "ru")
    try:
        due_date = datetime.strptime(message.text, "%d.%m.%Y").date().isoformat()
        await state.clear()
        token = await add_debtor(
            data['name'], data['phone'], data['product'],
            data['amount'], data['currency'], due_date
        )
        bot_info = await message.bot.get_me()
        link = f"https://t.me/{bot_info.username}?start={token}"
        await message.answer(
            f"{TEXTS[lang]['added']}\n\n"
            f"👤 {data['name']}\n"
            f"📱 {data['phone']}\n"
            f"🛒 {data['product']}\n"
            f"💰 {data['amount']} {data['currency']}\n"
            f"📅 Срок: {message.text}\n\n"
            f"{TEXTS[lang]['debt_link']}<code>{link}</code>\n\n"
            f"📲 Отправьте эту ссылку должнику — он подпишется и получит бесплатное Telegram уведомление!",
            parse_mode="HTML"
        )
    except ValueError:
        await message.answer(TEXTS[lang]["wrong_date"])

@router.message(F.text.in_(["📋 Список должников", "📋 Рӯйхати қарздорон"]))
async def list_debtors(message: Message):
    lang = await get_lang(message.from_user.id)
    debtors = await get_all_debtors()
    if not debtors:
        await message.answer(TEXTS[lang]["no_debtors"])
        return
    text = "📋 <b>Список должников:</b>\n\n"
    for d in debtors:
        tg = "✅ в Telegram" if d['debtor_tg_id'] else "📱 только SMS"
        text += (
            f"🔹 <b>ID:{d['id']} {d['name']}</b>\n"
            f"   📱 {d['phone']}\n"
            f"   🛒 {d['product']}\n"
            f"   💰 {d['amount']} {d['currency']}\n"
            f"   📅 Срок: {d['due_date']}\n"
            f"   {tg}\n\n"
        )
    await message.answer(text, parse_mode="HTML")

@router.message(F.text.in_(["📊 Статистика", "📊 Омор"]))
async def stats(message: Message):
    active, closed, total = await get_stats()
    await message.answer(
        f"📊 <b>Статистика:</b>\n\n"
        f"🔴 Активных долгов: <b>{active}</b>\n"
        f"✅ Закрытых долгов: <b>{closed}</b>\n"
        f"💰 Общая сумма долгов: <b>{total:,.0f}</b>",
        parse_mode="HTML"
    )

@router.message(F.text.in_(["✅ Закрыть долг", "✅ Қарзро пӯшед"]))
async def start_close(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.set_state(CloseDebtForm.debtor_id)
    await message.answer(TEXTS[lang]["ask_id"])

@router.message(CloseDebtForm.debtor_id)
async def close_debt(message: Message, state: FSMContext):
    lang = await get_lang(message.from_user.id)
    await state.clear()
    try:
        debtor_id = int(message.text)
        await mark_paid(debtor_id)
        await message.answer(f"✅ {TEXTS[lang]['closed']} ID#{debtor_id}")
    except ValueError:
        await message.answer(TEXTS[lang]["wrong_id"])

# ========== ЗАПУСК ==========
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await init_db()
    scheduler = AsyncIOScheduler(timezone="Asia/Dushanbe")
    scheduler.add_job(check_due_debts, "cron", hour=9, minute=0, args=[bot])
    scheduler.start()
    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
