# app/config.py
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

# Bot configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS: List[int] = [int(id.strip()) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip()]

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL")
DB_PATH = 'app/debts.db'  # Fallback для SQLite

# PostgreSQL настройки (если нужны отдельно)
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "debt_bot")
DB_USER = os.getenv("DB_USER", "bot_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "secure_password_123")

# Отладка
DEBUG = os.getenv("DEBUG", "False").lower() == "true"