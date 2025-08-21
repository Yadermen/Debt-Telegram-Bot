import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from dotenv import load_dotenv
import aiosqlite
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz
import html
import json
import sys

load_dotenv()




# Новый обработчик выбора валюты при редактировании
@dp.callback_query(lambda c: c.data.startswith('editcur_'))
async def edit_currency_value(call: CallbackQuery, state: FSMContext):
    _, cur, debt_id, page = call.data.split('_')
    debt_id = int(debt_id)
    page = int(page)
    user_id = call.from_user.id
    debt = await get_debt_by_id(debt_id)
    if not debt or debt['user_id'] != user_id:
        await call.message.answer(await tr(user_id, 'not_found_or_no_access'))
        return
    try:
        await update_debt(debt_id, {'currency': cur})
    except Exception:
        await call.message.answer(await tr(user_id, 'update_error'))
        return
    await call.message.answer(await tr(user_id, 'currency_changed'))
    user_data = await get_user_data(user_id)
    notify_time = user_data.get('notify_time', '09:00')
    updated_debt = await get_debt_by_id(debt_id)
    text = await tr(user_id, 'debt_card', person=safe_str(updated_debt['person']), amount=safe_str(updated_debt['amount']), currency=safe_str(updated_debt.get('currency', 'UZS')), due=safe_str(updated_debt['due']), comment=safe_str(updated_debt['comment']), notify_time=notify_time)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await tr(user_id, 'edit'), callback_data=f'edit_{debt_id}_{page}')],
        [InlineKeyboardButton(text=await tr(user_id, 'close'), callback_data=f'close_{debt_id}_{page}'),
         InlineKeyboardButton(text=await tr(user_id, 'extend'), callback_data=f'extend_{debt_id}_{page}'),
         InlineKeyboardButton(text=await tr(user_id, 'delete'), callback_data=f'del_{debt_id}_{page}')],
        [InlineKeyboardButton(text=await tr(user_id, 'to_list'), callback_data=f'debts_page_{page}')],
        [InlineKeyboardButton(text=await tr(user_id, 'to_menu'), callback_data='back_main')],
    ])
    await call.message.answer(text, reply_markup=kb)
    await state.clear()

# --- Возврат к карточке после погашения, удаления, продления ---
# (уже реализовано: после действия возвращаемся к списку или карточке)

# --- Пагинация списка долгов ---
async def debts_list_keyboard_paginated(debts, user_id, page=0, per_page=5):
    keyboard = []
    start = page * per_page
    end = start + per_page
    for d in debts[start:end]:
        btn_text = f"{safe_str(d['person'])} | {safe_str(d['amount'])} {safe_str(d.get('currency', 'UZS'))}"
        keyboard.append([InlineKeyboardButton(text=btn_text, callback_data=f'debtcard_{d["id"]}_{page}')])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text=await tr(user_id, 'backward'), callback_data=f'debts_page_{page-1}'))
    if end < len(debts):
        nav.append(InlineKeyboardButton(text=await tr(user_id, 'forward'), callback_data=f'debts_page_{page+1}'))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton(text=await tr(user_id, 'to_menu'), callback_data='back_main')])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# --- Напоминания ---
@dp.callback_query(lambda c: c.data == 'reminders_menu')
async def reminders_menu(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    try:
        user_data = await get_user_data(user_id)
    except Exception:
        await call.message.answer(await tr(user_id, 'db_error'))
        return
    current = user_data.get('notify_time', None)
    text = await tr(user_id, 'reminder_time', time=(current if current else '-'))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await tr(user_id, 'reminder_change'), callback_data='reminder_change_time')],
        [InlineKeyboardButton(text=await tr(user_id, 'to_menu'), callback_data='back_main')],
    ])
    await call.message.edit_text(text, reply_markup=kb)

# --- Обработчик меню напоминаний с ручным вводом времени ---
@dp.callback_query(lambda c: c.data == 'reminder_change_time')
async def reminder_change_time(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    # Всегда предлагаем пример 09:00
    await call.message.edit_text(await tr(user_id, 'notify_time', suggest_time='09:00'))
    await state.set_state('set_notify_time')

from aiogram.filters import StateFilter

@dp.message(StateFilter('set_notify_time'))
async def set_notify_time_handler(message: Message, state: FSMContext):
    time_text = message.text.strip()
    try:
        # Разрешаем ввод 9, 9:0, 9:00, 09:0, 09:00, 9:9, 09:9, 09:09
        if ':' in time_text:
            parts = time_text.split(':')
            if len(parts) != 2:
                raise ValueError
            hour = int(parts[0])
            minute = int(parts[1])
        else:
            hour = int(time_text)
            minute = 0
        # Добавляем ведущие нули
        time_text = '{:02d}:{:02d}'.format(hour, minute)
        assert 0 <= hour < 24 and 0 <= minute < 60
    except Exception:
        await message.answer(await tr(message.from_user.id, 'notify_wrong'))
        return
    user_id = message.from_user.id
    try:
        await save_user_notify_time(user_id, time_text)
    except Exception:
        await message.answer(await tr(user_id, 'save_notify_error'))
        return
    await schedule_all_reminders()  # <-- обязательно перепланировать задачи
    try:
        user_data = await get_user_data(user_id)
    except Exception:
        user_data = {'notify_time': time_text}
    text = await tr(user_id, 'notify_set') + await tr(user_id, 'reminder_time', time=user_data.get('notify_time', '-'))
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await tr(user_id, 'to_menu'), callback_data='back_main')],
    ])
    await message.answer(text, reply_markup=kb)
    await state.clear()

