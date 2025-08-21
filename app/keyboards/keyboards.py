"""
Клавиатуры для бота
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from .texts import tr
from .callbacks import CallbackData, DynamicCallbacks, ButtonNames


async def main_menu(user_id: int) -> InlineKeyboardMarkup:
    """Главное меню (двухколоночная разметка)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'add_debt'),
                callback_data=CallbackData.ADD_DEBT
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'my_debts'),
                callback_data=CallbackData.MY_DEBTS
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'clear_all'),
                callback_data=CallbackData.CLEAR_ALL
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'reminders_menu'),
                callback_data=CallbackData.REMINDERS_MENU
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'how_to_use_btn'),
                callback_data=CallbackData.HOW_TO_USE
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'change_lang'),
                callback_data=CallbackData.CHANGE_LANG
            )
        ]
    ])


async def language_menu(user_id: int) -> InlineKeyboardMarkup:
    """Меню выбора языка"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'lang_ru'),
                callback_data=CallbackData.SETLANG_RU
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'lang_uz'),
                callback_data=CallbackData.SETLANG_UZ
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'to_menu'),
                callback_data=CallbackData.BACK_MAIN
            )
        ]
    ])


async def currency_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора валюты"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ButtonNames.USD, callback_data=CallbackData.CUR_USD)],
        [InlineKeyboardButton(text=ButtonNames.UZS, callback_data=CallbackData.CUR_UZS)],
        [InlineKeyboardButton(text=ButtonNames.EUR, callback_data=CallbackData.CUR_EUR)]
    ])


async def direction_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура выбора направления долга"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'dir_gave'),
                callback_data=CallbackData.DIR_GAVE
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'dir_took'),
                callback_data=CallbackData.DIR_TOOK
            )
        ]
    ])


async def skip_comment_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для пропуска комментария"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'skip_comment'),
                callback_data=CallbackData.SKIP_COMMENT
            )
        ]
    ])


async def menu_button(user_id: int) -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'to_menu'),
                callback_data=CallbackData.BACK_MAIN
            )
        ]
    ])


async def currency_edit_keyboard(debt_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для редактирования валюты конкретного долга"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=ButtonNames.USD,
                callback_data=DynamicCallbacks.edit_currency('USD', debt_id)
            )
        ],
        [
            InlineKeyboardButton(
                text=ButtonNames.UZS,
                callback_data=DynamicCallbacks.edit_currency('UZS', debt_id)
            )
        ],
        [
            InlineKeyboardButton(
                text=ButtonNames.EUR,
                callback_data=DynamicCallbacks.edit_currency('EUR', debt_id)
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'to_menu'),
                callback_data=CallbackData.BACK_MAIN
            )
        ]
    ])


async def debt_actions_keyboard(debt_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий с долгом"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'edit'),
                callback_data=DynamicCallbacks.debt_action('edit', debt_id)
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'close'),
                callback_data=DynamicCallbacks.debt_action('close', debt_id)
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'extend'),
                callback_data=DynamicCallbacks.debt_action('extend', debt_id)
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'delete'),
                callback_data=DynamicCallbacks.debt_action('delete', debt_id)
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'to_list'),
                callback_data=CallbackData.MY_DEBTS
            )
        ]
    ])


async def confirm_keyboard(action: str, debt_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'yes'),
                callback_data=DynamicCallbacks.confirm_action(action, debt_id)
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'no'),
                callback_data=CallbackData.BACK
            )
        ]
    ])


async def edit_fields_keyboard(debt_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура для выбора поля редактирования"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'editfield_person_btn'),
                callback_data=DynamicCallbacks.edit_field('person', debt_id)
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'editfield_amount_btn'),
                callback_data=DynamicCallbacks.edit_field('amount', debt_id)
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'editfield_currency_btn'),
                callback_data=DynamicCallbacks.edit_field('currency', debt_id)
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'editfield_due_btn'),
                callback_data=DynamicCallbacks.edit_field('due', debt_id)
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'editfield_comment_btn'),
                callback_data=DynamicCallbacks.edit_field('comment', debt_id)
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'back'),
                callback_data=DynamicCallbacks.debt_action('view', debt_id)
            )
        ]
    ])