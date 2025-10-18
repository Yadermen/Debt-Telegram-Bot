"""
Колбек данные для кнопок и динамических действий
"""


class CallbackData:
    """Константы для callback_data"""

    # === MAIN MENU ===
    ADD_DEBT = 'add_debt'
    MY_DEBTS = 'my_debts'
    CLEAR_ALL = 'clear_all'
    REMINDERS_MENU = 'reminders_menu'
    STATISTICS = 'statistics'
    CURRENCY_RATES = 'currency_rates'
    SETTINGS = 'settings'
    HELP = 'help'
    CHANGE_LANG = 'change_lang'
    HOW_TO_USE = 'how_to_use'
    ADD_DEBT_MENU = 'add_debt_menu'
    BACK_MAIN_REMINDER = 'back_main_reminder'

    # === MY DEBTS SUBMENU ===
    DEBTS_LIST = 'debts_list'
    EXPORT_EXCEL = 'export_excel'

    # === SETTINGS SUBMENU ===
    AI_DEBT_ADD = 'ai_debt_add'

    # === REMINDERS MENU ===
    DEBT_REMINDERS = 'debt_reminders'
    CURRENCY_REMINDERS = 'currency_reminders'
    ADD_REMINDER = 'add_reminder'
    MY_REMINDERS = 'my_reminders'

    # === DEBT REMINDERS ===
    TOGGLE_DEBT_REMINDERS = 'toggle_debt_reminders'
    SETUP_REMINDER_TIME = 'setup_reminder_time'

    # === CURRENCY REMINDERS ===
    ENABLE_MORNING_RATES = 'enable_morning_rates'
    ENABLE_EVENING_RATES = 'enable_evening_rates'
    DISABLE_CURRENCY_RATES = 'disable_currency_rates'

    # === REMINDER REPEAT ===
    REPEAT_NO = 'repeat_no'
    REPEAT_DAILY = 'repeat_daily'
    REPEAT_MONTHLY = 'repeat_monthly'

    # === MY REMINDERS ===
    REMINDERS_LIST = 'reminders_list'

    # === LANGUAGE ===
    SETLANG_RU = 'setlang_ru'
    SETLANG_UZ = 'setlang_uz'

    # === NAVIGATION ===
    BACK_MAIN = 'back_main'
    BACK = 'back'
    TO_LIST = 'to_list'
    FORWARD = 'forward'
    BACKWARD = 'backward'

    # === CURRENCY ===
    CUR_USD = 'cur_usd'
    CUR_UZS = 'cur_uzs'
    CUR_EUR = 'cur_eur'

    # === DIRECTION ===
    DIR_GAVE = 'dir_gave'   # Ты дал
    DIR_TOOK = 'dir_took'   # Ты взял

    # === COMMENT ===
    SKIP_COMMENT = 'skip_comment'

    # === DEBT ACTIONS ===
    DEBT_EDIT = 'debt_edit'
    DEBT_DELETE = 'debt_delete'
    DEBT_CLOSE = 'debt_close'
    DEBT_EXTEND = 'debt_extend'

    # === CONFIRMATION ===
    CONFIRM_YES = 'yes'
    CONFIRM_NO = 'no'

    # === EDIT FIELDS ===
    EDIT_PERSON = 'editfield_person'
    EDIT_AMOUNT = 'editfield_amount'
    EDIT_CURRENCY = 'editfield_currency'
    EDIT_DUE = 'editfield_due'
    EDIT_COMMENT = 'editfield_comment'

    # === REMINDERS (legacy) ===
    REMINDER_CHANGE = 'reminder_change'


class DynamicCallbacks:
    """Динамические колбеки с параметрами"""

    @staticmethod
    def debt_action(action: str, debt_id: int) -> str:
        """Действие с долгом: edit_123, delete_123, close_123, view_123"""
        return f"{action}_{debt_id}"

    @staticmethod
    def edit_currency(currency: str, debt_id: int) -> str:
        """Изменение валюты: editcur_USD_123"""
        return f"editcur_{currency}_{debt_id}"

    @staticmethod
    def confirm_action(action: str, debt_id: int) -> str:
        """Подтверждение действия: confirm_delete_123"""
        return f"confirm_{action}_{debt_id}"

    @staticmethod
    def edit_field(field: str, debt_id: int) -> str:
        """Редактирование поля: editfield_person_123"""
        return f"editfield_{field}_{debt_id}"

    @staticmethod
    def reminder_action(action: str, reminder_id: int) -> str:
        """Действие с напоминанием: view_123, edit_123, delete_123"""
        return f"reminder_{action}_{reminder_id}"

    @staticmethod
    def edit_reminder_field(field: str, reminder_id: int) -> str:
        """Редактирование поля напоминания: edit_reminder_text_123"""
        return f"edit_reminder_{field}_{reminder_id}"

    @staticmethod
    def confirm_reminder_action(action: str, reminder_id: int) -> str:
        """Подтверждение действия с напоминанием: confirm_reminder_delete_123"""
        return f"confirm_reminder_{action}_{reminder_id}"


class ButtonNames:
    """Названия кнопок без перевода"""

    # Валюты
    USD = 'USD'
    UZS = 'UZS'
    EUR = 'EUR'

    # Эмодзи для действий
    EMOJI_ADD = '➕'
    EMOJI_LIST = '📋'
    EMOJI_DELETE = '🧹'
    EMOJI_REMIND = '🔔'
    EMOJI_STATISTICS = '📊'
    EMOJI_CURRENCY = '💱'
    EMOJI_SETTINGS = '⚙️'
    EMOJI_HELP = 'ℹ️'
    EMOJI_LANG = '🌍'
    EMOJI_BACK = '⬅️'
    EMOJI_FORWARD = '➡️'
    EMOJI_YES = '✅'
    EMOJI_NO = '❌'
    EMOJI_EXTEND = '🔁'
    EMOJI_EDIT = '✏️'
    EMOJI_TIME = '⏰'
    EMOJI_MORNING = '🌅'
    EMOJI_EVENING = '🌆'
