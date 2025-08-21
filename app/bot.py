
import asyncio
import os
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

from .handlers import register_all_handlers
from .database import init_db
from .utils.scheduler import scheduler, schedule_all_reminders
from .utils.broadcast import process_scheduled_messages
# Получаем токен бота
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не найден в переменных окружения!")
    sys.exit(1)

# Создаем бота и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


async def on_startup():
    """Функция, выполняемая при запуске бота"""
    print("🚀 Запуск бота...")

    # Инициализируем базу данных
    await init_db()
    print("✅ База данных инициализирована")

    # Запускаем планировщик
    if not scheduler.running:
        scheduler.start()
        print("✅ Планировщик запущен")

    # Планируем напоминания
    await schedule_all_reminders()
    print("✅ Напоминания запланированы")

    # Добавляем задачу проверки запланированных сообщений каждую минуту
    scheduler.add_job(
        process_scheduled_messages,
        'interval',
        minutes=1,
        id='check_scheduled_messages'
    )
    print("✅ Задача проверки сообщений добавлена")

    print("🎉 Бот успешно запущен!")


async def on_shutdown():
    """Функция, выполняемая при остановке бота"""
    print("🛑 Остановка бота...")

    if scheduler.running:
        scheduler.shutdown()
        print("✅ Планировщик остановлен")

    await bot.session.close()
    print("✅ Сессия бота закрыта")
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