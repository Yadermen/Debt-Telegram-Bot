import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS: List[int] = [
    int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()
]

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "debt_bot")
DB_USER = os.getenv("DB_USER", "bot_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "secure_password_123")

# Асинхронное подключение (для бота)
DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"postgresql+asyncpg://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Синхронное подключение (для админки)
SYNC_DATABASE_URL = os.getenv("SYNC_DATABASE_URL") or (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

DB_PATH = 'app/debts.db'
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
