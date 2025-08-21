"""
Колбек данные для кнопок
"""


class CallbackData:
    """Константы для callback_data"""

    # === MAIN MENU ===
    ADD_DEBT = 'add_debt'
    MY_DEBTS = 'my_debts'
    CLEAR_ALL = 'clear_all'
    REMINDERS_MENU = 'reminders_menu'
    CHANGE_LANG = 'change_lang'
    HOW_TO_USE = 'how_to_use'

    # === LANGUAGE ===
    SETLANG_RU = 'setlang_ru'
    SETLANG_UZ = 'setlang_uz'

    # === NAVIGATION ===
    BACK_MAIN = 'back_main'
    BACK = 'back'
    TO_LIST = 'to_list'

    # === CURRENCY ===
    CUR_USD = 'cur_usd'
    CUR_UZS = 'cur_uzs'
    CUR_EUR = 'cur_eur'

    # === DIRECTION ===
    DIR_GAVE = 'dir_gave'  # Ты дал
    DIR_TOOK = 'dir_took'  # Ты взял

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

    # === NAVIGATION ===
    FORWARD = 'forward'
    BACKWARD = 'backward'

    # === EDIT FIELDS ===
    EDIT_PERSON = 'editfield_person'
    EDIT_AMOUNT = 'editfield_amount'
    EDIT_CURRENCY = 'editfield_currency'
    EDIT_DUE = 'editfield_due'
    EDIT_COMMENT = 'editfield_comment'

    # === REMINDERS ===
    REMINDER_CHANGE = 'reminder_change'


class DynamicCallbacks:
    """Динамические колбеки с параметрами"""

    @staticmethod
    def debt_action(action: str, debt_id: int) -> str:
        """Действие с долгом: edit_123, delete_123, close_123"""
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


# === BUTTON NAMES (без перевода) ===
class ButtonNames:
    """Названия кнопок без перевода"""

    # Валюты
    USD = 'USD'
    UZS = 'UZS'
    EUR = 'EUR'

    # Эмодзи для действий
    EMOJI_ADD = '➕'
    EMOJI_LIST = '📄'
    EMOJI_DELETE = '🕔'
    EMOJI_REMIND = '⏰'
    EMOJI_LANG = '🌐'
    EMOJI_INFO = 'ℹ️'
    EMOJI_BACK = '⬅️'
    EMOJI_FORWARD = '➡️'
    EMOJI_YES = '✅'
    EMOJI_NO = '❌'
    EMOJI_EXTEND = '🔁'