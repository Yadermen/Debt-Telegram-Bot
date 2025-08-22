from .texts import tr, LANGS
from .callbacks import CallbackData, DynamicCallbacks, ButtonNames
from .keyboards import (
    main_menu,
    language_menu,
    currency_keyboard,
    direction_keyboard,
    skip_comment_keyboard,
    menu_button,
    currency_edit_keyboard,
    debt_actions_keyboard,
    confirm_keyboard,
    edit_fields_keyboard
)
from .pagination import (
    debts_list_keyboard_paginated,
    debts_list_keyboard,
    debt_card_keyboard,
    edit_debt_menu_keyboard,
    edit_currency_debt_keyboard,
    confirm_action_keyboard
)


def safe_str(value):
    """Безопасное преобразование в строку"""
    if value is None:
        return ""
    return str(value)


__all__ = [
    # Texts and translations
    'tr', 'LANGS',

    # Callback constants
    'CallbackData', 'DynamicCallbacks', 'ButtonNames',

    # Keyboards
    'main_menu',
    'language_menu',
    'currency_keyboard',
    'direction_keyboard',
    'skip_comment_keyboard',
    'menu_button',
    'currency_edit_keyboard',
    'debt_actions_keyboard',
    'confirm_keyboard',
    'edit_fields_keyboard',

    # Pagination keyboards
    'debts_list_keyboard_paginated',
    'debts_list_keyboard',
    'debt_card_keyboard',
    'edit_debt_menu_keyboard',
    'edit_currency_debt_keyboard',
    'confirm_action_keyboard',

    # Utils
    'safe_str'
]