"""
Клавиатуры с пагинацией для списков долгов и дополнительные клавиатуры
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from .texts import tr
from ..database.models import safe_str


async def debts_list_keyboard_paginated(debts: list, user_id: int, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Клавиатура со списком долгов с пагинацией"""
    keyboard = []
    start = page * per_page
    end = start + per_page

    # Добавляем долги для текущей страницы
    for debt in debts[start:end]:
        btn_text = f"{safe_str(debt['person'])} | {safe_str(debt['amount'])} {safe_str(debt.get('currency', 'UZS'))}"
        keyboard.append([
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f'debtcard_{debt["id"]}_{page}'
            )
        ])

    # Добавляем навигацию
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                text=await tr(user_id, 'backward'),
                callback_data=f'debts_page_{page-1}'
            )
        )
    if end < len(debts):
        nav_buttons.append(
            InlineKeyboardButton(
                text=await tr(user_id, 'forward'),
                callback_data=f'debts_page_{page+1}'
            )
        )

    if nav_buttons:
        keyboard.append(nav_buttons)

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def debts_list_keyboard(debts: list, user_id: int) -> InlineKeyboardMarkup:
    """Простая клавиатура со списком долгов без пагинации"""
    keyboard = []

    for debt in debts:
        btn_text = f"{safe_str(debt['person'])} | {safe_str(debt['amount'])} {safe_str(debt.get('currency', 'UZS'))}"
        keyboard.append([
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f'debtcard_{debt["id"]}_0'
            )
        ])

    # Кнопка возврата в меню
    keyboard.append([
        InlineKeyboardButton(
            text=await tr(user_id, 'to_menu'),
            callback_data='back_main'
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def debt_card_keyboard(debt_id: int, page: int, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для карточки долга"""
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
            text=await tr(user_id, 'to_list'),
            callback_data=f'debts_page_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_menu'),
            callback_data='back_main'
        )],
    ])


async def reminder_debt_actions_keyboard(debt_id: int, page: int, user_id: int) -> InlineKeyboardMarkup:
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


async def edit_debt_menu_keyboard(debt_id: int, page: int, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для меню редактирования долга"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await tr(user_id, 'editfield_person_btn'),
            callback_data=f'editfield_person_{debt_id}_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'editfield_amount_btn'),
            callback_data=f'editfield_amount_{debt_id}_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'editfield_currency_btn'),
            callback_data=f'editfield_currency_{debt_id}_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'editfield_due_btn'),
            callback_data=f'editfield_due_{debt_id}_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'editfield_comment_btn'),
            callback_data=f'editfield_comment_{debt_id}_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_menu'),
            callback_data='back_main'
        )],
    ])


async def edit_currency_debt_keyboard(debt_id: int, page: int, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для редактирования валюты долга"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text='USD',
            callback_data=f'editcur_USD_{debt_id}_{page}'
        )],
        [InlineKeyboardButton(
            text='UZS',
            callback_data=f'editcur_UZS_{debt_id}_{page}'
        )],
        [InlineKeyboardButton(
            text='EUR',
            callback_data=f'editcur_EUR_{debt_id}_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_menu'),
            callback_data='back_main'
        )],
    ])


async def confirm_action_keyboard(action: str, debt_id: int, page: int, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await tr(user_id, 'yes'),
            callback_data=f'confirm_{action}_{debt_id}_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'no'),
            callback_data=f'debtcard_{debt_id}_{page}'
        )],
    ])


async def clear_all_confirm_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения очистки всех долгов"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await tr(user_id, 'yes'),
            callback_data='confirm_clear_all'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'no'),
            callback_data='cancel_action'
        )],
    ])


async def reminders_menu_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для меню напоминаний"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await tr(user_id, 'reminder_change'),
            callback_data='reminder_change_time'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_menu'),
            callback_data='back_main'
        )],
    ])