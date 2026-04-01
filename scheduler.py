from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

from database import get_due_today, mark_notified
from notifications.sms_notify import send_sms
from config import ADMIN_ID

def start_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler(timezone="Asia/Bishkek")  # Измени на свой часовой пояс
    scheduler.add_job(check_due_debts, "cron", hour=9, minute=0, args=[bot])
    scheduler.start()
    print("⏰ Планировщик запущен")

async def check_due_debts(bot: Bot):
    """Проверяем должников каждый день в 9:00"""
    debtors = await get_due_today()

    if not debtors:
        return

    for debtor in debtors:
        message = (
            f"Здравствуйте, {debtor['name']}! "
            f"Напоминаем о долге: {debtor['amount']} сом за {debtor['product']}. "
            f"Пожалуйста, оплатите сегодня. Спасибо!"
        )

        # Отправляем SMS
        sms_sent = await send_sms(debtor['phone'], message)

        # Отмечаем что уведомление отправлено
        await mark_notified(debtor['id'])

        # Уведомляем продавца
        status = "✅ SMS отправлено" if sms_sent else "❌ SMS не отправлено"
        await bot.send_message(
            ADMIN_ID,
            f"📋 Уведомление должнику:\n"
            f"👤 {debtor['name']}\n"
            f"📱 {debtor['phone']}\n"
            f"🛒 {debtor['product']} — {debtor['amount']} сом\n"
            f"{status}"
        )
