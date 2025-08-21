"""
Инициализация всех хендлеров
"""
from aiogram import Dispatcher
from . import start, debt


def register_all_handlers(dp: Dispatcher):
    """Регистрация всех роутеров"""
    # Порядок важен! Более специфичные хендлеры должны идти первыми
    dp.include_router(start.router)
    dp.include_router(debt.router)

    print("✅ Все хендлеры зарегистрированы")


__all__ = ['register_all_handlers']