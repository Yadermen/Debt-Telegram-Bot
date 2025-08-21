from aiogram.fsm.state import StatesGroup, State

class AdminBroadcast(StatesGroup):
    waiting_for_text = State()
    waiting_for_photo = State()
    waiting_for_schedule_time = State()