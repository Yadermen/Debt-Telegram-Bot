"""
Обработчики для напоминаний
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
import re

from database import get_user_data, save_user_notify_time
from keyboards import tr
from states import SetNotifyTime
from utils import safe_edit_message
from utils.scheduler import schedule_all_reminders

router = Router()


@router.callback_query(F.data == 'reminders_menu')
async def reminders_menu(call: CallbackQuery, state: FSMContext):
    """Меню напоминаний"""
    user_id = call.from_user.id
    try:
        user_data = await get_user_data(user_id)
    except Exception:
        await call.message.answer(await tr(user_id, 'db_error'))
        return

    current = user_data.get('notify_time', '09:00')
    text = await tr(user_id, 'reminder_time', time=current if current else '-')

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await tr(user_id, 'reminder_change'),
            callback_data='reminder_change_time'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_menu'),
            callback_data='back_main'
        )],
    ])

    await safe_edit_message(call, text, kb)


@router.callback_query(F.data == 'reminder_change_time')
async def reminder_change_time(call: CallbackQuery, state: FSMContext):
    """Изменение времени напоминаний"""
    user_id = call.from_user.id

    await call.message.edit_text(await tr(user_id, 'notify_time'))
    await state.set_state(SetNotifyTime.waiting_for_time)


@router.message(SetNotifyTime.waiting_for_time)
async def set_notify_time_handler(message: Message, state: FSMContext):
    """Установка времени уведомлений"""
    time_text = message.text.strip()
    user_id = message.from_user.id

    try:
        # Разрешаем разные форматы ввода: 9, 9:0, 9:00, 09:0, 09:00, 9:30, 09:30
        if ':' in time_text:
            parts = time_text.split(':')
            if len(parts) != 2:
                raise ValueError
            hour = int(parts[0])
            minute = int(parts[1])
        else:
            hour = int(time_text)
            minute = 0

        # Проверяем корректность времени
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError

        # Форматируем время с ведущими нулями
        formatted_time = '{:02d}:{:02d}'.format(hour, minute)

    except ValueError:
        await message.answer(await tr(user_id, 'notify_wrong'))
        return

    try:
        await save_user_notify_time(user_id, formatted_time)
    except Exception:
        await message.answer(await tr(user_id, 'save_notify_error'))
        return

    # Перепланируем все напоминания после изменения времени
    await schedule_all_reminders()

    try:
        user_data = await get_user_data(user_id)
    except Exception:
        user_data = {'notify_time': formatted_time}

    success_text = await tr(user_id, 'notify_set')
    time_info = await tr(user_id, 'reminder_time', time=user_data.get('notify_time', '-'))

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_menu'),
            callback_data='back_main'
        )],
    ])

    await message.answer(success_text + time_info, reply_markup=kb)
    await state.clear()


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