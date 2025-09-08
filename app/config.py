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

# Admin Panel configuration
ADMIN_HOST = os.getenv("ADMIN_HOST", "0.0.0.0")
ADMIN_PORT = int(os.getenv("ADMIN_PORT", "8080"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "your-admin-secret-key-change-me")

# Настройки безопасности админки
ADMIN_SESSION_TIMEOUT = int(os.getenv("ADMIN_SESSION_TIMEOUT", "24"))  # в часах
ADMIN_ENABLE_EXPORT = os.getenv("ADMIN_ENABLE_EXPORT", "True").lower() == "true"
ADMIN_MAX_EXPORT_ROWS = int(os.getenv("ADMIN_MAX_EXPORT_ROWS", "1000"))

# Настройки отображения админки
ADMIN_PAGE_SIZE = int(os.getenv("ADMIN_PAGE_SIZE", "25"))
ADMIN_THEME = os.getenv("ADMIN_THEME", "cerulean")  # Bootstrap theme

# Отладка
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ADMIN_DEBUG = os.getenv("ADMIN_DEBUG", "False").lower() == "true"

# Настройки логирования
LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING")

# Дополнительные настройки админки
ADMIN_AUTO_START = os.getenv("ADMIN_AUTO_START", "True").lower() == "true"  # Автозапуск с ботом
ADMIN_ALLOWED_IPS = [ip.strip() for ip in os.getenv("ADMIN_ALLOWED_IPS", "").split(",") if ip.strip()]  # Ограничение по IP