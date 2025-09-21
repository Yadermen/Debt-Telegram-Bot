import asyncio
import os
import sys
import threading
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

from app.handlers import register_all_handlers
from app.database import init_db
from app.utils.scheduler import scheduler, schedule_all_reminders
from app.utils.broadcast import process_scheduled_messages
from app.config import BOT_TOKEN, DEBUG
from app.admin_panel import create_admin_app  # <-- импорт админки

logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)

if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не найден в переменных окружения!")
    sys.exit(1)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler.set_bot(bot)

@dp.errors()
async def error_handler(update, exception):
    print(f"[error_handler] update={update}, exception={exception}")
    print(f"❌ Ошибка в обработчике: {type(exception).__name__}: {exception}")
    if "IllegalStateChangeError" in str(exception):
        print("⚠️ Ошибка состояния SQLAlchemy - игнорируем")
        return True
    return True

async def on_startup():
    print("🚀 Запуск бота...")
    try:
        await init_db()
        print("✅ База данных инициализирована")
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        return

    try:
        if not scheduler.running:
            await scheduler.start()
            print("✅ Планировщик запущен")
    except Exception as e:
        print(f"❌ Ошибка запуска планировщика: {e}")

    try:
        await schedule_all_reminders()
        print("✅ Напоминания запланированы")
    except Exception as e:
        print(f"❌ Ошибка планирования напоминаний: {e}")

    try:
        scheduler.add_job(
            process_scheduled_messages,
            'interval',
            minutes=1,
            id='check_scheduled_messages'
        )
        print("✅ Задача проверки сообщений добавлена")
    except Exception as e:
        print(f"❌ Ошибка добавления задачи: {e}")

    print("🎉 Бот успешно запущен!")

async def on_shutdown():
    print("🛑 Остановка бота...")
    try:
        if scheduler.running:
            if hasattr(scheduler, 'stop'):
                await scheduler.stop()
            elif hasattr(scheduler.scheduler, 'shutdown'):
                scheduler.scheduler.stop()
            print("✅ Планировщик остановлен")
    except Exception as e:
        print(f"❌ Ошибка остановки планировщика: {e}")

    try:
        await bot.session.close()
        print("✅ Сессия бота закрыта")
    except Exception as e:
        print(f"❌ Ошибка закрытия сессии бота: {e}")

    print("👋 Бот остановлен!")

# --- добавлено ---
def run_admin():
    """Запуск Flask-Admin в отдельном потоке"""
    app = create_admin_app()
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)
# -----------------

async def main():
    # --- добавлено ---
    threading.Thread(target=run_admin, daemon=True).start()
    # -----------------

    register_all_handlers(dp)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка при запуске: {e}")
        sys.exit(1)
