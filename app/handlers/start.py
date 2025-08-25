"""
Обработчики команды /start и выбора языка
"""
from aiogram import Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from ..database import get_user_data, get_user_by_id, save_user_lang, get_or_create_user
from ..keyboards import tr, LANGS, main_menu, CallbackData
from ..utils import safe_edit_message

router = Router()


async def language_menu_start(user_id: int) -> InlineKeyboardMarkup:
    """Меню выбора языка при старте (всегда показываем оба языка одинаково)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Русский",
                callback_data=CallbackData.SETLANG_RU
            )
        ],
        [
            InlineKeyboardButton(
                text="O'zbek tili",
                callback_data=CallbackData.SETLANG_UZ
            )
        ]
    ])


@router.message(Command('start'))
async def cmd_start(message: Message, state: FSMContext):
    """Обработчик команды /start"""
    user_id = message.from_user.id

    try:
        # Проверяем, существует ли пользователь
        user = await get_user_by_id(user_id)

        if not user:
            # Новый пользователь — предлагаем выбрать язык
            # Показываем приветствие на двух языках
            welcome_text = """
🇷🇺 Добро пожаловать в QarzNazoratBot!
Выберите язык / Tilni tanlang:

🇺🇿 QarzNazoratBot-ga xush kelibsiz!
Выберите язык / Tilni tanlang:
"""
            kb = await language_menu_start(user_id)
            await message.answer(welcome_text, reply_markup=kb)
            return

        # Существующий пользователь
        user_data = await get_user_data(user_id)
        welcome_text = await tr(user_id, 'welcome')
        kb = await main_menu(user_id)
        await message.answer(welcome_text, reply_markup=kb)

    except Exception as e:
        print(f"❌ Ошибка в cmd_start для пользователя {user_id}: {e}")
        # В случае ошибки показываем выбор языка
        welcome_text = """
🇷🇺 Добро пожаловать в QarzNazoratBot!
Выберите язык / Tilni tanlang:

🇺🇿 QarzNazoratBot-ga xush kelibsiz!
Выберите язык / Tilni tanlang:
"""
        kb = await language_menu_start(user_id)
        await message.answer(welcome_text, reply_markup=kb)


async def language_menu_settings(user_id: int) -> InlineKeyboardMarkup:
    """Меню выбора языка в настройках (всегда показываем оба языка одинаково)"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="Русский",
                callback_data=CallbackData.SETLANG_RU
            )
        ],
        [
            InlineKeyboardButton(
                text="O'zbek tili",
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


@router.callback_query(lambda c: c.data == CallbackData.CHANGE_LANG)
async def change_lang_menu(call: CallbackQuery, state: FSMContext):
    """Меню смены языка"""
    user_id = call.from_user.id

    try:
        kb = await language_menu_settings(user_id)
        choose_lang_text = await tr(user_id, 'choose_lang')
        await safe_edit_message(call, choose_lang_text, kb)

    except Exception as e:
        print(f"❌ Ошибка в change_lang_menu: {e}")
        await call.answer("Ошибка при смене языка")


@router.callback_query(lambda c: c.data.startswith('setlang_'))
async def set_language(call: CallbackQuery, state: FSMContext):
    """Обработчик смены языка"""
    try:
        lang = call.data.split('_')[1]  # setlang_ru -> ru
        user_id = call.from_user.id

        # Проверяем корректность языка
        if lang not in LANGS:
            await call.answer("❌ Неподдерживаемый язык")
            return

        # Получаем или создаем пользователя с узбекским языком по умолчанию
        user = await get_or_create_user(user_id, default_lang='uz')

        # Сохраняем язык
        await save_user_lang(user_id, lang)

        # Отправляем приветствие на выбранном языке
        welcome_text = await tr(user_id, 'welcome')  # Теперь tr будет использовать новый язык
        kb = await main_menu(user_id)

        await safe_edit_message(call, welcome_text, kb)

        # Показываем уведомление о смене языка
        if lang == 'ru':
            lang_change_msg = "Вы поменяли язык на русский"
        else:
            lang_change_msg = "Siz tilni o'zbek tiliga o'zgartirdingiz"

        await call.answer(f"✅ {lang_change_msg}")

    except Exception as e:
        print(f"❌ Ошибка в set_language: {e}")
        await call.answer("❌ Ошибка при смене языка")


@router.callback_query(lambda c: c.data == CallbackData.BACK_MAIN)
async def back_to_main(call: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    user_id = call.from_user.id

    try:
        # Очищаем состояние FSM
        await state.clear()

        welcome_text = await tr(user_id, 'welcome')
        kb = await main_menu(user_id)

        await safe_edit_message(call, welcome_text, kb)

    except Exception as e:
        print(f"❌ Ошибка в back_to_main: {e}")
        await call.answer("❌ Ошибка возврата в меню")