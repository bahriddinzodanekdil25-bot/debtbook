import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from handlers import add_debtor, list_debtors, delete_debtor, start
from scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрируем хэндлеры
    dp.include_router(start.router)
    dp.include_router(add_debtor.router)
    dp.include_router(list_debtors.router)
    dp.include_router(delete_debtor.router)

    # Инициализируем базу данных
    await init_db()

    # Запускаем планировщик
    start_scheduler(bot)

    print("✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
