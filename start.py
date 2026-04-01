from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

router = Router()

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Добавить должника")],
        [KeyboardButton(text="📋 Список должников")],
        [KeyboardButton(text="✅ Закрыть долг")],
    ],
    resize_keyboard=True
)

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Добро пожаловать в *Книгу долгов*!\n\n"
        "Здесь вы можете:\n"
        "• Добавлять должников\n"
        "• Следить за сроками\n"
        "• Автоматически отправлять SMS напоминания\n\n"
        "Выберите действие 👇",
        reply_markup=main_keyboard,
        parse_mode="Markdown"
    )
