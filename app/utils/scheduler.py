"""
Планировщик задач для уведомлений и рассылок
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
from ..database import get_all_users, get_due_debts, get_user_data
from ..keyboards import tr
from ..database.models import safe_str
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Создаем глобальный планировщик
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Tashkent'))


async def send_due_reminders(user_id: int):
    """Отправить напоминания о долгах пользователю"""
    from bot import bot

    try:
        user_data = await get_user_data(user_id)
    except Exception:
        return

    notify_time = user_data.get('notify_time', '09:00')

    # Долги, срок которых истекает завтра
    try:
        tomorrow_debts = await get_due_debts(user_id, 1)
    except Exception:
        tomorrow_debts = []

    for debt in tomorrow_debts:
        text = await tr(
            user_id, 'debt_card',
            person=safe_str(debt['person']),
            amount=safe_str(debt['amount']),
            currency=safe_str(debt.get('currency', 'UZS')),
            due=safe_str(debt['due']),
            comment=safe_str(debt['comment']),
            notify_time=safe_str(notify_time)
        )
        try:
            kb = await reminder_debt_actions(debt['id'], 0, user_id)
            await bot.send_message(user_id, text, reply_markup=kb)
        except Exception:
            pass

    # Долги, срок которых истекает сегодня
    try:
        today_debts = await get_due_debts(user_id, 0)
    except Exception:
        today_debts = []

    for debt in today_debts:
        text = await tr(
            user_id, 'debt_card',
            person=safe_str(debt['person']),
            amount=safe_str(debt['amount']),
            currency=safe_str(debt.get('currency', 'UZS')),
            due=safe_str(debt['due']),
            comment=safe_str(debt['comment']),
            notify_time=safe_str(notify_time)
        )
        try:
            kb = await reminder_debt_actions(debt['id'], 0, user_id)
            await bot.send_message(user_id, text, reply_markup=kb)
        except Exception:
            pass


async def reminder_debt_actions(debt_id: int, page: int, user_id: int) -> InlineKeyboardMarkup:
    """Кнопки для карточки долга в напоминаниях"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await tr(user_id, 'edit'),
            callback_data=f'edit_{debt_id}_{page}'
        )],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'close'),
                callback_data=f'close_{debt_id}_{page}'
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'extend'),
                callback_data=f'extend_{debt_id}_{page}'
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'delete'),
                callback_data=f'del_{debt_id}_{page}'
            )
        ],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_menu'),
            callback_data='back_main'
        )]
    ])


async def schedule_all_reminders():
    """Запланировать напоминания для всех пользователей"""
    try:
        # Очищаем существующие задачи напоминаний
        for job in scheduler.get_jobs():
            if job.id.startswith('reminder_'):
                job.remove()

        # Получаем всех пользователей
        users = await get_all_users()

        for user in users:
            user_id = user['user_id']
            notify_time = user.get('notify_time', '09:00')

            # Парсим время
            try:
                hour, minute = map(int, notify_time.split(':'))
            except ValueError:
                hour, minute = 9, 0  # Значение по умолчанию

            # Добавляем задачу для каждого пользователя
            scheduler.add_job(
                send_due_reminders,
                'cron',
                hour=hour,
                minute=minute,
                args=[user_id],
                id=f'reminder_{user_id}',
                replace_existing=True
            )

        print(f"✅ Запланировано напоминаний для {len(users)} пользователей")

    except Exception as e:
        print(f"❌ Ошибка при планировании напоминаний: {e}")


async def schedule_user_reminder(user_id: int, notify_time: str):
    """Запланировать напоминание для конкретного пользователя"""
    try:
        # Парсим время
        hour, minute = map(int, notify_time.split(':'))

        # Добавляем или обновляем задачу
        scheduler.add_job(
            send_due_reminders,
            'cron',
            hour=hour,
            minute=minute,
            args=[user_id],
            id=f'reminder_{user_id}',
            replace_existing=True
        )

        print(f"✅ Напоминание для пользователя {user_id} запланировано на {notify_time}")

    except Exception as e:
        print(f"❌ Ошибка при планировании напоминания для {user_id}: {e}")


def remove_user_reminder(user_id: int):
    """Удалить напоминание пользователя"""
    try:
        job = scheduler.get_job(f'reminder_{user_id}')
        if job:
            job.remove()
            print(f"✅ Напоминание для пользователя {user_id} удалено")
    except Exception as e:
        print(f"❌ Ошибка при удалении напоминания для {user_id}: {e}")