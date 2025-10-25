from aiogram.fsm.state import StatesGroup, State


class AddDebt(StatesGroup):
    """Состояния для добавления нового долга"""
    person = State()
    currency = State()
    amount = State()
    due = State()
    direction = State()
    comment = State()


class EditDebt(StatesGroup):
    """Состояния для редактирования долга"""
    edit_value = State()
    extend_due = State()


class AdminBroadcast(StatesGroup):
    waiting_for_text = State()
    waiting_for_photo = State()
    waiting_for_schedule_time = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()


class SetNotifyTime(StatesGroup):
    """Состояния для установки времени уведомлений"""
    waiting_for_time = State()


class AddReminder(StatesGroup):
    """Состояния для добавления пользовательского напоминания"""
    text = State()
    datetime = State()
    repeat = State()


class EditReminder(StatesGroup):
    """Состояния для редактирования напоминания"""
    edit_value = State()

class AdminReferral(StatesGroup):
    """Состояния для управления рефералками"""
    waiting_for_code = State()         # ввод кода (например promo2025)
    waiting_for_description = State()

__all__ = [
    'AddDebt',
    'EditDebt',
    'AdminBroadcast',
    'SetNotifyTime',
    'AddReminder',
    'EditReminder',
    'AdminReferral'
]
