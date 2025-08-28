"""
Утилиты для рассылок
"""
import asyncio
from datetime import datetime
from typing import List, Tuple

from ..database import (
    get_all_users, save_scheduled_message,
    get_pending_scheduled_messages, delete_scheduled_message
)


async def send_broadcast_to_all_users(text: str, photo_id: str = None, admin_id: int = None) -> Tuple[int, int, List[int]]:
    """Отправить рассылку всем пользователям"""
    from app.bot import bot

    users = await get_all_users()
    success_count = 0
    error_count = 0
    blocked_users = []

    # Отправляем уведомление о начале рассылки
    if admin_id:
        try:
            start_message = f"📤 Начинаю рассылку...\n\n📊 Всего получателей: {len(users)}\n📝 Тип: {'С фото' if photo_id else 'Только текст'}"
            await bot.send_message(admin_id, start_message)
        except Exception:
            pass

    for i, user in enumerate(users, 1):
        try:
            if photo_id:
                await bot.send_photo(user['user_id'], photo_id, caption=text)
            else:
                await bot.send_message(user['user_id'], text)
            success_count += 1

            # Отправляем прогресс каждые 10 пользователей
            if admin_id and i % 10 == 0:
                try:
                    progress = f"📤 Прогресс: {i}/{len(users)} ({round(i/len(users)*100, 1)}%)"
                    await bot.send_message(admin_id, progress)
                except Exception:
                    pass

            await asyncio.sleep(0.1)  # Небольшая задержка между отправками
        except Exception as e:
            error_count += 1
            blocked_users.append(user['user_id'])
            # Не выводим ошибки в консоль, чтобы не засорять логи

    return success_count, error_count, blocked_users


async def send_scheduled_message(message_data: dict) -> bool:
    """Отправить запланированное сообщение"""
    from bot import bot

    try:
        if message_data['photo_id']:
            await bot.send_photo(message_data['user_id'], message_data['photo_id'], caption=message_data['text'])
        else:
            await bot.send_message(message_data['user_id'], message_data['text'])
        return True
    except Exception as e:
        # Не выводим ошибки в консоль, чтобы не засорять логи
        return False


async def schedule_message_for_user(user_id: int, text: str, photo_id: str = None, schedule_datetime: str = None) -> bool:
    """Запланировать сообщение для конкретного пользователя"""
    from utils.scheduler import scheduler

    if schedule_datetime:
        await save_scheduled_message(user_id, text, photo_id, schedule_datetime)
        # Добавляем задачу в планировщик
        job_id = f"scheduled_msg_{user_id}_{datetime.now().timestamp()}"
        schedule_time = datetime.strptime(schedule_datetime, '%Y-%m-%d %H:%M')
        scheduler.add_job(
            send_scheduled_message,
            'date',
            run_date=schedule_time,
            id=job_id,
            args=[{'user_id': user_id, 'text': text, 'photo_id': photo_id}]
        )
        return True
    return False


async def send_scheduled_broadcast_with_stats(text: str, photo_id: str = None, admin_id: int = None) -> Tuple[int, int, List[int]]:
    """Отправить запланированную рассылку с отправкой статистики админу"""
    from bot import bot

    success, errors, blocked_users = await send_broadcast_to_all_users(text, photo_id, admin_id)

    if admin_id:
        # Отправляем статистику запланированной рассылки
        scheduled_stats = f"""
📅 Запланированная рассылка выполнена!

📊 Результаты:
✅ Успешно отправлено: {success}
❌ Ошибок: {errors}
📈 Процент доставки: {round((success/(success+errors))*100, 1) if (success+errors) > 0 else 0}%

📝 Детали:
• Всего пользователей: {success + errors}
• Получили сообщение: {success}
• Не получили: {errors}

⏰ Время выполнения: {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""

        try:
            await bot.send_message(admin_id, scheduled_stats)
        except Exception:
            pass

        # Показываем заблокированных пользователей
        if blocked_users and len(blocked_users) <= 10:
            blocked_text = f"🚫 Заблокированные пользователи (первые 10):\n"
            for user_id in blocked_users[:10]:
                blocked_text += f"• {user_id}\n"
            try:
                await bot.send_message(admin_id, blocked_text)
            except Exception:
                pass
        elif blocked_users:
            try:
                await bot.send_message(admin_id, f"🚫 Заблокированных пользователей: {len(blocked_users)} (список скрыт)")
            except Exception:
                pass

    return success, errors, blocked_users


async def process_scheduled_messages():
    """Обработать все запланированные сообщения"""
    try:
        messages = await get_pending_scheduled_messages()
        for message in messages:
            sent = await send_scheduled_message(message)
            if sent:
                await delete_scheduled_message(message['id'])
            await asyncio.sleep(0.1)  # Небольшая задержка между отправками
    except Exception as e:
        print(f"❌ Ошибка при обработке запланированных сообщений: {e}")


async def check_scheduled_messages():
    """Проверить и обработать запланированные сообщения (для scheduler)"""
    await process_scheduled_messages()