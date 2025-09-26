"""
Инициализация всех хендлеров
"""
from aiogram import Dispatcher
from . import start, debt, instructions, reminders, admin, export, currency, ai # 🔥 добавили currency

def register_all_handlers(dp: Dispatcher):
    """Регистрация всех роутеров"""
    # Порядок важен! Более специфичные хендлеры должны идти первыми
    dp.include_router(admin.router)   # Админ хендлеры первыми
    dp.include_router(export.router)
    dp.include_router(start.router)
    dp.include_router(ai.router)
    dp.include_router(debt.router)
    dp.include_router(instructions.router)
    dp.include_router(reminders.router)
    dp.include_router(currency.router)  # 🔥 новый роутер для курсов валют

    print("✅ Все хендлеры зарегистрированы")


__all__ = ['register_all_handlers']
