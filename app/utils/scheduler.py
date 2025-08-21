
import asyncio
from typing import Dict, Any
from aiogram.exceptions import TelegramAPIError

from database import get_due_debts, mark_message_as_sent


async def send_due_reminders(user_id: int):
    """Отправить напоминания о просроченных долгах"""
    try:
        from bot import bot  # Импортируем бота

        # Получаем долги, которые истекают сегодня (0 дней)
        due_debts = await get_due_debts(user_id, 0)

        if not due_debts:
            return

        # Формируем сообщение с напоминанием
        reminder_text = "🔔 <b>Напоминание о долгах!</b>\n\n"
        reminder_text += f"Сегодня истекает срок по {len(due_debts)} долг(ам):\n\n"

        for debt in due_debts:
            direction_text = "💰 Вам должны" if debt['direction'] == 'owed' else "⚠️ Вы должны"
            reminder_text += f"{direction_text} <b>{debt['person']}</b>\n"
            reminder_text += f"Сумма: {debt['amount']} {debt['currency']}\n"
            if debt['comment']:
                reminder_text += f"Комментарий: {debt['comment']}\n"
            reminder_text += "\n"

        await bot.send_message(user_id, reminder_text, parse_mode='HTML')

    except Exception as e:
        print(f"❌ Ошибка отправки напоминания пользователю {user_id}: {e}")


async def send_scheduled_message(message: Dict[str, Any]) -> bool:
    """Отправить запланированное сообщение"""
    try:
        from bot import bot  # Импортируем бота

        user_id = message['user_id']
        text = message['text']
        photo_id = message.get('photo_id')

        if photo_id:
            # Отправляем сообщение с фото
            await bot.send_photo(
                chat_id=user_id,
                photo=photo_id,
                caption=text,
                parse_mode='HTML'
            )
        else:
            # Отправляем текстовое сообщение
            await bot.send_message(
                chat_id=user_id,
                text=text,
                parse_mode='HTML'
            )

        # Помечаем сообщение как отправленное
        await mark_message_as_sent(message['id'])

        return True

    except TelegramAPIError as e:
        print(f"❌ Telegram API ошибка при отправке сообщения {message['id']}: {e}")
        return False
    except Exception as e:
        print(f"❌ Общая ошибка при отправке сообщения {message['id']}: {e}")
        return False