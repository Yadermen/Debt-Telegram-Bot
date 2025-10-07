"""
Клавиатуры для бота
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.keyboards.texts import tr
from .callbacks import CallbackData, DynamicCallbacks, ButtonNames


async def main_menu(user_id: int) -> InlineKeyboardMarkup:
    """Главное меню согласно новым требованиям"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'add_debt'),
                callback_data=CallbackData.ADD_DEBT_MENU
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'my_debts'),
                callback_data=CallbackData.MY_DEBTS
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'reminders_menu'),
                callback_data=CallbackData.REMINDERS_MENU
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'statistics'),
                callback_data=CallbackData.STATISTICS
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'currency_rates'),
                callback_data=CallbackData.CURRENCY_RATES
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'settings'),
                callback_data=CallbackData.SETTINGS
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'help'),
                callback_data=CallbackData.HOW_TO_USE
            )
        ]
    ])

async def add_debts_menu(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
            text=await tr(user_id, 'add_debt'),
            callback_data=CallbackData.ADD_DEBT
        ),
        ],
        [

            InlineKeyboardButton(
                text=await tr(user_id, 'ai_debt_add'),
                callback_data=CallbackData.AI_DEBT_ADD
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'back'),
                callback_data=CallbackData.BACK_MAIN
            )
        ]

    ])



async def my_debts_menu(user_id: int) -> InlineKeyboardMarkup:
    """Подменю 'Мои долги'"""
    return InlineKeyboardMarkup(inline_keyboard=[

        [
            InlineKeyboardButton(
                text=await tr(user_id, 'export_excel_btn'),
                callback_data=CallbackData.EXPORT_EXCEL
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'clear_all'),
                callback_data=CallbackData.CLEAR_ALL
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'back'),
                callback_data=CallbackData.BACK_MAIN
            )
        ]
    ])


async def settings_menu(user_id: int) -> InlineKeyboardMarkup:
    """Подменю 'Настройки'"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'change_lang'),
                callback_data=CallbackData.CHANGE_LANG
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
                text=await tr(user_id, 'back'),
                callback_data=CallbackData.BACK_MAIN
            )
        ]
    ])


async def reminders_menu(user_id: int) -> InlineKeyboardMarkup:
    """Главное меню напоминаний"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'debt_reminders'),
                callback_data=CallbackData.DEBT_REMINDERS
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'currency_reminders'),
                callback_data=CallbackData.CURRENCY_REMINDERS
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'add_reminder'),
                callback_data=CallbackData.ADD_REMINDER
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'my_reminders'),
                callback_data=CallbackData.MY_REMINDERS
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'back'),
                callback_data=CallbackData.BACK_MAIN
            )
        ]
    ])


async def debt_reminders_menu(user_id: int, enabled: bool = False) -> InlineKeyboardMarkup:
    """Меню напоминаний о долгах"""
    toggle_button = InlineKeyboardButton(
        text=await tr(user_id, 'disable_reminders' if enabled else 'enable_reminders'),
        callback_data=CallbackData.TOGGLE_DEBT_REMINDERS
    )
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [toggle_button],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'setup_time'),
                callback_data=CallbackData.SETUP_REMINDER_TIME
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'back'),
                callback_data=CallbackData.REMINDERS_MENU
            )
        ]
    ])


async def currency_reminders_menu(user_id: int, morning_enabled: bool = False, evening_enabled: bool = False) -> InlineKeyboardMarkup:
    """Меню напоминаний о курсе валют"""
    buttons = []
    
    if not morning_enabled:
        buttons.append([
            InlineKeyboardButton(
                text=await tr(user_id, 'enable_morning_rates'),
                callback_data=CallbackData.ENABLE_MORNING_RATES
            )
        ])
    
    if not evening_enabled:
        buttons.append([
            InlineKeyboardButton(
                text=await tr(user_id, 'enable_evening_rates'),
                callback_data=CallbackData.ENABLE_EVENING_RATES
            )
        ])
    
    if morning_enabled or evening_enabled:
        buttons.append([
            InlineKeyboardButton(
                text=await tr(user_id, 'disable_currency_rates'),
                callback_data=CallbackData.DISABLE_CURRENCY_RATES
            )
        ])
    
    buttons.append([
        InlineKeyboardButton(
            text=await tr(user_id, 'back'),
            callback_data=CallbackData.REMINDERS_MENU
        )
    ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def reminder_repeat_menu(user_id: int) -> InlineKeyboardMarkup:
    """Меню выбора повторения напоминания"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'no_repeat'),
                callback_data=CallbackData.REPEAT_NO
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'daily_repeat'),
                callback_data=CallbackData.REPEAT_DAILY
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'monthly_repeat'),
                callback_data=CallbackData.REPEAT_MONTHLY
            )
        ]
    ])


async def my_reminders_menu(user_id: int) -> InlineKeyboardMarkup:
    """Меню списка напоминаний"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'reminders_list'),
                callback_data=CallbackData.REMINDERS_LIST
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'back'),
                callback_data=CallbackData.REMINDERS_MENU
            )
        ]
    ])


async def reminder_actions_keyboard(reminder_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура действий с напоминанием"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'edit'),
                callback_data=DynamicCallbacks.reminder_action('edit', reminder_id)
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'delete'),
                callback_data=DynamicCallbacks.reminder_action('delete', reminder_id)
            )
        ]
    ])


async def edit_reminder_menu(reminder_id: int, user_id: int) -> InlineKeyboardMarkup:
    """Меню редактирования напоминания"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'edit_reminder_text'),
                callback_data=DynamicCallbacks.edit_reminder_field('text', reminder_id)
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'edit_reminder_datetime'),
                callback_data=DynamicCallbacks.edit_reminder_field('datetime', reminder_id)
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'edit_reminder_repeat'),
                callback_data=DynamicCallbacks.edit_reminder_field('repeat', reminder_id)
            )
        ],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'back'),
                callback_data=DynamicCallbacks.reminder_action('view', reminder_id)
            )
        ]
    ])


# Существующие клавиатуры остаются без изменений
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