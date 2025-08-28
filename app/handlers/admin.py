"""
Админ панель для управления ботом - исправленная версия
"""
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
from app.utils.scheduler import scheduler

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
        [InlineKeyboardButton(text="📤 Отправить сейчас", callback_data="send_broadcast_now")],
        [InlineKeyboardButton(text="⏰ Запланировать", callback_data="schedule_broadcast")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="admin_back")]
    ])

    await message.answer(
        f"📢 Текст рассылки:\n\n{message.text}\n\n"
        "Выберите действие:",
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
    admin_id = call.from_user.id

    await call.message.edit_text("📤 Отправка рассылки...")

    try:
        success, errors, blocked_users = await scheduler.send_broadcast_to_all_users(text, None, admin_id)

        result_text = f"✅ Рассылка завершена!\n\n📊 Результаты:\n✅ Успешно отправлено: {success}\n❌ Ошибок: {errors}"

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_back")]
        ])

        await call.message.edit_text(result_text, reply_markup=kb)
        await state.clear()

    except Exception as e:
        print(f"❌ Ошибка отправки рассылки: {e}")
        await call.message.edit_text(
            "❌ Ошибка при отправке рассылки",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
            ])
        )
        await state.clear()


@router.callback_query(F.data == "schedule_broadcast")
async def admin_broadcast_schedule(call: CallbackQuery, state: FSMContext):
    """Запланировать рассылку"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return

    await state.set_state(AdminBroadcast.waiting_for_schedule_time)

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
                    None,
                    schedule_time.strftime('%Y-%m-%d %H:%M')
                )
                saved_count += 1
            except Exception as e:
                print(f"❌ Ошибка сохранения для пользователя {user['user_id']}: {e}")

        # Добавляем задачу в планировщик
        job_id = f"broadcast_{datetime.now().timestamp()}"
        scheduler.scheduler.add_job(
            scheduler.send_scheduled_broadcast_with_stats,
            'date',
            run_date=schedule_time,
            id=job_id,
            args=[text, None, message.from_user.id]
        )

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_back")]
        ])

        confirm_text = f"✅ Рассылка запланирована на {schedule_time.strftime('%d.%m.%Y %H:%M')}\nПолучателей: {saved_count}"
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