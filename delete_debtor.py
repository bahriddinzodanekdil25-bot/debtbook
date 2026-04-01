from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import mark_paid, delete_debtor

router = Router()

class CloseDebtForm(StatesGroup):
    debtor_id = State()

@router.message(F.text == "✅ Закрыть долг")
async def start_close(message: Message, state: FSMContext):
    await state.set_state(CloseDebtForm.debtor_id)
    await message.answer(
        "Введите ID должника из списка.\n"
        "Чтобы посмотреть ID — нажмите 📋 Список должников"
    )

@router.message(CloseDebtForm.debtor_id)
async def close_debt(message: Message, state: FSMContext):
    await state.clear()
    try:
        debtor_id = int(message.text)
        await mark_paid(debtor_id)
        await message.answer(f"✅ Долг #{debtor_id} закрыт! Должник удалён из активных.")
    except ValueError:
        await message.answer("❌ Введите только номер ID!")
