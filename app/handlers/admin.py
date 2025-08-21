"""
Админ панель для управления ботом
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime
import os

from database import (
    get_all_users, get_user_count, get_active_debts_count,
    save_scheduled_message
)
from states import AdminBroadcast
from utils.broadcast import send_broadcast_to_all_users, send_scheduled_broadcast_with_stats
from utils.scheduler import scheduler

router = Router()

# ID администраторов из переменных окружения
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '').split(','))) if os.getenv('ADMIN_IDS') else []


def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


@router.message(Command('admin'))
async def admin_panel(message: Message, state: FSMContext):
    """Админ панель"""
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к админ панели.")
        return

    user_count = await get_user_count()
    active_debts = await get_active_debts_count()

    stats_text = f"📊 Статистика бота:\n👥 Пользователей: {user_count}\n📄 Активных долгов: {active_debts}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👥 Список пользователей ({user_count})", callback_data="admin_users")],
        [InlineKeyboardButton(text="📢 Отправить рассылку", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])

    await message.answer(stats_text, reply_markup=kb)


@router.callback_query(F.data == "admin_users")
async def admin_users_list(call: CallbackQuery):
    """Список пользователей"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return

    users = await get_all_users()
    if not users:
        await call.message.edit_text("Пользователей пока нет.")
        return

    # Показываем первые 10 пользователей
    text = "👥 Список пользователей:\n\n"
    for i, user in enumerate(users[:10], 1):
        text += f"{i}. ID: {user['user_id']}\n"
        text += f"   Язык: {user.get('lang', 'ru')}\n"
        text += f"   Напоминания: {user.get('notify_time', '09:00')}\n"
        text += f"   Активных долгов: {user.get('active_debts', 0)}\n"
        text += f"   Всего долгов: {user.get('total_debts', 0)}\n\n"

    if len(users) > 10:
        text += f"... и еще {len(users) - 10} пользователей"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_back")]
    ])

    await call.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(call: CallbackQuery, state: FSMContext):
    """Начать создание рассылки"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return

    await state.set_state(AdminBroadcast.waiting_for_text)
    await call.message.edit_text(
        "📢 Создание рассылки\n\n"
        "Отправьте текст сообщения для рассылки всем пользователям:"
    )


@router.message(AdminBroadcast.waiting_for_text)
async def admin_broadcast_text(message: Message, state: FSMContext):
    """Получить текст для рассылки"""
    if not is_admin(message.from_user.id):
        return

    await state.update_data(broadcast_text=message.text)
    await state.set_state(AdminBroadcast.waiting_for_photo)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📷 Добавить фото", callback_data="add_photo")],
        [InlineKeyboardButton(text="📤 Отправить без фото", callback_data="send_without_photo")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_back")]
    ])

    await message.answer(
        f"📢 Текст рассылки:\n\n{message.text}\n\n"
        "Хотите добавить фото к сообщению?",
        reply_markup=kb
    )


@router.callback_query(F.data == "add_photo", AdminBroadcast.waiting_for_photo)
async def admin_broadcast_add_photo(call: CallbackQuery, state: FSMContext):
    """Добавить фото к рассылке"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return

    if call.message.photo:
        await call.message.edit_caption(caption="📷 Отправьте фото для рассылки:")
    else:
        await call.message.edit_text("📷 Отправьте фото для рассылки:")


@router.message(AdminBroadcast.waiting_for_photo, F.photo)
async def admin_broadcast_photo(message: Message, state: FSMContext):
    """Получить фото для рассылки"""
    if not is_admin(message.from_user.id):
        return

    photo_id = message.photo[-1].file_id
    data = await state.get_data()
    text = data['broadcast_text']

    await state.update_data(broadcast_photo=photo_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Отправить сейчас", callback_data="send_broadcast_now")],
        [InlineKeyboardButton(text="⏰ Запланировать", callback_data="schedule_broadcast")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_back")]
    ])

    await message.answer_photo(
        photo_id,
        caption=f"📢 Рассылка с фото:\n\n{text}\n\nВыберите действие:",
        reply_markup=kb
    )


