"""
Обработчик для отображения курсов валют
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

try:
    from ..keyboards import tr, main_menu, CallbackData
    from ..utils import safe_edit_message
    from ..utils.currency_api import format_currency_notification
except ImportError as e:
    print(f"❌ Ошибка импорта в currency.py: {e}")

router = Router()


@router.callback_query(F.data == CallbackData.CURRENCY_RATES)
async def show_currency_rates(call: CallbackQuery, state: FSMContext):
    """Показать актуальные курсы валют"""
    user_id = call.from_user.id

    try:
        await state.clear()

        # Показываем индикатор загрузки
        await call.answer("⏳ Загружаем курсы валют...")

        # Получаем отформатированное сообщение с курсами
        currency_message = await format_currency_notification(user_id, tr)

        # Добавляем кнопку возврата в главное меню
        kb = await main_menu(user_id)

        await safe_edit_message(call, currency_message, kb)

    except Exception as e:
        print(f"❌ Ошибка в show_currency_rates: {e}")
        try:
            error_text = await tr(user_id, 'currency_error')
            kb = await main_menu(user_id)
            await safe_edit_message(call, error_text, kb)
        except Exception as inner_e:
            print(f"❌ Критическая ошибка при отображении ошибки курсов: {inner_e}")
            await call.answer("❌ Ошибка получения курсов валют")