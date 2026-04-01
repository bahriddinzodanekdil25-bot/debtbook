import aiohttp
from config import SMSC_LOGIN, SMSC_PASSWORD

async def send_sms(phone: str, message: str) -> bool:
    """Отправка SMS через SMSC.ru"""
    # Убираем лишние символы из номера
    phone = phone.replace("+", "").replace("-", "").replace(" ", "").replace("(", "").replace(")", "")

    url = "https://smsc.ru/sys/send.php"
    params = {
        "login": SMSC_LOGIN,
        "psw": SMSC_PASSWORD,
        "phones": phone,
        "mes": message,
        "charset": "utf-8",
        "fmt": 3  # JSON ответ
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                result = await response.json(content_type=None)
                if "error" in result:
                    print(f"❌ Ошибка SMS для {phone}: {result}")
                    return False
                print(f"✅ SMS отправлено на {phone}")
                return True
    except Exception as e:
        print(f"❌ Исключение при отправке SMS: {e}")
        return False
