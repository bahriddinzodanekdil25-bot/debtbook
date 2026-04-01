from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from database import add_debtor

router = Router()

class AddDebtorForm(StatesGroup):
    name = State()
    phone = State()
    product = State()
    amount = State()
    due_date = State()

@router.message(F.text == "➕ Добавить должника")
async def start_add(message: Message, state: FSMContext):
    await state.set_state(AddDebtorForm.name)
    await message.answer("👤 Введите имя должника:")

@router.message(AddDebtorForm.name)
async def get_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(AddDebtorForm.phone)
    await message.answer("📱 Введите номер телефона:\n(например: +79001234567)")

@router.message(AddDebtorForm.phone)
async def get_phone(message: Message, state: FSMContext):
    await state.update_data(phone=message.text)
    await state.set_state(AddDebtorForm.product)
    await message.answer("🛒 Что взял в долг? (название товара):")

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
        await message.answer("📅 Дата возврата долга:\n(формат: ДД.ММ.ГГГГ, например 15.04.2026)")
    except ValueError:
        await message.answer("❌ Введите только число! Например: 5000")

@router.message(AddDebtorForm.due_date)
async def get_due_date(message: Message, state: FSMContext):
    try:
        due_date = datetime.strptime(message.text, "%d.%m.%Y").date().isoformat()
        data = await state.get_data()
        await state.clear()

        await add_debtor(
            name=data['name'],
            phone=data['phone'],
            product=data['product'],
            amount=data['amount'],
            due_date=due_date
        )

        await message.answer(
            f"✅ *Должник добавлен!*\n\n"
            f"👤 Имя: {data['name']}\n"
            f"📱 Телефон: {data['phone']}\n"
            f"🛒 Товар: {data['product']}\n"
            f"💰 Сумма: {data['amount']} сом\n"
            f"📅 Срок: {message.text}\n\n"
            f"SMS будет отправлено автоматически в день срока в 9:00",
            parse_mode="Markdown"
        )
    except ValueError:
        await message.answer("❌ Неверный формат даты! Введите в формате ДД.ММ.ГГГГ\nНапример: 15.04.2026")