# В LANGS ключ notify_time уже содержит пример (например: 09:00), если нужно, можно добавить suggest_time как параметр.

# --- Отправка напоминаний пользователю ---
async def send_due_reminders(user_id):
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

# --- Кнопки для карточки долга в напоминаниях ---
async def reminder_debt_actions(debt_id, page, user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await tr(user_id, 'edit'), callback_data='edit_{}_{}'.format(debt_id, page))],
        [
            InlineKeyboardButton(text=await tr(user_id, 'close'), callback_data=f'close_{debt_id}_{page}'),
            InlineKeyboardButton(text=await tr(user_id, 'extend'), callback_data=f'extend_{debt_id}_{page}'),
            InlineKeyboardButton(text=await tr(user_id, 'delete'), callback_data=f'del_{debt_id}_{page}')
        ],
        [InlineKeyboardButton(text=await tr(user_id, 'to_menu'), callback_data='back_main')]
    ])

# --- Функции для рассылок и планирования ---
# 
# 📸 Хранение картинок:
# - Картинки НЕ сохраняются локально на сервере
# - В базе данных хранится только photo_id (file_id от Telegram)
# - Сами файлы хранятся на серверах Telegram
# - file_id уникален для каждого бота и может быть использован повторно
# - При получении фото: photo_id = message.photo[-1].file_id
# - При отправке: await bot.send_photo(user_id, photo_id, caption=text)
#
async def send_broadcast_to_all_users(text: str, photo_id: str = None, admin_id: int = None):
    """Отправить рассылку всем пользователям"""
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

async def send_scheduled_message(message_data: dict):
    """Отправить запланированное сообщение"""
    try:
        if message_data['photo_id']:
            await bot.send_photo(message_data['user_id'], message_data['photo_id'], caption=message_data['text'])
        else:
            await bot.send_message(message_data['user_id'], message_data['text'])
        return True
    except Exception as e:
        # Не выводим ошибки в консоль, чтобы не засорять логи
        return False

async def schedule_message_for_user(user_id: int, text: str, photo_id: str = None, schedule_datetime: str = None):
    """Запланировать сообщение для конкретного пользователя"""
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

async def send_scheduled_broadcast_with_stats(text: str, photo_id: str = None, admin_id: int = None):
    """Отправить запланированную рассылку с отправкой статистики админу"""
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

# --- Функция для обработки запланированных сообщений ---
async def process_scheduled_messages():
    """Обработать все запланированные сообщения"""
    messages = await get_pending_scheduled_messages()
    for message in messages:
        sent = await send_scheduled_message(message)
        if sent:
            await delete_scheduled_message(message['id'])
        await asyncio.sleep(0.1)  # Небольшая задержка между отправками

# --- Удаление сообщения из scheduled_messages ---
async def delete_scheduled_message(message_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM scheduled_messages WHERE id = ?', (message_id,))
        await db.commit()

# --- Запуск планировщика при старте ---
@dp.startup()
async def on_startup(dispatcher):
    await init_db()
    if not scheduler.running:
        scheduler.start()
    await schedule_all_reminders()
    # Добавляем задачу проверки запланированных сообщений каждую минуту
    scheduler.add_job(check_scheduled_messages, 'interval', minutes=1, id='check_scheduled_messages')

# --- Функция main() для запуска бота ---
async def main():
    await init_db()
    await dp.start_polling(bot)

# Дальнейшая реализация: FSM, база, меню, обработчики, напоминания и т.д. (будет добавлено поэтапно) 

# --- Админ панель ---
def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

@dp.message(Command('admin'))
async def admin_panel(message: Message, state: FSMContext):
    """Админ панель"""
    await state.clear()  # Сброс FSM при входе в админку
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

@dp.callback_query(lambda c: c.data == "admin_users")
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
        text += f"   Язык: {user['lang']}\n"
        text += f"   Напоминания: {user['notify_time']}\n"
        text += f"   Активных долгов: {user['active_debts']}\n"
        text += f"   Всего долгов: {user['total_debts']}\n\n"
    
    if len(users) > 10:
        text += f"... и еще {len(users) - 10} пользователей"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_back")]
    ])
    
    await call.message.edit_text(text, reply_markup=kb)

@dp.callback_query(lambda c: c.data == "admin_broadcast")
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

@dp.message(AdminBroadcast.waiting_for_text)
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

