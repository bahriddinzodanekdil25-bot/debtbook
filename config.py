import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН_БОТА")
SMSC_LOGIN = os.getenv("SMSC_LOGIN", "ВАШ_ЛОГИН")
SMSC_PASSWORD = os.getenv("SMSC_PASSWORD", "ВАШ_ПАРОЛЬ")

# ID продавца (твой Telegram ID) - получи через @userinfobot
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
