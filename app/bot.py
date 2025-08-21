import asyncio
import pytz
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN
from database import init_db, get_all_users_with_notifications, get_pending_scheduled_messages
from utils import send_due_reminders, send_scheduled_message

# Инициализация компонентов
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Tashkent'))


@dp.startup()
async def on_startup(dispatcher):
    """Действия при запуске бота"""
    await init_db()

    if not scheduler.running:
        scheduler.start()

    await schedule_all_reminders()

    # Добавляем задачу проверки запланированных сообщений каждую минуту
    scheduler.add_job(
        check_scheduled_messages,
        'interval',
        minutes=1,
        id='check_scheduled_messages'
    )
    print("✅ Бот успешно запущен!")


async def schedule_all_reminders():
    """Обновить все напоминания в планировщике"""
    scheduler.remove_all_jobs()

    try:
        users = await get_all_users_with_notifications()
    except Exception as e:
        print(f"❌ Ошибка получения пользователей: {e}")
        return

    for user_info in users:
        notify_time = user_info.get('notify_time')
        if not notify_time:
            continue

        try:
            hour, minute = map(int, notify_time.split(':'))
        except Exception:
            continue

        # Уникальный ID задачи для каждого пользователя
        job_id = f'notify_{user_info["user_id"]}'

        # Удаляем старую задачу, если существует
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass

        # Добавляем новую задачу напоминания
        scheduler.add_job(
            send_due_reminders,
            'cron',
            hour=hour,
            minute=minute,
            id=job_id,
            args=[user_info["user_id"]]
        )

    print(f"📅 Запланировано {len(users)} напоминаний")


async def check_scheduled_messages():
    """Проверять запланированные сообщения каждую минуту"""
    await process_scheduled_messages()


async def process_scheduled_messages():
    """Обработать все запланированные сообщения"""
    try:
        messages = await get_pending_scheduled_messages()

        for message in messages:
            sent = await send_scheduled_message(message)
            if sent:
                # Используем soft delete вместо физического удаления
                from database import delete_scheduled_message
                await delete_scheduled_message(message['id'])

            await asyncio.sleep(0.1)  # Небольшая задержка между отправками

    except Exception as e:
        print(f"❌ Ошибка обработки запланированных сообщений: {e}")


async def main():
    """Основная функция запуска бота"""
    try:
        # Импортируем хендлеры
        from handlers import register_all_handlers

        # Регистрируем все хендлеры
        register_all_handlers(dp)

        # Запускаем бота
        await dp.start_polling(bot)

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())