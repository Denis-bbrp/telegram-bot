import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_GROUP_ID = int(os.getenv("ADMIN_GROUP_ID", "0"))
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан. Создай файл .env и укажи токен бота.")
if not SPREADSHEET_ID:
    raise ValueError("SPREADSHEET_ID не задан. Создай файл .env и укажи ID таблицы.")
