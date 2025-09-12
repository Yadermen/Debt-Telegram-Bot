from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime
import os
import asyncio

# Исправленные импорты
from app.database import (
    get_all_users, get_user_count, get_active_debts_count,
    save_scheduled_message
)
from app.states import AdminBroadcast
from app.utils.broadcast import send_broadcast_to_all_users, send_scheduled_broadcast_with_stats

router = Router()

# ID администраторов из переменных окружения
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '').split(','))) if os.getenv('ADMIN_IDS') else []


def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь администратором"""
    return user_id in ADMIN_IDS


async def get_admin_stats_safely():
    """Безопасно получить статистику для админ панели"""
    try:
        # Получаем статистику с повторными попытками
        user_count = 0
        active_debts = 0

        for attempt in range(3):
            try:
                user_count = await get_user_count()
                break
            except Exception as e:
                if attempt == 2:  # Последняя попытка
                    print(f"❌ Не удалось получить количество пользователей: {e}")
                    user_count = 0
                else:
                    await asyncio.sleep(0.1)

        for attempt in range(3):
            try:
                active_debts = await get_active_debts_count()
                break
            except Exception as e:
                if attempt == 2:  # Последняя попытка
                    print(f"❌ Не удалось получить количество долгов: {e}")
                    active_debts = 0
                else:
                    await asyncio.sleep(0.1)

        return user_count, active_debts
    except Exception as e:
        print(f"❌ Критическая ошибка получения статистики: {e}")
        return 0, 0


@router.message(Command('admin'))
async def admin_panel(message: Message, state: FSMContext):
    """Админ панель"""
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет доступа к админ панели.")
        return

    # Безопасно получаем статистику
    user_count, active_debts = await get_admin_stats_safely()

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

    try:
        users = await get_all_users()
        if not users:
            await call.message.edit_text("Пользователей пока нет.")
            return

        # Показываем первые 10 пользователей
        text = "👥 Список пользователей:\n\n"
        for i, user in enumerate(users[:10], 1):
            text += f"{i}. ID: {user['user_id']}\n"
            text += f"   Язык: {user.get('lang', 'ru')}\n"
            text += f"   Напоминания: {user.get('notify_time', '09:00')}\n\n"

        if len(users) > 10:
            text += f"... и еще {len(users) - 10} пользователей"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_back")]
        ])

        await call.message.edit_text(text, reply_markup=kb)

    except Exception as e:
        print(f"❌ Ошибка получения списка пользователей: {e}")
        await call.message.edit_text(
            "❌ Ошибка получения списка пользователей",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
            ])
        )


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

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📷 Добавить картинку", callback_data="add_broadcast_photo")],
        [InlineKeyboardButton(text="📤 Отправить сейчас", callback_data="send_broadcast_now")],
        [InlineKeyboardButton(text="⏰ Запланировать", callback_data="schedule_broadcast")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_back")]
    ])

    await message.answer(
        f"📢 Текст рассылки:\n\n{message.text}\n\n"
        "Выберите действие:",
        reply_markup=kb
    )


@router.callback_query(F.data == "add_broadcast_photo")
async def admin_broadcast_add_photo(call: CallbackQuery, state: FSMContext):
    """Добавить картинку к рассылке"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return

    await state.set_state(AdminBroadcast.waiting_for_photo)
    await call.message.edit_text(
        "📷 Добавление картинки\n\n"
        "Отправьте картинку для рассылки:"
    )


@router.message(AdminBroadcast.waiting_for_photo, F.photo)
async def admin_broadcast_photo(message: Message, state: FSMContext):
    """Получить картинку для рассылки"""
    if not is_admin(message.from_user.id):
        return

    photo_id = message.photo[-1].file_id  # Берем фото лучшего качества
    await state.update_data(broadcast_photo=photo_id)

    data = await state.get_data()
    text = data.get('broadcast_text', '')

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Отправить сейчас", callback_data="send_broadcast_now")],
        [InlineKeyboardButton(text="⏰ Запланировать", callback_data="schedule_broadcast")],
        [InlineKeyboardButton(text="🔄 Изменить картинку", callback_data="add_broadcast_photo")],
        [InlineKeyboardButton(text="🗑 Убрать картинку", callback_data="remove_broadcast_photo")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_back")]
    ])

    try:
        await message.answer_photo(
            photo_id,
            caption=f"📢 Рассылка с картинкой:\n\n{text}\n\n✅ Картинка добавлена! Выберите действие:",
            reply_markup=kb
        )
    except Exception as e:
        print(f"❌ Ошибка отправки превью: {e}")
        await message.answer(
            f"📢 Рассылка с картинкой:\n\n{text}\n\n✅ Картинка добавлена! Выберите действие:",
            reply_markup=kb
        )


@router.message(AdminBroadcast.waiting_for_photo)
async def admin_broadcast_photo_invalid(message: Message, state: FSMContext):
    """Неправильный тип файла для картинки"""
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "❌ Отправьте картинку (фото)!\n\n"
        "Поддерживаются только изображения."
    )


