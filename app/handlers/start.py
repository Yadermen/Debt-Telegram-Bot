"""
Обработчики команды /start и выбора языка
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from ..database import get_user_data, get_user_by_id, save_user_lang, get_or_create_user
from ..keyboards import tr, LANGS, main_menu, CallbackData, settings_menu, my_debts_menu
from ..utils import safe_edit_message
from ..states import AddDebt, EditDebt, SetNotifyTime, AdminBroadcast
from .debt import show_debts_simple


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
    if message.chat.type == "private":
        try:
            await message.delete()
        except Exception as e:
            print(f"Ошибка при удалении: {e}")

    try:
        current_state = await state.get_state()

        if current_state:
            if isinstance(current_state, str) and (
                current_state.startswith('AddDebt:') or
                current_state.startswith('EditDebt:') or
                current_state.startswith('SetNotifyTime:') or
                current_state.startswith('AdminBroadcast:')
            ):
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=await tr(user_id, 'continue_process'),
                        callback_data='continue_current_process'
                    )],
                    [InlineKeyboardButton(
                        text=await tr(user_id, 'cancel_and_menu'),
                        callback_data='cancel_and_go_menu'
                    )]
                ])

                process_name = await tr(user_id, 'process_unknown')
                if 'AddDebt:' in current_state:
                    process_name = await tr(user_id, 'process_add_debt')
                elif 'EditDebt:' in current_state:
                    process_name = await tr(user_id, 'process_edit_debt')
                elif 'SetNotifyTime:' in current_state:
                    process_name = await tr(user_id, 'process_set_time')
                elif 'AdminBroadcast:' in current_state:
                    process_name = await tr(user_id, 'process_broadcast')

                warning_text = await tr(user_id, 'process_interrupted', process=process_name)
                await message.answer(warning_text, reply_markup=kb)
                return

        await state.clear()

        user = await get_user_by_id(user_id)

        # ✅ ВАЖНО: определяем источник трафика (например /start reklama1)
        args = message.text.split(maxsplit=1)
        source = args[1] if len(args) > 1 else "organic"

        if not user:
            # Новый пользователь — добавим source
            welcome_text = """
🇷🇺 Добро пожаловать в QarzNazoratBot!
Выберите язык / Tilni tanlang:

🇺🇿 QarzNazoratBot-ga xush kelibsiz!
Выберите язык / Tilni tanlang:
"""
            kb = await language_menu_start(user_id)

            # 👇 создаём пользователя в БД с source
            from ..database import async_session
            from ..database.models import User
            async with async_session() as session:
                new_user = User(user_id=user_id, lang='ru', source=source)
                session.add(new_user)
                await session.commit()

            await message.answer(welcome_text, reply_markup=kb)
            return

        user_data = await get_user_data(user_id)
        welcome_text = await tr(user_id, 'welcome')
        kb = await main_menu(user_id)
        await message.answer(welcome_text, reply_markup=kb)

    except Exception as e:
        print(f"❌ Ошибка в cmd_start для пользователя {user_id}: {e}")
        welcome_text = """
🇷🇺 Добро пожаловать в QarzNazoratBot!
Выберите язык / Tilni tanlang:

🇺🇿 QarzNazoratBot-ga xush kelibsiz!
Выберите язык / Tilni tanlang:
"""
        kb = await language_menu_start(user_id)
        await message.answer(welcome_text, reply_markup=kb)

@router.callback_query(lambda c: c.data == 'continue_current_process')
async def continue_current_process(call: CallbackQuery, state: FSMContext):
    """Продолжить текущий процесс"""
    user_id = call.from_user.id
    current_state = await state.get_state()

    if not current_state:
        # Если состояние потерялось, переходим в меню
        text = await tr(user_id, 'process_lost')
        markup = await main_menu(user_id)
        await safe_edit_message(call, text, markup)
        return

    # Показываем подсказку в зависимости от состояния
    if 'AddDebt:person' in current_state:
        text = await tr(user_id, 'person')
    elif 'AddDebt:currency' in current_state:
        text = await tr(user_id, 'currency')
        from ..keyboards import currency_keyboard
        markup = await currency_keyboard(user_id)
        await safe_edit_message(call, text, markup)
        return
    elif 'AddDebt:amount' in current_state:
        text = await tr(user_id, 'amount')
    elif 'AddDebt:due' in current_state:
        from datetime import datetime, timedelta
        suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        text = await tr(user_id, 'due', suggest_date=suggest_date)
    elif 'AddDebt:direction' in current_state:
        text = await tr(user_id, 'direction')
        from ..keyboards import direction_keyboard
        markup = await direction_keyboard(user_id)
        await safe_edit_message(call, text, markup)
        return
    elif 'AddDebt:comment' in current_state:
        text = await tr(user_id, 'comment')
        from ..keyboards import skip_comment_keyboard
        markup = await skip_comment_keyboard(user_id)
        await safe_edit_message(call, text, markup)
        return
    elif 'EditDebt:' in current_state:
        text = await tr(user_id, 'continue_edit')
    elif 'SetNotifyTime:' in current_state:
        text = await tr(user_id, 'notify_time')
    else:
        text = await tr(user_id, 'continue_process_hint')

    from ..keyboards import menu_button
    markup = await menu_button(user_id)
    await safe_edit_message(call, text, markup)


@router.callback_query(lambda c: c.data == 'cancel_and_go_menu')
async def cancel_and_go_menu(call: CallbackQuery, state: FSMContext):
    """Отменить процесс и перейти в меню"""
    user_id = call.from_user.id
    await state.clear()

    text = await tr(user_id, 'process_cancelled')
    markup = await main_menu(user_id)
    await safe_edit_message(call, text, markup)


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

@router.callback_query(F.data == CallbackData.SETTINGS)
async def settings_menu_handler(call: CallbackQuery, state: FSMContext):
    """Меню настроек"""
    user_id = call.from_user.id
    try:
        await state.clear()
        text = await tr(user_id, 'choose_action')
        kb = await settings_menu(user_id)
        await safe_edit_message(call, text, kb)
    except Exception as e:
        print(f"❌ Ошибка в settings_menu_handler: {e}")
        await call.answer("❌ Ошибка настроек")

