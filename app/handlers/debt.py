"""
Обработчики для работы с долгами
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import re

from ..database import (
    add_debt, get_open_debts, get_debt_by_id, update_debt,
    soft_delete_debt, clear_user_debts, get_user_data, delete_debt
)
from ..keyboards import (
    tr, main_menu, currency_keyboard, direction_keyboard,
    skip_comment_keyboard, menu_button, debt_actions_keyboard,
    confirm_keyboard, edit_fields_keyboard, currency_edit_keyboard,
    CallbackData, DynamicCallbacks, debts_list_keyboard_paginated,
    debts_list_keyboard, safe_str
)
from ..states import AddDebt, EditDebt
from ..utils import safe_edit_message

router = Router()


# === УТИЛИТЫ ===


# === НАВИГАЦИЯ ===

@router.callback_query(F.data == 'back_main')
async def back_main(call: CallbackQuery, state: FSMContext):
    """Возврат в главное меню"""
    await state.clear()
    text = await tr(call.from_user.id, 'choose_action')
    markup = await main_menu(call.from_user.id)

    await safe_edit_message(call, text, markup)


# === ПРОСМОТР ДОЛГОВ (Простой подход) ===

@router.callback_query(F.data == 'my_debts')
async def show_debts_simple(call: CallbackQuery, state: FSMContext):
    """Показать список долгов (простой подход)"""
    user_id = call.from_user.id
    try:
        debts = await get_open_debts(user_id)
    except Exception:
        await call.message.answer(await tr(user_id, 'db_error'))
        return

    if not debts:
        text = await tr(user_id, 'no_debts')
        markup = await main_menu(user_id)
        await safe_edit_message(call, text, markup)
        return

    text = await tr(user_id, 'your_debts')
    markup = await debts_list_keyboard_paginated(debts, user_id, page=0)
    await safe_edit_message(call, text, markup)


# === НАВИГАЦИЯ ПО СТРАНИЦАМ ===
@router.callback_query(lambda c: c.data.startswith('debts_page_'))
async def debts_page_navigation(call: CallbackQuery, state: FSMContext):
    """Навигация по страницам долгов"""
    try:
        page = int(call.data.split('_')[2])
    except Exception:
        page = 0

    user_id = call.from_user.id
    try:
        debts = await get_open_debts(user_id)
    except Exception:
        await call.message.answer(await tr(user_id, 'db_error'))
        return

    if not debts:
        text = await tr(user_id, 'no_debts')
        markup = await main_menu(user_id)
        await safe_edit_message(call, text, markup)
        return

    text = await tr(user_id, 'your_debts')
    markup = await debts_list_keyboard_paginated(debts, user_id, page=page)
    await safe_edit_message(call, text, markup)


async def show_debt_card(user_id, debt_id):
    """Показать карточку долга"""
    try:
        debt = await get_debt_by_id(debt_id)
    except Exception:
        return None, None

    if not debt or debt['user_id'] != user_id:
        return None, None

    text = await tr(
        user_id, 'debt_card',
        person=safe_str(debt['person']),
        amount=safe_str(debt['amount']),
        currency=safe_str(debt.get('currency', 'UZS')),
        due=safe_str(debt['due']),
        comment=safe_str(debt['comment']),
        notify_time='-'
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await tr(user_id, 'edit'),
            callback_data=f'edit_{debt_id}_{0}'
        )],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'close'),
                callback_data=f'close_{debt_id}_{0}'
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'extend'),
                callback_data=f'extend_{debt_id}_{0}'
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'delete'),
                callback_data=f'del_{debt_id}_{0}'
            )
        ],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_list'),
            callback_data='my_debts'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_menu'),
            callback_data='back_main'
        )],
    ])
    return text, kb


# === УПРАВЛЕНИЕ ДОЛГАМИ ===

@router.callback_query(F.data == 'clear_all')
async def clear_all_confirm(call: CallbackQuery, state: FSMContext):
    """Подтверждение очистки всех долгов"""
    user_id = call.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await tr(user_id, 'yes'),
            callback_data='confirm_clear_all'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'no'),
            callback_data='cancel_action'
        )],
    ])
    await call.message.edit_text(
        await tr(user_id, 'clear_all_confirm'),
        reply_markup=kb
    )


@router.callback_query(F.data == 'confirm_clear_all')
async def clear_all(call: CallbackQuery, state: FSMContext):
    """Очистить все долги"""
    user_id = call.from_user.id
    await clear_user_debts(user_id)
    text = await tr(user_id, 'all_deleted')
    markup = await main_menu(user_id)
    await safe_edit_message(call, text, markup)


@router.callback_query(F.data == 'cancel_action')
async def cancel_action(call: CallbackQuery, state: FSMContext):
    """Отмена действия"""
    text = await tr(call.from_user.id, 'cancelled')
    markup = await main_menu(call.from_user.id)
    await safe_edit_message(call, text, markup)


# === КАРТОЧКА ДОЛГА ===

@router.callback_query(lambda c: c.data.startswith('debtcard_'))
async def debt_card(call: CallbackQuery, state: FSMContext):
    """Показать карточку долга с поддержкой возврата на нужную страницу"""
    try:
        parts = call.data.split('_')
        debt_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'bad_request'))
        return

    user_id = call.from_user.id
    await state.update_data(current_page=page)

    try:
        debt = await get_debt_by_id(debt_id)
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'db_error'))
        return

    if not debt or debt['user_id'] != user_id:
        await call.message.answer(await tr(call.from_user.id, 'not_found_or_no_access'))
        return

    # Получаем notify_time пользователя
    user_data = await get_user_data(user_id)
    notify_time = user_data.get('notify_time', '09:00')

    text = await tr(
        user_id, 'debt_card',
        person=safe_str(debt['person']),
        amount=safe_str(debt['amount']),
        currency=safe_str(debt.get('currency', 'UZS')),
        due=safe_str(debt['due']),
        comment=safe_str(debt['comment']),
        notify_time=notify_time
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await tr(user_id, 'edit'),
            callback_data=f'edit_{debt_id}_{page}'
        )],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'close'),
                callback_data=f'close_{debt_id}_{page}'
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'extend'),
                callback_data=f'extend_{debt_id}_{page}'
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'delete'),
                callback_data=f'del_{debt_id}_{page}'
            )
        ],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_list'),
            callback_data=f'debts_page_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_menu'),
            callback_data='back_main'
        )],
    ])

    await safe_edit_message(call, text, kb)


# === УДАЛЕНИЕ ДОЛГОВ ===

@router.callback_query(lambda c: c.data.startswith('del_'))
async def del_debt_confirm(call: CallbackQuery, state: FSMContext):
    """Подтверждение удаления долга"""
    try:
        parts = call.data.split('_')
        debt_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'bad_request'))
        return

    user_id = call.from_user.id
    await state.update_data(current_page=page)

    try:
        debt = await get_debt_by_id(debt_id)
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'db_error'))
        return

    if not debt or debt['user_id'] != user_id:
        await call.message.answer(await tr(call.from_user.id, 'not_found_or_no_access'))
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await tr(user_id, 'yes'),
            callback_data=f'confirm_del_{debt_id}_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'no'),
            callback_data=f'debtcard_{debt_id}_{page}'
        )],
    ])

    await call.message.edit_text(
        await tr(user_id, 'confirm_del'),
        reply_markup=kb
    )


@router.callback_query(lambda c: c.data.startswith('confirm_del_'))
async def del_debt(call: CallbackQuery, state: FSMContext):
    """Удаление долга"""
    try:
        parts = call.data.split('_')
        debt_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'bad_request'))
        return

    user_id = call.from_user.id

    try:
        debt = await get_debt_by_id(debt_id)
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'db_error'))
        return

    if not debt or debt['user_id'] != user_id:
        await call.message.answer(await tr(call.from_user.id, 'not_found_or_no_access'))
        return

    try:
        await delete_debt(debt_id)
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'delete_error'))
        return

    # Получаем обновленный список долгов
    try:
        debts = await get_open_debts(user_id)
    except Exception:
        debts = []

    if not debts:
        # Если долгов больше нет, возвращаем в главное меню
        text = await tr(user_id, 'debt_deleted')
        markup = await main_menu(user_id)
        await safe_edit_message(call, text, markup)
    else:
        # Если долги есть, показываем список с сообщением об удалении
        text = await tr(user_id, 'debt_deleted') + '\n\n' + await tr(user_id, 'your_debts')
        markup = await debts_list_keyboard_paginated(debts, user_id, page=page)
        await safe_edit_message(call, text, markup)


# === ЗАКРЫТИЕ ДОЛГОВ ===

@router.callback_query(lambda c: c.data.startswith('close_'))
async def close_debt_confirm(call: CallbackQuery, state: FSMContext):
    """Подтверждение закрытия долга"""
    try:
        debt_id = int(call.data.split('_')[1])
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'bad_request'))
        return

    user_id = call.from_user.id

    try:
        debt = await get_debt_by_id(debt_id)
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'db_error'))
        return

    if not debt or debt['user_id'] != user_id:
        await call.message.answer(await tr(call.from_user.id, 'not_found_or_no_access'))
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await tr(user_id, 'yes'),
            callback_data=f'confirm_close_{debt_id}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'no'),
            callback_data='back_main'
        )],
    ])

    await call.message.edit_text(
        await tr(user_id, 'confirm_close'),
        reply_markup=kb
    )


@router.callback_query(lambda c: c.data.startswith('confirm_close_'))
async def close_debt(call: CallbackQuery, state: FSMContext):
    """Закрытие долга"""
    try:
        debt_id = int(call.data.split('_')[2])
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'bad_request'))
        return

    user_id = call.from_user.id

    try:
        debt = await get_debt_by_id(debt_id)
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'db_error'))
        return

    if not debt or debt['user_id'] != user_id:
        await call.message.answer(await tr(call.from_user.id, 'not_found_or_no_access'))
        return

    try:
        await update_debt(debt_id, {'closed': True})
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'update_error'))
        return

    text = await tr(user_id, 'debt_closed')
    markup = await main_menu(user_id)
    await safe_edit_message(call, text, markup)


# === ПРОДЛЕНИЕ СРОКА ДОЛГА ===

@router.callback_query(lambda c: c.data.startswith('extend_'))
async def extend_debt_start(call: CallbackQuery, state: FSMContext):
    """Начало продления срока долга"""
    try:
        debt_id = int(call.data.split('_')[1])
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'bad_request'))
        return

    user_id = call.from_user.id

    try:
        debt = await get_debt_by_id(debt_id)
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'db_error'))
        return

    if not debt or debt['user_id'] != user_id:
        await call.message.answer(await tr(call.from_user.id, 'not_found_or_no_access'))
        return

    await state.update_data(extend_debt_id=debt_id)
    suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    await call.message.edit_text(await tr(user_id, 'due', suggest_date=suggest_date))
    await state.set_state(EditDebt.extend_due)


@router.message(EditDebt.extend_due)
async def extend_debt_value(message: Message, state: FSMContext):
    """Обработка новой даты для продления"""
    data = await state.get_data()
    user_id = message.from_user.id
    val = message.text.strip()

    try:
        date_obj = datetime.strptime(val, '%Y-%m-%d')
    except Exception:
        await message.answer(await tr(user_id, 'due_wrong', suggest_date=(datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')))
        return

    # Прибавляем 7 дней к дате
    new_due = (date_obj + timedelta(days=7)).strftime('%Y-%m-%d')

    try:
        await update_debt(data['extend_debt_id'], {'due': new_due})
    except Exception:
        await message.answer(await tr(user_id, 'update_error'))
        return

    text = await tr(user_id, 'date_changed')
    markup = await main_menu(user_id)
    await message.answer(text, reply_markup=markup)
    await state.clear()


# === РЕДАКТИРОВАНИЕ ДОЛГА ===

@router.callback_query(lambda c: c.data.startswith('edit_'))
async def edit_debt_menu(call: CallbackQuery, state: FSMContext):
    """Меню редактирования долга"""
    try:
        parts = call.data.split('_')
        debt_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'bad_request'))
        return

    user_id = call.from_user.id
    debt = await get_debt_by_id(debt_id)

    if not debt or debt['user_id'] != user_id:
        await call.message.answer(await tr(user_id, 'not_found_or_no_access'))
        return

    await state.update_data(edit_debt_id=debt_id, edit_page=page)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await tr(user_id, 'editfield_person_btn'),
            callback_data=f'editfield_person_{debt_id}_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'editfield_amount_btn'),
            callback_data=f'editfield_amount_{debt_id}_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'editfield_currency_btn'),
            callback_data=f'editfield_currency_{debt_id}_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'editfield_due_btn'),
            callback_data=f'editfield_due_{debt_id}_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'editfield_comment_btn'),
            callback_data=f'editfield_comment_{debt_id}_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_menu'),
            callback_data='back_main'
        )],
    ])

    await call.message.edit_text(await tr(user_id, 'edit_what'), reply_markup=kb)


@router.callback_query(lambda c: c.data.startswith('editfield_'))
async def edit_debt_field(call: CallbackQuery, state: FSMContext):
    """Выбор поля для редактирования"""
    _, field, debt_id, page = call.data.split('_')
    debt_id = int(debt_id)
    page = int(page)
    user_id = call.from_user.id

    debt = await get_debt_by_id(debt_id)
    if not debt or debt['user_id'] != user_id:
        await call.message.answer(await tr(user_id, 'not_found_or_no_access'))
        return

    await state.update_data(edit_debt_id=debt_id, edit_field=field, edit_page=page)

    # Индивидуальные подсказки для каждого поля
    if field == 'person':
        await call.message.edit_text(await tr(user_id, 'editfield_person'))
    elif field == 'amount':
        await call.message.edit_text(await tr(user_id, 'editfield_amount'))
    elif field == 'currency':
        # Показываем клавиатуру выбора валюты
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text='USD',
                callback_data=f'editcur_USD_{debt_id}_{page}'
            )],
            [InlineKeyboardButton(
                text='UZS',
                callback_data=f'editcur_UZS_{debt_id}_{page}'
            )],
            [InlineKeyboardButton(
                text='EUR',
                callback_data=f'editcur_EUR_{debt_id}_{page}'
            )],
            [InlineKeyboardButton(
                text=await tr(user_id, 'to_menu'),
                callback_data='back_main'
            )],
        ])
        await call.message.edit_text(
            await tr(user_id, 'editfield_currency'),
            reply_markup=kb
        )
        return
    elif field == 'due':
        suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        await call.message.edit_text(
            await tr(user_id, 'editfield_due', suggest_date=suggest_date)
        )
    elif field == 'comment':
        await call.message.edit_text(await tr(user_id, 'editfield_comment'))
    else:
        # Fallback for other fields
        await call.message.edit_text(await tr(user_id, 'editfield_person'))

    await state.set_state(EditDebt.edit_value)


@router.message(EditDebt.edit_value)
async def edit_debt_value(message: Message, state: FSMContext):
    """Обработка нового значения поля"""
    data = await state.get_data()
    user_id = message.from_user.id
    debt_id = data.get('edit_debt_id')
    field = data.get('edit_field')
    page = data.get('edit_page', 0)
    val = message.text.strip()

    debt = await get_debt_by_id(debt_id)
    if not debt or debt['user_id'] != user_id:
        await message.answer(await tr(user_id, 'not_found_or_no_access'))
        return

    updates = {}

    # Индивидуальная валидация для каждого поля
    if field == 'amount':
        if not val.isdigit():
            await message.answer(await tr(user_id, 'amount_wrong'))
            return
        updates['amount'] = int(val)
    elif field == 'due':
        try:
            date_obj = datetime.strptime(val, '%Y-%m-%d')
        except Exception:
            suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            await message.answer(await tr(user_id, 'due_wrong', suggest_date=suggest_date))
            return
        # Прибавляем 7 дней к дате
        updates['due'] = (date_obj + timedelta(days=7)).strftime('%Y-%m-%d')
    elif field == 'person':
        if not val:
            await message.answer(await tr(user_id, 'editfield_person'))
            return
        updates['person'] = val
    elif field == 'comment':
        updates['comment'] = val
    else:
        updates[field] = val

    try:
        await update_debt(debt_id, updates)
    except Exception:
        await message.answer(await tr(user_id, 'update_error'))
        return

    await message.answer(await tr(user_id, 'changed'))

    # Получаем обновленные данные долга и показываем карточку
    user_data = await get_user_data(user_id)
    notify_time = user_data.get('notify_time', '09:00')
    updated_debt = await get_debt_by_id(debt_id)

    text = await tr(
        user_id, 'debt_card',
        person=safe_str(updated_debt['person']),
        amount=safe_str(updated_debt['amount']),
        currency=safe_str(updated_debt.get('currency', 'UZS')),
        due=safe_str(updated_debt['due']),
        comment=safe_str(updated_debt['comment']),
        notify_time=notify_time
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await tr(user_id, 'edit'),
            callback_data=f'edit_{debt_id}_{page}'
        )],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'close'),
                callback_data=f'close_{debt_id}_{page}'
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'extend'),
                callback_data=f'extend_{debt_id}_{page}'
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'delete'),
                callback_data=f'del_{debt_id}_{page}'
            )
        ],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_list'),
            callback_data=f'debts_page_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_menu'),
            callback_data='back_main'
        )],
    ])

    await message.answer(text, reply_markup=kb)
    await state.clear()


# === РЕДАКТИРОВАНИЕ ВАЛЮТЫ ===

@router.callback_query(lambda c: c.data.startswith('editcur_'))
async def edit_currency_callback(call: CallbackQuery, state: FSMContext):
    """Обработка выбора валюты при редактировании"""
    try:
        _, currency, debt_id, page = call.data.split('_')
        debt_id = int(debt_id)
        page = int(page)
    except Exception:
        await call.message.answer(await tr(call.from_user.id, 'bad_request'))
        return

    user_id = call.from_user.id
    debt = await get_debt_by_id(debt_id)

    if not debt or debt['user_id'] != user_id:
        await call.message.answer(await tr(user_id, 'not_found_or_no_access'))
        return

    try:
        await update_debt(debt_id, {'currency': currency})
    except Exception:
        await call.message.answer(await tr(user_id, 'update_error'))
        return

    await call.answer(await tr(user_id, 'changed'))

    # Показываем обновленную карточку долга
    user_data = await get_user_data(user_id)
    notify_time = user_data.get('notify_time', '09:00')
    updated_debt = await get_debt_by_id(debt_id)

    text = await tr(
        user_id, 'debt_card',
        person=safe_str(updated_debt['person']),
        amount=safe_str(updated_debt['amount']),
        currency=safe_str(updated_debt.get('currency', 'UZS')),
        due=safe_str(updated_debt['due']),
        comment=safe_str(updated_debt['comment']),
        notify_time=notify_time
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=await tr(user_id, 'edit'),
            callback_data=f'edit_{debt_id}_{page}'
        )],
        [
            InlineKeyboardButton(
                text=await tr(user_id, 'close'),
                callback_data=f'close_{debt_id}_{page}'
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'extend'),
                callback_data=f'extend_{debt_id}_{page}'
            ),
            InlineKeyboardButton(
                text=await tr(user_id, 'delete'),
                callback_data=f'del_{debt_id}_{page}'
            )
        ],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_list'),
            callback_data=f'debts_page_{page}'
        )],
        [InlineKeyboardButton(
            text=await tr(user_id, 'to_menu'),
            callback_data='back_main'
        )],
    ])

    await safe_edit_message(call, text, kb)


# === ДОБАВЛЕНИЕ ДОЛГА (Новый подход) ===

@router.callback_query(F.data == 'add_debt')
async def add_debt_start(call: CallbackQuery, state: FSMContext):
    """Начало добавления долга (простой подход)"""
    await state.clear()
    await call.message.edit_text(await tr(call.from_user.id, 'person'))
    await state.set_state(AddDebt.person)


@router.message(AddDebt.person)
async def add_debt_person_simple(message: Message, state: FSMContext):
    """Получение имени должника (простой подход)"""
    await state.update_data(person=message.text)
    await message.answer(await tr(message.from_user.id, 'currency'), reply_markup=await currency_keyboard(message.from_user.id))
    await state.set_state(AddDebt.currency)


@router.callback_query(lambda c: c.data.startswith('cur_'), AddDebt.currency)
async def add_debt_currency_simple(call: CallbackQuery, state: FSMContext):
    """Выбор валюты (простой подход)"""
    currency = call.data.split('_')[1].upper()
    await state.update_data(currency=currency)
    await call.message.edit_text(await tr(call.from_user.id, 'amount'))
    await state.set_state(AddDebt.amount)


@router.message(AddDebt.amount)
async def add_debt_amount_simple(message: Message, state: FSMContext):
    """Получение суммы долга (простой подход)"""
    if not message.text.isdigit():
        await message.answer(await tr(message.from_user.id, 'amount_wrong'))
        return
    await state.update_data(amount=int(message.text))
    suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
    await message.answer(await tr(message.from_user.id, 'due', suggest_date=suggest_date))
    await state.set_state(AddDebt.due)


@router.message(AddDebt.due)
async def add_debt_due_simple(message: Message, state: FSMContext):
    """Получение срока возврата (простой подход)"""
    try:
        datetime.strptime(message.text, '%Y-%m-%d')
    except Exception:
        suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        await message.answer(await tr(message.from_user.id, 'due_wrong', suggest_date=suggest_date))
        return
    await state.update_data(due=message.text)
    await message.answer(await tr(message.from_user.id, 'direction'), reply_markup=await direction_keyboard(message.from_user.id))
    await state.set_state(AddDebt.direction)


@router.callback_query(lambda c: c.data.startswith('dir_'), AddDebt.direction)
async def add_debt_direction_simple(call: CallbackQuery, state: FSMContext):
    """Выбор направления долга (простой подход)"""
    direction = 'gave' if call.data == 'dir_gave' else 'took'
    await state.update_data(direction=direction)
    await call.message.edit_text(await tr(call.from_user.id, 'comment'), reply_markup=await skip_comment_keyboard(call.from_user.id))
    await state.set_state(AddDebt.comment)


@router.message(AddDebt.comment)
async def add_debt_comment_simple(message: Message, state: FSMContext):
    """Получение комментария (простой подход)"""
    data = await state.get_data()
    debt = {
        'person': data['person'],
        'amount': data['amount'],
        'currency': data.get('currency', 'UZS'),
        'direction': data['direction'],
        'date': datetime.now().strftime('%Y-%m-%d'),
        'due': data['due'],
        'comment': message.text if message.text.strip() else '',
        'closed': False
    }
    await add_debt(int(message.from_user.id), debt)
    await message.answer(await tr(message.from_user.id, 'debt_saved'), reply_markup=await main_menu(message.from_user.id))
    await state.clear()


@router.callback_query(F.data == 'skip_comment', AddDebt.comment)
async def skip_comment_simple(call: CallbackQuery, state: FSMContext):
    """Пропуск комментария (простой подход)"""
    data = await state.get_data()
    debt = {
        'person': data['person'],
        'amount': data['amount'],
        'currency': data.get('currency', 'UZS'),
        'direction': data['direction'],
        'date': datetime.now().strftime('%Y-%m-%d'),
        'due': data['due'],
        'comment': '',
        'closed': False
    }
    await add_debt(int(call.from_user.id), debt)
    await call.message.edit_text(await tr(call.from_user.id, 'debt_saved'), reply_markup=await main_menu(call.from_user.id))
    await state.clear()


# === ДОБАВЛЕНИЕ ДОЛГА (Расширенный подход) ===

@router.callback_query(lambda c: c.data == CallbackData.ADD_DEBT)
async def start_add_debt(call: CallbackQuery, state: FSMContext):
    """Начало добавления долга"""
    user_id = call.from_user.id

    try:
        await state.set_state(AddDebt.person)
        person_text = await tr(user_id, 'person')
        kb = await menu_button(user_id)

        await safe_edit_message(call, person_text, kb)

    except Exception as e:
        print(f"❌ Ошибка в start_add_debt: {e}")
        await call.answer("❌ Ошибка начала добавления долга")


@router.message(AddDebt.person)
async def add_debt_person_extended(message: Message, state: FSMContext):
    """Получение имени должника (расширенный подход)"""
    user_id = message.from_user.id

    try:
        person_name = message.text.strip()

        if not person_name or len(person_name) > 50:
            await message.answer("❌ Имя должно быть от 1 до 50 символов")
            return

        await state.update_data(person=person_name)
        await state.set_state(AddDebt.currency)

        currency_text = await tr(user_id, 'currency')
        kb = await currency_keyboard(user_id)

        await message.answer(currency_text, reply_markup=kb)

    except Exception as e:
        print(f"❌ Ошибка в add_debt_person: {e}")


@router.callback_query(lambda c: c.data.startswith('cur_') and hasattr(CallbackData, 'CUR_USD'), AddDebt.currency)
async def add_debt_currency_extended(call: CallbackQuery, state: FSMContext):
    """Выбор валюты (расширенный подход)"""
    user_id = call.from_user.id

    try:
        currency_map = {
            CallbackData.CUR_USD: 'USD',
            CallbackData.CUR_UZS: 'UZS',
            CallbackData.CUR_EUR: 'EUR'
        }

        currency = currency_map.get(call.data)
        if not currency:
            await call.answer("❌ Неизвестная валюта")
            return

        await state.update_data(currency=currency)
        await state.set_state(AddDebt.amount)

        amount_text = await tr(user_id, 'amount')
        kb = await menu_button(user_id)

        await safe_edit_message(call, amount_text, kb)

    except Exception as e:
        print(f"❌ Ошибка в add_debt_currency: {e}")


@router.message(AddDebt.amount)
async def add_debt_amount_extended(message: Message, state: FSMContext):
    """Получение суммы долга (расширенный подход)"""
    user_id = message.from_user.id

    try:
        amount_text = message.text.strip()

        # Проверяем, что введено число
        if not re.match(r'^\d+, amount_text'):
            error_text = await tr(user_id, 'amount_wrong')
            await message.answer(error_text)
            return

        amount = int(amount_text)
        if amount <= 0 or amount > 999999999:
            await message.answer("❌ Сумма должна быть от 1 до 999,999,999")
            return

        await state.update_data(amount=amount)
        await state.set_state(AddDebt.due)

        # Предлагаем дату через неделю
        suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        due_text = await tr(user_id, 'due', suggest_date=suggest_date)
        kb = await menu_button(user_id)

        await message.answer(due_text, reply_markup=kb)

    except Exception as e:
        print(f"❌ Ошибка в add_debt_amount: {e}")


@router.message(AddDebt.due)
async def add_debt_due_extended(message: Message, state: FSMContext):
    """Получение срока возврата (расширенный подход)"""
    user_id = message.from_user.id

    try:
        due_text = message.text.strip()

        # Проверяем формат даты YYYY-MM-DD
        if not re.match(r'^\d{4}-\d{2}-\d{2}, due_text'):
            suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            error_text = await tr(user_id, 'due_wrong', suggest_date=suggest_date)
            await message.answer(error_text)
            return

        # Проверяем корректность даты
        try:
            due_date = datetime.strptime(due_text, '%Y-%m-%d')
            if due_date.date() < datetime.now().date():
                await message.answer("❌ Дата не может быть в прошлом")
                return
        except ValueError:
            suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            error_text = await tr(user_id, 'due_wrong', suggest_date=suggest_date)
            await message.answer(error_text)
            return

        await state.update_data(due=due_text)
        await state.set_state(AddDebt.direction)

        direction_text = await tr(user_id, 'direction')
        kb = await direction_keyboard(user_id)

        await message.answer(direction_text, reply_markup=kb)

    except Exception as e:
        print(f"❌ Ошибка в add_debt_due: {e}")


@router.callback_query(lambda c: c.data.startswith('dir_') and hasattr(CallbackData, 'DIR_GAVE'), AddDebt.direction)
async def add_debt_direction_extended(call: CallbackQuery, state: FSMContext):
    """Выбор направления долга (расширенный подход)"""
    user_id = call.from_user.id

    try:
        direction_map = {
            CallbackData.DIR_GAVE: 'owed',  # Ты дал = тебе должны
            CallbackData.DIR_TOOK: 'owe'  # Ты взял = ты должен
        }

        direction = direction_map.get(call.data)
        if not direction:
            await call.answer("❌ Неизвестное направление")
            return

        await state.update_data(direction=direction)
        await state.set_state(AddDebt.comment)

        comment_text = await tr(user_id, 'comment')
        kb = await skip_comment_keyboard(user_id)

        await safe_edit_message(call, comment_text, kb)

    except Exception as e:
        print(f"❌ Ошибка в add_debt_direction: {e}")


@router.callback_query(lambda c: c.data == CallbackData.SKIP_COMMENT, AddDebt.comment)
async def skip_debt_comment_extended(call: CallbackQuery, state: FSMContext):
    """Пропуск комментария (расширенный подход)"""
    await finish_add_debt(call.from_user.id, state, "")
    await call.answer()


async def finish_add_debt(user_id: int, state: FSMContext, comment: str):
    """Завершение добавления долга"""
    try:
        data = await state.get_data()

        # Проверяем наличие всех данных
        required_fields = ['person', 'currency', 'amount', 'due', 'direction']
        for field in required_fields:
            if field not in data:
                print(f"❌ Отсутствует поле {field} в данных состояния")
                return

        # Подготавливаем данные долга
        debt_data = {
            'person': data['person'],
            'currency': data['currency'],
            'amount': data['amount'],
            'due': data['due'],
            'direction': data['direction'],
            'comment': comment,
            'date': datetime.now().strftime('%Y-%m-%d')
        }

        # Сохраняем долг в базе
        debt_id = await add_debt(user_id, debt_data)

        # Очищаем состояние
        await state.clear()

        # Отправляем подтверждение
        success_text = await tr(user_id, 'debt_saved')
        kb = await main_menu(user_id)

        from bot import bot
        await bot.send_message(user_id, success_text, reply_markup=kb)

        print(f"✅ Долг #{debt_id} добавлен пользователем {user_id}")

    except Exception as e:
        print(f"❌ Ошибка в finish_add_debt: {e}")
        # В случае ошибки очищаем состояние и возвращаем в меню
        await state.clear()
        error_text = await tr(user_id, 'db_error')
        kb = await main_menu(user_id)

        from bot import bot
        await bot.send_message(user_id, error_text, reply_markup=kb)


# === ПРОСМОТР ДОЛГОВ ===

@router.callback_query(lambda c: c.data == CallbackData.MY_DEBTS)
async def show_debts_list(call: CallbackQuery, state: FSMContext):
    """Показать список долгов"""
    user_id = call.from_user.id

    try:
        await state.clear()

        debts = await get_open_debts(user_id)

        if not debts:
            no_debts_text = await tr(user_id, 'no_debts')
            kb = await main_menu(user_id)
            await safe_edit_message(call, no_debts_text, kb)
            return

        # Формируем список долгов
        debts_text = await tr(user_id, 'your_debts') + "\n\n"

        for debt in debts:
            direction_emoji = "💰" if debt['direction'] == 'owed' else "⚠️"
            direction_text = "Вам должны" if debt['direction'] == 'owed' else "Вы должны"

            debts_text += f"{direction_emoji} <b>{debt['person']}</b>\n"
            debts_text += f"💳 {debt['amount']} {debt['currency']}\n"
            debts_text += f"📅 До: {debt['due']}\n"

            if debt['comment']:
                debts_text += f"📝 {debt['comment']}\n"

            debts_text += f"/debt_{debt['id']}\n\n"

        kb = await menu_button(user_id)
        await safe_edit_message(call, debts_text, kb, parse_mode='HTML')

    except Exception as e:
        print(f"❌ Ошибка в show_debts_list: {e}")
        await call.answer("❌ Ошибка при получении списка долгов")