@router.callback_query(F.data == "remove_broadcast_photo")
async def admin_broadcast_remove_photo(call: CallbackQuery, state: FSMContext):
    """Убрать картинку из рассылки"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return

    await state.update_data(broadcast_photo=None)
    data = await state.get_data()
    text = data.get('broadcast_text', '')

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📷 Добавить картинку", callback_data="add_broadcast_photo")],
        [InlineKeyboardButton(text="📤 Отправить сейчас", callback_data="send_broadcast_now")],
        [InlineKeyboardButton(text="⏰ Запланировать", callback_data="schedule_broadcast")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_back")]
    ])

    await call.message.edit_text(
        f"📢 Текст рассылки:\n\n{text}\n\n🗑 Картинка удалена. Выберите действие:",
        reply_markup=kb
    )


from aiogram.exceptions import TelegramBadRequest

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

    broadcast_type = "с картинкой" if photo_id else "только текст"

    # Безопасная попытка редактирования
    try:
        if call.message.text:
            await call.message.edit_text(f"📤 Отправка рассылки ({broadcast_type})...")
        elif call.message.caption:
            await call.message.edit_caption(f"📤 Отправка рассылки ({broadcast_type})...")
        else:
            await call.message.answer(f"📤 Отправка рассылки ({broadcast_type})...")
    except TelegramBadRequest:
        await call.message.answer(f"📤 Отправка рассылки ({broadcast_type})...")

    try:
        success, errors, blocked_users = await send_broadcast_to_all_users(text, photo_id, admin_id)

        result_text = f"""✅ Рассылка завершена!

📊 Результаты:
✅ Успешно отправлено: {success}
❌ Ошибок: {errors}
📈 Процент доставки: {round((success/(success+errors))*100, 1) if (success+errors) > 0 else 0}%

📝 Тип рассылки: {broadcast_type}"""

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_back")]
        ])

        # Аналогично — проверяем, что редактируем
        try:
            if call.message.text:
                await call.message.edit_text(result_text, reply_markup=kb)
            elif call.message.caption:
                await call.message.edit_caption(result_text, reply_markup=kb)
            else:
                await call.message.answer(result_text, reply_markup=kb)
        except TelegramBadRequest:
            await call.message.answer(result_text, reply_markup=kb)

        await state.clear()

    except Exception as e:
        print(f"❌ Ошибка отправки рассылки: {e}")
        error_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ])
        try:
            if call.message.text:
                await call.message.edit_text("❌ Ошибка при отправке рассылки", reply_markup=error_kb)
            elif call.message.caption:
                await call.message.edit_caption("❌ Ошибка при отправке рассылки", reply_markup=error_kb)
            else:
                await call.message.answer("❌ Ошибка при отправке рассылки", reply_markup=error_kb)
        except TelegramBadRequest:
            await call.message.answer("❌ Ошибка при отправке рассылки", reply_markup=error_kb)

        await state.clear()


@router.callback_query(F.data == "schedule_broadcast")
async def admin_broadcast_schedule(call: CallbackQuery, state: FSMContext):
    """Запланировать рассылку"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return

    await state.set_state(AdminBroadcast.waiting_for_schedule_time)

    try:
        await call.message.edit_text(
            "⏰ Планирование рассылки\n\n"
            "Введите дату и время отправки в формате:\n"
            "YYYY-MM-DD HH:MM\n\n"
            "Например: 2024-01-15 14:30"
        )
    except:
        await call.message.answer(
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

    try:
        # Безопасно получаем список пользователей
        users = await get_all_users()

        if not users:
            await message.answer("❌ Нет пользователей для рассылки")
            await state.clear()
            return

        # Сохраняем запланированную рассылку для всех пользователей
        saved_count = 0
        for user in users:
            try:
                await save_scheduled_message(
                    user['user_id'],
                    text,
                    photo_id,
                    schedule_time.strftime('%Y-%m-%d %H:%M')
                )
                saved_count += 1
            except Exception as e:
                print(f"❌ Ошибка сохранения для пользователя {user['user_id']}: {e}")

        # Добавляем задачу в планировщик
        from app.utils.scheduler import scheduler
        job_id = f"broadcast_{datetime.now().timestamp()}"
        scheduler.scheduler.add_job(
            send_scheduled_broadcast_with_stats,
            'date',
            run_date=schedule_time,
            id=job_id,
            args=[text, photo_id, message.from_user.id]
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_back")]
        ])

        broadcast_type = "с картинкой" if photo_id else "только текст"
        confirm_text = f"""✅ Рассылка запланирована на {schedule_time.strftime('%d.%m.%Y %H:%M')}

📊 Детали:
👥 Получателей: {saved_count}
📝 Тип: {broadcast_type}"""

        await message.answer(confirm_text, reply_markup=kb)
        await state.clear()

    except Exception as e:
        print(f"❌ Ошибка планирования рассылки: {e}")
        await message.answer("❌ Ошибка при планировании рассылки")
        await state.clear()


@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    """Показать статистику"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return

    # Безопасно получаем статистику
    user_count, active_debts = await get_admin_stats_safely()

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

    # Безопасно получаем статистику
    user_count, active_debts = await get_admin_stats_safely()

    stats_text = f"📊 Статистика бота:\n👥 Пользователей: {user_count}\n📄 Активных долгов: {active_debts}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👥 Список пользователей ({user_count})", callback_data="admin_users")],
        [InlineKeyboardButton(text="📢 Отправить рассылку", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])

    try:
        await call.message.edit_text(stats_text, reply_markup=kb)
    except Exception as e:
        print(f"❌ Ошибка редактирования сообщения админ панели: {e}")
        # Отправляем новое сообщение, если не можем отредактировать
        await call.message.answer(stats_text, reply_markup=kb)