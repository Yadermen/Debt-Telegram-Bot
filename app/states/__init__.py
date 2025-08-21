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
    """Состояния для админ панели - рассылка"""
    waiting_for_text = State()
    waiting_for_photo = State()
    waiting_for_schedule_time = State()


__all__ = ['AddDebt', 'EditDebt', 'AdminBroadcast']