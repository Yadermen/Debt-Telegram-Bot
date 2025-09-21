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
    edit_fields_keyboard,
    # Новые клавиатуры
    my_debts_menu,
    settings_menu,
    reminders_menu,
    debt_reminders_menu,
    currency_reminders_menu,
    reminder_repeat_menu,
    my_reminders_menu,
    reminder_actions_keyboard,
    edit_reminder_menu
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

    # New keyboards for extended functionality
    'my_debts_menu',
    'settings_menu',
    'reminders_menu',
    'debt_reminders_menu',
    'currency_reminders_menu',
    'reminder_repeat_menu',
    'my_reminders_menu',
    'reminder_actions_keyboard',
    'edit_reminder_menu',

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