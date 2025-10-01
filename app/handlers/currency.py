"""
Обработчик для отображения и конвертации курсов валют
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

try:
    from ..keyboards import tr, CallbackData
    from ..utils import safe_edit_message
    from app.utils.currency_api import format_currency_notification, convert_currency
except ImportError as e:
    print(f"❌ Ошибка импорта в currency.py: {e}")

router = Router()


# FSM для ввода суммы
class CurrencyFSM(StatesGroup):
    waiting_for_amount = State()


# Универсальная клавиатура "Назад к курсам"
async def back_to_currency_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=await tr(user_id, "back"), callback_data=CallbackData.CURRENCY_RATES)]]
    )


# Главное меню курсов валют
@router.callback_query(F.data == CallbackData.CURRENCY_RATES)
async def show_currency_menu(call: CallbackQuery, state: FSMContext):
    """Показать меню курсов валют"""
    user_id = call.from_user.id
    await state.clear()

    try:
        # Получаем текст с курсами
        currency_message = await format_currency_notification(user_id, tr)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="UZS → USD", callback_data="convert_uzs_usd"),
             InlineKeyboardButton(text="USD → UZS", callback_data="convert_usd_uzs")],
            [InlineKeyboardButton(text="UZS → EUR", callback_data="convert_uzs_eur"),
             InlineKeyboardButton(text="EUR → UZS", callback_data="convert_eur_uzs")],
            [InlineKeyboardButton(text="UZS → RUB", callback_data="convert_uzs_rub"),
             InlineKeyboardButton(text="RUB → UZS", callback_data="convert_rub_uzs")],
            [InlineKeyboardButton(text=await tr(user_id, "back_main_btn"), callback_data=CallbackData.BACK_MAIN)]
        ])

        await safe_edit_message(call, currency_message, kb)

    except Exception as e:
        print(f"❌ Ошибка в show_currency_menu: {e}")
        error_text = await tr(user_id, 'currency_error')
        await safe_edit_message(call, error_text, await back_to_currency_kb(call.from_user.id))


# Обработка выбора направления
@router.callback_query(F.data.startswith("convert_"))
async def ask_for_amount(call: CallbackQuery, state: FSMContext):
    direction = call.data.replace("convert_", "")
    await state.set_state(CurrencyFSM.waiting_for_amount)
    await state.update_data(direction=direction)

    # call.answer() чтобы убрать "часики"
    await call.answer()

    await call.message.answer(
        await tr(call.from_user.id, "enter_amount"),
        reply_markup=await back_to_currency_kb(call.from_user.id)
    )


# Обработка суммы и конвертации
@router.message(CurrencyFSM.waiting_for_amount)
async def process_conversion(message: Message, state: FSMContext):
    data = await state.get_data()
    direction = data.get("direction")

    try:
        amount = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer(await tr(message.from_user.id, "invalid_number_prompt"), reply_markup=await back_to_currency_kb(message.from_user.id))
        return

    result = await convert_currency(direction, amount)
    if result is None:
        await message.answer(await tr(message.from_user.id, "conversion_error"), reply_markup=await back_to_currency_kb(message.from_user.id))
        await state.clear()
        return

    from_curr, to_curr = direction.upper().split("_")

    await message.answer(
        f"💱 {amount} {from_curr} = {result:.2f} {to_curr}",
        reply_markup=await back_to_currency_kb(message.from_user.id)
    )
    await state.clear()