@dp.callback_query(lambda c: c.data == "add_photo", AdminBroadcast.waiting_for_photo)
async def admin_broadcast_add_photo(call: CallbackQuery, state: FSMContext):
    """Добавить фото к рассылке"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return
    
    # Проверяем, есть ли фото в сообщении
    if call.message.photo:
        await call.message.edit_caption(caption="📷 Отправьте фото для рассылки:")
    else:
        await call.message.edit_text("📷 Отправьте фото для рассылки:")

@dp.message(AdminBroadcast.waiting_for_photo, F.photo)
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

@dp.callback_query(lambda c: c.data == "send_without_photo", AdminBroadcast.waiting_for_photo)
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
    
    # Проверяем, есть ли фото в сообщении
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

@dp.callback_query(lambda c: c.data == "send_broadcast_now")
async def admin_broadcast_send_now(call: CallbackQuery, state: FSMContext):
    """Отправить рассылку сейчас"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return
    
    data = await state.get_data()
    text = data['broadcast_text']
    photo_id = data.get('broadcast_photo')
    admin_id = call.from_user.id
    
    # Проверяем, есть ли фото в сообщении
    if call.message.photo:
        await call.message.edit_caption(caption="📤 Отправка рассылки...")
    else:
        await call.message.edit_text("📤 Отправка рассылки...")
    
    success, errors, blocked_users = await send_broadcast_to_all_users(text, photo_id, admin_id)
    
    result_text = f"✅ Рассылка завершена!\n\n📊 Результаты:\n✅ Успешно отправлено: {success}\n❌ Ошибок: {errors}"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад в админ панель", callback_data="admin_back")]
    ])
    
    # Проверяем, есть ли фото в сообщении
    if call.message.photo:
        await call.message.edit_caption(caption=result_text, reply_markup=kb)
    else:
        await call.message.edit_text(result_text, reply_markup=kb)
    
    # Отправляем подробную статистику
    detailed_stats = f"""
📢 Статистика рассылки

📊 Общие результаты:
✅ Успешно отправлено: {success}
❌ Ошибок: {errors}
📈 Процент доставки: {round((success/(success+errors))*100, 1) if (success+errors) > 0 else 0}%

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
    
    # Если есть заблокированные пользователи, показываем их
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
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "send_broadcast_now_no_photo")
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
    
    # Отправляем подробную статистику
    detailed_stats = f"""
📢 Статистика рассылки

📊 Общие результаты:
✅ Успешно отправлено: {success}
❌ Ошибок: {errors}
📈 Процент доставки: {round((success/(success+errors))*100, 1) if (success+errors) > 0 else 0}%

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
    
    # Если есть заблокированные пользователи, показываем их
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
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "schedule_broadcast")
async def admin_broadcast_schedule(call: CallbackQuery, state: FSMContext):
    """Запланировать рассылку"""
    if not is_admin(call.from_user.id):
        await call.answer("Нет доступа")
        return
    
    await state.set_state(AdminBroadcast.waiting_for_schedule_time)
    
    # Проверяем, есть ли фото в сообщении
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

@dp.message(AdminBroadcast.waiting_for_schedule_time)
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
    
    # Добавляем задачу в планировщик с отправкой статистики админу
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
    
    # Отправляем сообщение с подтверждением планирования
    confirm_text = f"✅ Рассылка запланирована на {schedule_time.strftime('%d.%m.%Y %H:%M')}\nПолучателей: {len(users)}"
    await message.answer(confirm_text, reply_markup=kb)
    
    # Отправляем дополнительную статистику планирования
    admin_id = message.from_user.id
    planning_stats = f"""
📅 Планирование рассылки

📊 Детали планирования:
• Дата и время: {schedule_time.strftime('%d.%m.%Y %H:%M')}
• Получателей: {len(users)}
• Тип сообщения: {'С фото' if photo_id else 'Только текст'}

📝 Напоминание:
• Рассылка будет отправлена автоматически
• Статистика доставки будет доступна после отправки
• Время по часовому поясу: Asia/Tashkent
"""
    
    try:
        await bot.send_message(admin_id, planning_stats)
    except Exception:
        pass
    
    await state.clear()

@dp.callback_query(lambda c: c.data == "admin_stats")
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

@dp.callback_query(lambda c: c.data == "admin_back")
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
    
    # Проверяем, есть ли фото в сообщении
    if call.message.photo:
        await call.message.edit_caption(caption=stats_text, reply_markup=kb)
    else:
        await call.message.edit_text(stats_text, reply_markup=kb)

@dp.callback_query(lambda c: c.data == 'how_to_use')
async def how_to_use_handler(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    user_data = await get_user_data(user_id)
    lang = user_data.get('lang', 'ru')
    # Ссылки на Telegraph
    if lang == 'uz':
        url = 'https://telegra.ph/QarzNazoratBot--Foydalanuvchi-uchun-yoriqnoma-07-16'
    else:
        url = 'https://telegra.ph/QarzNazoratBot--Instrukciya-polzovatelya-07-16'
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await tr(user_id, 'open_instruction'), url=url)],
        [InlineKeyboardButton(text=await tr(user_id, 'instruction_back'), callback_data='back_main')],
    ])
    await safe_edit_message(call, await tr(user_id, 'how_to_use_msg'), kb)

if __name__ == '__main__':
    try:
        import asyncio
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print('Бот остановлен!')
    except Exception as e:
        print('Ошибка при запуске:', e, file=sys.stderr)