@router.callback_query(F.data == "send_without_photo", AdminBroadcast.waiting_for_photo)
async def admin_broadcast_no_photo(call: CallbackQuery, state: FSMContext):
    """Отправить рассылку без фото"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return

    data = await state.get_data()
    text = data['broadcast_text']

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Отправить сейчас", callback_data="send_broadcast_now_no_photo")],
        [InlineKeyboardButton(text="⏰ Запланировать", callback_data="schedule_broadcast")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_back")]
    ])

    if call.message.photo:
        await call.message.edit_caption(
            caption=f"📢 Рассылка без фото:\n\n{text}\n\nВыберите действие:",
            reply_markup=kb
        )
    else:
        await call.message.edit_text(
            f"📢 Рассылка без фото:\n\n{text}\n\nВыберите действие:",
            reply_markup=kb
        )


@router.callback_query(F.data == "send_broadcast_now")
async def admin_broadcast_send_now(call: CallbackQuery, state: FSMContext):
    """Отправить рассылку сейчас"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return

    data = await state.get_data()
    text = data['broadcast_text']
    photo_id = data.get('broadcast_photo')
    admin_id = call.from_user.id

    if call.message.photo:
        await call.message.edit_caption(caption="📤 Отправка рассылки...")
    else:
        await call.message.edit_text("📤 Отправка рассылки...")

    success, errors, blocked_users = await send_broadcast_to_all_users(text, photo_id, admin_id)

    result_text = f"✅ Рассылка завершена!\n\n📊 Результаты:\n✅ Успешно отправлено: {success}\n❌ Ошибок: {errors}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_back")]
    ])

    if call.message.photo:
        await call.message.edit_caption(caption=result_text, reply_markup=kb)
    else:
        await call.message.edit_text(result_text, reply_markup=kb)

    await _send_detailed_stats(admin_id, success, errors, blocked_users)
    await state.clear()


@router.callback_query(F.data == "send_broadcast_now_no_photo")
async def admin_broadcast_send_now_no_photo(call: CallbackQuery, state: FSMContext):
    """Отправить рассылку без фото сейчас"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return

    data = await state.get_data()
    text = data['broadcast_text']
    admin_id = call.from_user.id

    await call.message.edit_text("📤 Отправка рассылки...")

    success, errors, blocked_users = await send_broadcast_to_all_users(text, None, admin_id)

    result_text = f"✅ Рассылка завершена!\n\n📊 Результаты:\n✅ Успешно отправлено: {success}\n❌ Ошибок: {errors}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_back")]
    ])

    await call.message.edit_text(result_text, reply_markup=kb)
    await _send_detailed_stats(admin_id, success, errors, blocked_users)
    await state.clear()


@router.callback_query(F.data == "schedule_broadcast")
async def admin_broadcast_schedule(call: CallbackQuery, state: FSMContext):
    """Запланировать рассылку"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return

    await state.set_state(AdminBroadcast.waiting_for_schedule_time)

    if call.message.photo:
        await call.message.edit_caption(
            caption="⏰ Планирование рассылки\n\nВведите дату и время отправки в формате:\nYYYY-MM-DD HH:MM\n\nНапример: 2024-01-15 14:30"
        )
    else:
        await call.message.edit_text(
            "⏰ Планирование рассылки\n\n"
            "Введите дату и время отправки в формате:\n"
            "YYYY-MM-DD HH:MM\n\n"
            "Например: 2024-01-15 14:30"
        )


