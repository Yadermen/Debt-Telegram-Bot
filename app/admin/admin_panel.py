import asyncio
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv
import logging
from threading import Thread

load_dotenv()

from .handlers import register_all_handlers
from .database import init_db
from .utils.scheduler import scheduler, schedule_all_reminders
from .utils.broadcast import process_scheduled_messages
from .config import (
    ADMIN_HOST, ADMIN_PORT, ADMIN_USERNAME, ADMIN_PASSWORD,
    ADMIN_AUTO_START, ADMIN_ALLOWED_IPS
)

# Импорт админки
try:
    from .admin.admin_panel import start_admin_in_background

    ADMIN_AVAILABLE = True
    print("✅ Модуль админки загружен")
except ImportError as e:
    print(f"⚠️ Админка недоступна: {e}")
    ADMIN_AVAILABLE = False

# Настройка логирования для отслеживания ошибок SQLAlchemy
logging.basicConfig(
    level=logging.WARNING,  # Показывать только предупреждения и ошибки
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Скрываем избыточные логи SQLAlchemy
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)

# Получаем токен бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не найден в переменных окружения!")
    sys.exit(1)

# Создаем бота и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

scheduler.set_bot(bot)


# Добавляем глобальный обработчик ошибок
@dp.errors()
async def error_handler(event, exception):
    """Глобальный обработчик ошибок"""
    # Логируем ошибку
    print(f"❌ Ошибка в обработчике: {type(exception).__name__}: {exception}")

    # Для ошибок SQLAlchemy пытаемся продолжить работу
    if "IllegalStateChangeError" in str(exception):
        print("⚠️ Ошибка состояния SQLAlchemy - игнорируем")
        return True  # Продолжаем работу

    # Для других критических ошибок логируем и продолжаем
    return True


async def on_startup():
    """Функция, выполняемая при запуске бота"""
    print("🚀 Запуск бота...")

    try:
        # Инициализируем базу данных
        await init_db()
        print("✅ База данных инициализирована")
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        return

    try:
        # Запускаем планировщик
        if not scheduler.running:
            await scheduler.start()
            print("✅ Планировщик запущен")
    except Exception as e:
        print(f"❌ Ошибка запуска планировщика: {e}")

    try:
        # Планируем напоминания
        await schedule_all_reminders()
        print("✅ Напоминания запланированы")
    except Exception as e:
        print(f"❌ Ошибка планирования напоминаний: {e}")

    try:
        # Добавляем задачу проверки запланированных сообщений каждую минуту
        scheduler.add_job(
            process_scheduled_messages,
            'interval',
            minutes=1,
            id='check_scheduled_messages'
        )
        print("✅ Задача проверки сообщений добавлена")
    except Exception as e:
        print(f"❌ Ошибка добавления задачи: {e}")

    # Запуск админки в фоновом режиме
    if ADMIN_AVAILABLE and ADMIN_AUTO_START:
        try:
            admin_thread = start_admin_in_background()
            if admin_thread:
                print("✅ Админка запущена в фоновом режиме")

                print("=" * 50)
                print("🔧 ИНФОРМАЦИЯ О АДМИНКЕ")
                print("=" * 50)
                print(f"🌐 URL: http://{ADMIN_HOST}:{ADMIN_PORT}/admin")
                print(f"👤 Логин: {ADMIN_USERNAME}")
                print(f"🔑 Пароль: {ADMIN_PASSWORD}")
                if ADMIN_ALLOWED_IPS:
                    print(f"🛡️ Разрешенные IP: {', '.join(ADMIN_ALLOWED_IPS)}")
                print("=" * 50)
            else:
                print("⚠️ Админка не запущена (автозапуск отключен)")

        except Exception as e:
            print(f"❌ Ошибка запуска админки: {e}")
    else:
        if not ADMIN_AVAILABLE:
            print("⚠️ Админка не запущена (модуль недоступен)")
        elif not ADMIN_AUTO_START:
            print("⚠️ Админка не запущена (автозапуск отключен в config.py)")

    print("🎉 Бот успешно запущен!")


async def on_shutdown():
    """Функция, выполняемая при остановке бота"""
    print("🛑 Остановка бота...")

    try:
        # Исправляем вызов shutdown для scheduler
        if scheduler.running:
            # Используем правильный метод для остановки планировщика
            if hasattr(scheduler, 'stop'):
                await scheduler.stop()
            elif hasattr(scheduler.scheduler, 'shutdown'):
                scheduler.scheduler.stop()
            else:
                print("⚠️ Не удалось найти метод остановки планировщика")
            print("✅ Планировщик остановлен")
    except Exception as e:
        print(f"❌ Ошибка остановки планировщика: {e}")

    try:
        await bot.session.close()
        print("✅ Сессия бота закрыта")
    except Exception as e:
        print(f"❌ Ошибка закрытия сессии бота: {e}")

    print("👋 Бот остановлен!")


async def main():
    """Главная функция"""
    try:
        # Регистрируем хендлеры
        register_all_handlers(dp)

        # Устанавливаем функции запуска/остановки
        dp.startup.register(on_startup)
        dp.shutdown.register(on_shutdown)

        # Запускаем polling
        await dp.start_polling(bot)

    except KeyboardInterrupt:
        print("🛑 Получен сигнал остановки (Ctrl+C)")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
    finally:
        await on_shutdown()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Ошибка при запуске: {e}")
        sys.exit(1)