@router.message(AdminBroadcast.waiting_for_schedule_time)
async def admin_broadcast_schedule_time(message: Message, state: FSMContext):
    """Получить время для планирования рассылки"""
    if not is_admin(message.from_user.id):
        return

    try:
        schedule_time = datetime.strptime(message.text, '%Y-%m-%d %H:%M')
        if schedule_time <= datetime.now():
            await message.answer("❌ Время должно быть в будущем!")
            return
    except ValueError:
        await message.answer("❌ Неверный формат даты! Используйте: YYYY-MM-DD HH:MM")
        return

    data = await state.get_data()
    text = data['broadcast_text']
    photo_id = data.get('broadcast_photo')

    # Сохраняем запланированную рассылку для всех пользователей
    users = await get_all_users()
    for user in users:
        await save_scheduled_message(user['user_id'], text, photo_id, schedule_time.strftime('%Y-%m-%d %H:%M'))

    # Добавляем задачу в планировщик
    job_id = f"broadcast_{datetime.now().timestamp()}"
    scheduler.add_job(
        send_scheduled_broadcast_with_stats,
        'date',
        run_date=schedule_time,
        id=job_id,
        args=[text, photo_id, message.from_user.id]
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_back")]
    ])

    confirm_text = f"✅ Рассылка запланирована на {schedule_time.strftime('%d.%m.%Y %H:%M')}\nПолучателей: {len(users)}"
    await message.answer(confirm_text, reply_markup=kb)

    await _send_planning_stats(message.from_user.id, schedule_time, len(users), bool(photo_id))
    await state.clear()


@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    """Показать статистику"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return

    user_count = await get_user_count()
    active_debts = await get_active_debts_count()

    stats_text = f"""
📊 Статистика бота:

👥 Пользователей: {user_count}
📄 Активных долгов: {active_debts}
"""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_back")]
    ])

    await call.message.edit_text(stats_text, reply_markup=kb)


@router.callback_query(F.data == "admin_back")
async def admin_back(call: CallbackQuery, state: FSMContext):
    """Вернуться в админ панель"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return

    await state.clear()
    user_count = await get_user_count()
    active_debts = await get_active_debts_count()

    stats_text = f"📊 Статистика бота:\n👥 Пользователей: {user_count}\n📄 Активных долгов: {active_debts}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👥 Список пользователей ({user_count})", callback_data="admin_users")],
        [InlineKeyboardButton(text="📢 Отправить рассылку", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])

    if call.message.photo:
        await call.message.edit_caption(caption=stats_text, reply_markup=kb)
    else:
        await call.message.edit_text(stats_text, reply_markup=kb)


async def _send_detailed_stats(admin_id: int, success: int, errors: int, blocked_users: list):
    """Отправить подробную статистику рассылки"""
    from bot import bot

    detailed_stats = f"""
📢 Статистика рассылки

📊 Общие результаты:
✅ Успешно отправлено: {success}
❌ Ошибок: {errors}
📈 Процент доставки: {round((success / (success + errors)) * 100, 1) if (success + errors) > 0 else 0}%

📝 Детали:
• Всего пользователей в базе: {success + errors}
• Получили сообщение: {success}
• Не получили (заблокировали/удалили бота): {errors}

⏰ Время отправки: {datetime.now().strftime('%d.%m.%Y %H:%M')}
"""

    try:
        await bot.send_message(admin_id, detailed_stats)
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


async def _send_planning_stats(admin_id: int, schedule_time: datetime, user_count: int, has_photo: bool):
    """Отправить статистику планирования"""
    from bot import bot

    planning_stats = f"""
📅 Планирование рассылки

📊 Детали планирования:
• Дата и время: {schedule_time.strftime('%d.%m.%Y %H:%M')}
• Получателей: {user_count}
• Тип сообщения: {'С фото' if has_photo else 'Только текст'}

📝 Напоминание:
• Рассылка будет отправлена автоматически
• Статистика доставки будет доступна после отправки
• Время по часовому поясу: Asia/Tashkent
"""

    try:
        await bot.send_message(admin_id, planning_stats)
    except Exception:
        pass