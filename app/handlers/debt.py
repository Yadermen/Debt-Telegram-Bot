"""
Обработчики для работы с долгами - исправленная версия с полной обработкой ошибок
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from datetime import datetime, timedelta
import re

try:
    from ..database import (
        add_debt, get_open_debts, get_debt_by_id, update_debt,
        soft_delete_debt, clear_user_debts, get_user_data, delete_debt
    )
    from ..keyboards import (
        tr, main_menu, currency_keyboard, direction_keyboard,
        skip_comment_keyboard, menu_button, debt_actions_keyboard,
        confirm_keyboard, edit_fields_keyboard, currency_edit_keyboard,
        CallbackData, DynamicCallbacks, debts_list_keyboard_paginated,
        debts_list_keyboard, safe_str, my_debts_menu
    )
    from ..states import AddDebt, EditDebt
    from ..utils import safe_edit_message
except ImportError as e:
    print(f"❌ Ошибка импорта в debt.py: {e}")

router = Router()


# === УТИЛИТЫ ===

def is_text_message(message: Message) -> bool:
    """Проверить, что сообщение содержит только текст"""
    try:
        return message.content_type == 'text' and message.text and message.text.strip()
    except Exception as e:
        print(f"❌ Ошибка в is_text_message: {e}")
        return False


def validate_person_name(name: str) -> bool:
    """Валидация имени человека (поддерживает узбекские символы)"""
    try:
        if not name or len(name.strip()) < 1 or len(name.strip()) > 50:
            return False

        # Разрешаем латиницу, кириллицу, цифры, пробелы и основные знаки препинания
        # Включаем узбекские специальные символы: ʻ, ʼ, ʾ, ʿ, ğ, ž, ç, ş, ü, ö, и др.
        allowed_pattern = r"^[\w\s\-\.'ʻʼʾʿğžçşüöıəȯḩṭẓ]+$"
        return bool(re.match(allowed_pattern, name.strip(), re.IGNORECASE | re.UNICODE))
    except Exception as e:
        print(f"❌ Ошибка в validate_person_name: {e}")
        return False


# === НАВИГАЦИЯ ===

@router.callback_query(F.data == 'back_main')
async def back_main(call: CallbackQuery, state: FSMContext):
    await call.answer(text="fff")
    """Возврат в главное меню"""
    # 1. Сразу убираем "часики"
    await call.answer()

    try:
        await state.clear()
        text = await tr(call.from_user.id, 'choose_action')
        markup = await main_menu(call.from_user.id)
        await safe_edit_message(call, text, markup)
    except Exception as e:
        print(f"❌ Ошибка в back_main: {e}")
        try:
            await call.answer("❌ Ошибка перехода в меню", show_alert=True)
        except:
            pass






# === ПРОСМОТР ДОЛГОВ ===

@router.callback_query(F.data == 'my_debts')
async def show_debts_simple(call: CallbackQuery, state: FSMContext):
    """Показать список долгов"""
    user_id = call.from_user.id
    try:
        await state.clear()
        debts = await get_open_debts(user_id)

        if not debts:
            text = await tr(user_id, 'no_debts')
            # Возвращаем в подменю "Мои долги" вместо главного меню
            markup = await my_debts_menu(user_id)
            await safe_edit_message(call, text, markup)
            return

        text = await tr(user_id, 'your_debts')
        markup = await debts_list_keyboard_paginated(debts, user_id, page=0)
        await safe_edit_message(call, text, markup)

    except Exception as e:
        print(f"❌ Ошибка в show_debts_simple: {e}")
        try:
            await call.answer("❌ Ошибка загрузки долгов")
        except:
            pass


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

        if not debts:
            text = await tr(user_id, 'no_debts')
            markup = await main_menu(user_id)
            await safe_edit_message(call, text, markup)
            return

        text = await tr(user_id, 'your_debts')
        markup = await debts_list_keyboard_paginated(debts, user_id, page=page)
        await safe_edit_message(call, text, markup)

    except Exception as e:
        print(f"❌ Ошибка в debts_page_navigation: {e}")
        try:
            await call.answer("❌ Ошибка навигации")
        except:
            pass


# === КАРТОЧКА ДОЛГА ===

@router.callback_query(lambda c: c.data.startswith('debtcard_'))
async def debt_card(call: CallbackQuery, state: FSMContext):
    """Показать карточку долга"""
    try:
        parts = call.data.split('_')
        debt_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0
    except Exception as e:
        print(f"❌ Ошибка парсинга debt_card: {e}")
        try:
            await call.answer("❌ Ошибка данных")
        except:
            pass
        return

    user_id = call.from_user.id

    try:
        await state.update_data(current_page=page)
        debt = await get_debt_by_id(debt_id)

        if not debt or debt['user_id'] != user_id:
            await call.message.answer(await tr(user_id, 'not_found_or_no_access'))
            return

        # Получаем notify_time пользователя
        user_data = await get_user_data(user_id)
        notify_time = user_data.get('notify_time', '09:00')

        # Определяем тип долга
        direction = debt.get('direction', 'owed')
        text_key = 'debt_card_owed' if direction == 'owed' else 'debt_card_owe'

        text = await tr(
            user_id, text_key,
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

    except Exception as e:
        print(f"❌ Ошибка в debt_card: {e}")
        try:
            await call.answer("❌ Ошибка загрузки долга")
        except:
            pass


# === ДОБАВЛЕНИЕ ДОЛГА ===

@router.callback_query(F.data == 'add_debt')
async def add_debt_start(call: CallbackQuery, state: FSMContext):
    """Начало добавления долга"""
    try:
        await state.clear()
        await call.message.edit_text(await tr(call.from_user.id, 'person'))
        await state.set_state(AddDebt.person)
    except Exception as e:
        print(f"❌ Ошибка в add_debt_start: {e}")
        try:
            await call.answer("❌ Ошибка начала добавления")
        except:
            pass


@router.message(AddDebt.person)
async def add_debt_person_simple(message: Message, state: FSMContext):
    """Получение имени должника с поддержкой узбекского языка"""
    user_id = message.from_user.id

    try:
        # Проверяем тип сообщения
        if not is_text_message(message):
            try:
                error_text = await tr(user_id, 'text_only_please')

                # Создаем кнопку возврата в меню
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(
                        text=await tr(user_id, 'to_menu'),
                        callback_data='back_main'
                    )]
                ])

                await message.answer(error_text, reply_markup=kb)
                await state.clear()
                return
            except Exception as inner_e:
                print(f"❌ Ошибка при обработке нетекстового сообщения: {inner_e}")
                await state.clear()
                return

        person_name = message.text.strip()

        # Валидация имени с поддержкой узбекских символов
        if not validate_person_name(person_name):
            try:
                error_text = await tr(user_id, 'person_name_invalid')
                await message.answer(error_text)
                return
            except Exception as inner_e:
                print(f"❌ Ошибка при отправке сообщения об ошибке валидации: {inner_e}")
                await state.clear()
                return

        await state.update_data(person=person_name)

        try:
            currency_text = await tr(user_id, 'currency')
            kb = await currency_keyboard(user_id)
            await message.answer(currency_text, reply_markup=kb)
            await state.set_state(AddDebt.currency)
        except Exception as inner_e:
            print(f"❌ Ошибка при переходе к выбору валюты: {inner_e}")
            await state.clear()
            try:
                error_text = await tr(user_id, 'system_error')
                markup = await main_menu(user_id)
                await message.answer(error_text, reply_markup=markup)
            except:
                pass

    except Exception as e:
        print(f"❌ Критическая ошибка в add_debt_person_simple: {e}")
        try:
            await state.clear()
            error_text = await tr(user_id, 'system_error')
            markup = await main_menu(user_id)
            await message.answer(error_text, reply_markup=markup)
        except Exception as inner_e:
            print(f"❌ Критическая ошибка в обработке ошибки: {inner_e}")


@router.callback_query(lambda c: c.data.startswith('cur_'), AddDebt.currency)
async def add_debt_currency_simple(call: CallbackQuery, state: FSMContext):
    """Выбор валюты"""
    try:
        currency = call.data.split('_')[1].upper()

        # Валидация валюты
        if currency not in ['USD', 'UZS', 'EUR']:
            await call.answer("❌ Неизвестная валюта")
            return

        await state.update_data(currency=currency)
        user_id = call.from_user.id

        amount_text = await tr(user_id, 'amount')
        await call.message.edit_text(amount_text)
        await state.set_state(AddDebt.amount)

    except Exception as e:
        print(f"❌ Ошибка в add_debt_currency_simple: {e}")
        try:
            await call.answer("❌ Ошибка выбора валюты")
            await state.clear()
        except:
            pass


@router.message(AddDebt.amount)
async def add_debt_amount_simple(message: Message, state: FSMContext):
    """Получение суммы долга"""
    user_id = message.from_user.id

    try:
        # Проверяем тип сообщения
        if not is_text_message(message):
            try:
                error_text = await tr(user_id, 'amount_wrong')
                await message.answer(error_text)
                return
            except Exception as inner_e:
                print(f"❌ Ошибка при отправке сообщения об ошибке типа: {inner_e}")
                await state.clear()
                return

        amount_text = message.text.strip()

        # Проверяем, что это число
        if not amount_text.isdigit():
            try:
                error_text = await tr(user_id, 'amount_wrong')
                await message.answer(error_text)
                return
            except Exception as inner_e:
                print(f"❌ Ошибка при отправке сообщения об ошибке числа: {inner_e}")
                await state.clear()
                return

        amount = int(amount_text)
        if amount <= 0 or amount > 999999999:
            try:
                error_text = await tr(user_id, 'amount_range_error')
                await message.answer(error_text)
                return
            except Exception as inner_e:
                print(f"❌ Ошибка при отправке сообщения об ошибке диапазона: {inner_e}")
                await state.clear()
                return

        await state.update_data(amount=amount)

        try:
            suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            due_text = await tr(user_id, 'due', suggest_date=suggest_date)
            await message.answer(due_text)
            await state.set_state(AddDebt.due)
        except Exception as inner_e:
            print(f"❌ Ошибка при переходе к дате: {inner_e}")
            await state.clear()
            try:
                error_text = await tr(user_id, 'system_error')
                markup = await main_menu(user_id)
                await message.answer(error_text, reply_markup=markup)
            except:
                pass

    except Exception as e:
        print(f"❌ Критическая ошибка в add_debt_amount_simple: {e}")
        try:
            await state.clear()
            error_text = await tr(user_id, 'system_error')
            markup = await main_menu(user_id)
            await message.answer(error_text, reply_markup=markup)
        except:
            pass


@router.message(AddDebt.due)
async def add_debt_due_simple(message: Message, state: FSMContext):
    """Получение срока возврата"""
    user_id = message.from_user.id

    try:
        # Проверяем тип сообщения
        if not is_text_message(message):
            try:
                suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
                error_text = await tr(user_id, 'due_wrong', suggest_date=suggest_date)
                await message.answer(error_text)
                return
            except Exception as inner_e:
                print(f"❌ Ошибка при отправке сообщения об ошибке типа даты: {inner_e}")
                await state.clear()
                return

        due_text = message.text.strip()

        # Валидация даты
        try:
            due_date = datetime.strptime(due_text, '%Y-%m-%d')
            if due_date.date() < datetime.now().date():
                try:
                    await message.answer(await tr(user_id, 'date_in_past'))
                    return
                except Exception as inner_e:
                    print(f"❌ Ошибка при отправке сообщения о прошлой дате: {inner_e}")
                    await state.clear()
                    return
        except ValueError:
            try:
                suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
                error_text = await tr(user_id, 'due_wrong', suggest_date=suggest_date)
                await message.answer(error_text)
                return
            except Exception as inner_e:
                print(f"❌ Ошибка при отправке сообщения об ошибке формата даты: {inner_e}")
                await state.clear()
                return

        await state.update_data(due=due_text)

        try:
            direction_text = await tr(user_id, 'direction')
            kb = await direction_keyboard(user_id)
            await message.answer(direction_text, reply_markup=kb)
            await state.set_state(AddDebt.direction)
        except Exception as inner_e:
            print(f"❌ Ошибка при переходе к направлению: {inner_e}")
            await state.clear()
            try:
                error_text = await tr(user_id, 'system_error')
                markup = await main_menu(user_id)
                await message.answer(error_text, reply_markup=markup)
            except:
                pass

    except Exception as e:
        print(f"❌ Критическая ошибка в add_debt_due_simple: {e}")
        try:
            await state.clear()
            error_text = await tr(user_id, 'system_error')
            markup = await main_menu(user_id)
            await message.answer(error_text, reply_markup=markup)
        except:
            pass


@router.callback_query(lambda c: c.data.startswith('dir_'), AddDebt.direction)
async def add_debt_direction_simple(call: CallbackQuery, state: FSMContext):
    """Выбор направления долга"""
    try:
        direction_data = call.data.split('_')[1]

        # Конвертируем в правильный формат направления
        direction = 'owed' if direction_data == 'gave' else 'owe'

        await state.update_data(direction=direction)
        user_id = call.from_user.id

        comment_text = await tr(user_id, 'comment')
        kb = await skip_comment_keyboard(user_id)
        await call.message.edit_text(comment_text, reply_markup=kb)
        await state.set_state(AddDebt.comment)

    except Exception as e:
        print(f"❌ Ошибка в add_debt_direction_simple: {e}")
        try:
            await call.answer("❌ Ошибка выбора направления")
            await state.clear()
        except:
            pass


@router.message(AddDebt.comment)
async def add_debt_comment_simple(message: Message, state: FSMContext):
    """Получение комментария"""
    user_id = message.from_user.id

    try:
        # Проверяем тип сообщения
        comment = ""
        if is_text_message(message):
            comment = message.text.strip()
        else:
            # Если не текст, используем пустой комментарий
            try:
                warning_text = await tr(user_id, 'comment_text_only')
                await message.answer(warning_text)
            except Exception as inner_e:
                print(f"❌ Ошибка при отправке предупреждения о комментарии: {inner_e}")

        await finish_add_debt(user_id, state, comment, message)

    except Exception as e:
        print(f"❌ Критическая ошибка в add_debt_comment_simple: {e}")
        try:
            await state.clear()
            error_text = await tr(user_id, 'system_error')
            markup = await main_menu(user_id)
            await message.answer(error_text, reply_markup=markup)
        except:
            pass


@router.callback_query(F.data == 'skip_comment', AddDebt.comment)
async def skip_comment_simple(call: CallbackQuery, state: FSMContext):
    """Пропуск комментария"""
    try:
        await finish_add_debt(call.from_user.id, state, "", None, call)
    except Exception as e:
        print(f"❌ Ошибка в skip_comment_simple: {e}")
        try:
            await call.answer("❌ Ошибка сохранения")
            await state.clear()
        except:
            pass


async def finish_add_debt(user_id: int, state: FSMContext, comment: str, message: Message = None, call: CallbackQuery = None):
    """Завершение добавления долга"""
    try:
        data = await state.get_data()

        # Проверяем наличие всех данных
        required_fields = ['person', 'currency', 'amount', 'due', 'direction']
        for field in required_fields:
            if field not in data:
                print(f"❌ Отсутствует поле {field} в данных состояния")
                try:
                    error_text = await tr(user_id, 'incomplete_data')
                    kb = await main_menu(user_id)

                    if message:
                        await message.answer(error_text, reply_markup=kb)
                    elif call:
                        await call.message.edit_text(error_text, reply_markup=kb)

                    await state.clear()
                    return
                except Exception as inner_e:
                    print(f"❌ Ошибка при отправке сообщения о неполных данных: {inner_e}")
                    await state.clear()
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

        try:
            # Сохраняем долг в базе
            debt_id = await add_debt(user_id, debt_data)

            # Очищаем состояние
            await state.clear()

            # Отправляем подтверждение
            success_text = await tr(user_id, 'debt_saved')
            kb = await main_menu(user_id)

            if message:
                await message.answer(success_text, reply_markup=kb)
            elif call:
                await call.message.edit_text(success_text, reply_markup=kb)

            print(f"✅ Долг #{debt_id} добавлен пользователем {user_id}")

        except Exception as db_e:
            print(f"❌ Ошибка сохранения в БД: {db_e}")
            await state.clear()
            try:
                error_text = await tr(user_id, 'save_debt_error')
                kb = await main_menu(user_id)

                if message:
                    await message.answer(error_text, reply_markup=kb)
                elif call:
                    await call.message.edit_text(error_text, reply_markup=kb)
            except Exception as msg_e:
                print(f"❌ Ошибка отправки сообщения об ошибке БД: {msg_e}")

    except Exception as e:
        print(f"❌ Критическая ошибка в finish_add_debt: {e}")
        try:
            # В случае ошибки очищаем состояние и возвращаем в меню
            await state.clear()
            error_text = await tr(user_id, 'save_debt_error')
            kb = await main_menu(user_id)

            if message:
                await message.answer(error_text, reply_markup=kb)
            elif call:
                await call.message.edit_text(error_text, reply_markup=kb)
        except Exception as inner_e:
            print(f"❌ Критическая ошибка в finish_add_debt cleanup: {inner_e}")


# === УДАЛЕНИЕ ДОЛГОВ ===

@router.callback_query(lambda c: c.data.startswith('del_'))
async def del_debt_confirm(call: CallbackQuery, state: FSMContext):
    """Подтверждение удаления долга"""
    try:
        parts = call.data.split('_')
        debt_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0

        user_id = call.from_user.id
        await state.update_data(current_page=page)

        debt = await get_debt_by_id(debt_id)

        if not debt or debt['user_id'] != user_id:
            await call.message.answer(await tr(user_id, 'not_found_or_no_access'))
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

        confirm_text = await tr(user_id, 'confirm_del')
        await call.message.edit_text(confirm_text, reply_markup=kb)

    except Exception as e:
        print(f"❌ Ошибка в del_debt_confirm: {e}")
        try:
            await call.answer("❌ Ошибка удаления")
        except:
            pass


@router.callback_query(lambda c: c.data.startswith('confirm_del_'))
async def del_debt(call: CallbackQuery, state: FSMContext):
    """Удаление долга"""
    try:
        parts = call.data.split('_')
        debt_id = int(parts[2])
        page = int(parts[3]) if len(parts) > 3 else 0

        user_id = call.from_user.id
        debt = await get_debt_by_id(debt_id)

        if not debt or debt['user_id'] != user_id:
            await call.message.answer(await tr(user_id, 'not_found_or_no_access'))
            return

        await delete_debt(debt_id)

        # Получаем обновленный список долгов
        debts = await get_open_debts(user_id)

        if not debts:
            # Если долгов больше нет, возвращаем в главное меню
            text = await tr(user_id, 'debt_deleted')
            markup = await main_menu(user_id)
            await safe_edit_message(call, text, markup)
        else:
            # Если долги есть, показываем список
            text = await tr(user_id, 'debt_deleted') + '\n\n' + await tr(user_id, 'your_debts')
            markup = await debts_list_keyboard_paginated(debts, user_id, page=page)
            await safe_edit_message(call, text, markup)

    except Exception as e:
        print(f"❌ Ошибка в del_debt: {e}")
        try:
            await call.answer("❌ Ошибка удаления долга")
        except:
            pass


# === РЕДАКТИРОВАНИЕ ДОЛГА ===

@router.callback_query(lambda c: c.data.startswith('edit_'))
async def edit_debt_menu(call: CallbackQuery, state: FSMContext):
    """Меню редактирования долга"""
    try:
        parts = call.data.split('_')
        debt_id = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 0

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

        edit_menu_text = await tr(user_id, 'edit_what')
        await call.message.edit_text(edit_menu_text, reply_markup=kb)

    except Exception as e:
        print(f"❌ Ошибка в edit_debt_menu: {e}")
        try:
            await call.answer("❌ Ошибка редактирования")
        except:
            pass


@router.callback_query(lambda c: c.data.startswith('editfield_'))
async def edit_debt_field(call: CallbackQuery, state: FSMContext):
    """Выбор поля для редактирования"""
    try:
        _, field, debt_id, page = call.data.split('_')
        debt_id = int(debt_id)
        page = int(page)
        user_id = call.from_user.id

        debt = await get_debt_by_id(debt_id)
        if not debt or debt['user_id'] != user_id:
            await call.message.answer(await tr(user_id, 'not_found_or_no_access'))
            return

        await state.update_data(edit_debt_id=debt_id, edit_field=field, edit_page=page)

        # Обработка разных полей
        if field == 'person':
            prompt_text = await tr(user_id, 'editfield_person')
            await call.message.edit_text(prompt_text)
            await state.set_state(EditDebt.edit_value)
        elif field == 'amount':
            prompt_text = await tr(user_id, 'editfield_amount')
            await call.message.edit_text(prompt_text)
            await state.set_state(EditDebt.edit_value)
        elif field == 'currency':
            # Показываем клавиатуру выбора валюты
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='USD', callback_data=f'editcur_USD_{debt_id}_{page}')],
                [InlineKeyboardButton(text='UZS', callback_data=f'editcur_UZS_{debt_id}_{page}')],
                [InlineKeyboardButton(text='EUR', callback_data=f'editcur_EUR_{debt_id}_{page}')],
                [InlineKeyboardButton(text=await tr(user_id, 'to_menu'), callback_data='back_main')],
            ])
            currency_text = await tr(user_id, 'editfield_currency')
            await call.message.edit_text(currency_text, reply_markup=kb)
            return
        elif field == 'due':
            suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
            prompt_text = await tr(user_id, 'editfield_due', suggest_date=suggest_date)
            await call.message.edit_text(prompt_text)
            await state.set_state(EditDebt.edit_value)
        elif field == 'comment':
            prompt_text = await tr(user_id, 'editfield_comment')
            await call.message.edit_text(prompt_text)
            await state.set_state(EditDebt.edit_value)
        else:
            # Fallback для неизвестных полей
            prompt_text = await tr(user_id, 'editfield_person')
            await call.message.edit_text(prompt_text)
            await state.set_state(EditDebt.edit_value)

    except Exception as e:
        print(f"❌ Ошибка в edit_debt_field: {e}")
        try:
            await call.answer("❌ Ошибка редактирования поля")
            await state.clear()
        except:
            pass


@router.message(EditDebt.edit_value)
async def edit_debt_value(message: Message, state: FSMContext):
    """Обработка нового значения поля"""
    user_id = message.from_user.id

    try:
        # Проверяем тип сообщения
        if not is_text_message(message):
            try:
                error_text = await tr(user_id, 'text_only_please')
                await message.answer(error_text)
                return
            except Exception as inner_e:
                print(f"❌ Ошибка при отправке сообщения об ошибке типа в редактировании: {inner_e}")
                await state.clear()
                return

        try:
            data = await state.get_data()
            debt_id = data.get('edit_debt_id')
            field = data.get('edit_field')
            page = data.get('edit_page', 0)
            val = message.text.strip()

            debt = await get_debt_by_id(debt_id)
            if not debt or debt['user_id'] != user_id:
                await message.answer(await tr(user_id, 'not_found_or_no_access'))
                return

            updates = {}

            # Валидация в зависимости от поля
            if field == 'amount':
                if not val.isdigit():
                    await message.answer(await tr(user_id, 'amount_wrong'))
                    return
                amount = int(val)
                if amount <= 0 or amount > 999999999:
                    await message.answer(await tr(user_id, 'amount_range_error'))
                    return
                updates['amount'] = amount

            elif field == 'due':
                try:
                    date_obj = datetime.strptime(val, '%Y-%m-%d')
                    if date_obj.date() < datetime.now().date():
                        await message.answer(await tr(user_id, 'date_in_past'))
                        return
                except ValueError:
                    suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
                    await message.answer(await tr(user_id, 'due_wrong', suggest_date=suggest_date))
                    return
                updates['due'] = val

            elif field == 'person':
                if not validate_person_name(val):
                    await message.answer(await tr(user_id, 'person_name_invalid'))
                    return
                updates['person'] = val

            elif field == 'comment':
                updates['comment'] = val
            else:
                updates[field] = val

            # Обновляем долг в базе
            await update_debt(debt_id, updates)

            # Показываем успешное сообщение
            success_text = await tr(user_id, 'changed')
            await message.answer(success_text)

            # Получаем обновленные данные долга и показываем карточку
            await show_updated_debt_card(message, user_id, debt_id, page)
            await state.clear()

        except Exception as process_e:
            print(f"❌ Ошибка обработки редактирования: {process_e}")
            await state.clear()
            try:
                error_text = await tr(user_id, 'update_error')
                markup = await main_menu(user_id)
                await message.answer(error_text, reply_markup=markup)
            except:
                pass

    except Exception as e:
        print(f"❌ Критическая ошибка в edit_debt_value: {e}")
        try:
            await state.clear()
            error_text = await tr(user_id, 'update_error')
            markup = await main_menu(user_id)
            await message.answer(error_text, reply_markup=markup)
        except:
            pass


async def show_updated_debt_card(message: Message, user_id: int, debt_id: int, page: int):
    """Показать обновленную карточку долга"""
    try:
        user_data = await get_user_data(user_id)
        notify_time = user_data.get('notify_time', '09:00')
        updated_debt = await get_debt_by_id(debt_id)

        if not updated_debt:
            return

        direction = updated_debt.get('direction', 'owed')
        text_key = 'debt_card_owed' if direction == 'owed' else 'debt_card_owe'

        text = await tr(
            user_id, text_key,
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

    except Exception as e:
        print(f"❌ Ошибка в show_updated_debt_card: {e}")


# === РЕДАКТИРОВАНИЕ ВАЛЮТЫ ===

@router.callback_query(lambda c: c.data.startswith('editcur_'))
async def edit_currency_callback(call: CallbackQuery, state: FSMContext):
    """Обработка выбора валюты при редактировании"""
    try:
        _, currency, debt_id, page = call.data.split('_')
        debt_id = int(debt_id)
        page = int(page)
        user_id = call.from_user.id

        # Валидация валюты
        if currency not in ['USD', 'UZS', 'EUR']:
            await call.answer("❌ Неизвестная валюта")
            return

        debt = await get_debt_by_id(debt_id)
        if not debt or debt['user_id'] != user_id:
            await call.message.answer(await tr(user_id, 'not_found_or_no_access'))
            return

        await update_debt(debt_id, {'currency': currency})
        await call.answer(await tr(user_id, 'changed'))

        # Показываем обновленную карточку долга
        await show_updated_debt_card_from_callback(call, user_id, debt_id, page)

    except Exception as e:
        print(f"❌ Ошибка в edit_currency_callback: {e}")
        try:
            await call.answer("❌ Ошибка изменения валюты")
        except:
            pass


async def show_updated_debt_card_from_callback(call: CallbackQuery, user_id: int, debt_id: int, page: int):
    """Показать обновленную карточку долга из callback"""
    try:
        user_data = await get_user_data(user_id)
        notify_time = user_data.get('notify_time', '09:00')
        updated_debt = await get_debt_by_id(debt_id)

        if not updated_debt:
            return

        direction = updated_debt.get('direction', 'owed')
        text_key = 'debt_card_owed' if direction == 'owed' else 'debt_card_owe'

        text = await tr(
            user_id, text_key,
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

    except Exception as e:
        print(f"❌ Ошибка в show_updated_debt_card_from_callback: {e}")


# === ЗАКРЫТИЕ ДОЛГОВ ===

@router.callback_query(lambda c: c.data.startswith('close_'))
async def close_debt_confirm(call: CallbackQuery, state: FSMContext):
    """Подтверждение закрытия долга"""
    try:
        debt_id = int(call.data.split('_')[1])
        user_id = call.from_user.id

        debt = await get_debt_by_id(debt_id)
        if not debt or debt['user_id'] != user_id:
            await call.message.answer(await tr(user_id, 'not_found_or_no_access'))
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

        confirm_text = await tr(user_id, 'confirm_close')
        await call.message.edit_text(confirm_text, reply_markup=kb)

    except Exception as e:
        print(f"❌ Ошибка в close_debt_confirm: {e}")
        try:
            await call.answer("❌ Ошибка закрытия")
        except:
            pass


@router.callback_query(lambda c: c.data.startswith('confirm_close_'))
async def close_debt(call: CallbackQuery, state: FSMContext):
    """Закрытие долга"""
    try:
        debt_id = int(call.data.split('_')[2])
        user_id = call.from_user.id

        debt = await get_debt_by_id(debt_id)
        if not debt or debt['user_id'] != user_id:
            await call.message.answer(await tr(user_id, 'not_found_or_no_access'))
            return

        await update_debt(debt_id, {'closed': True})

        text = await tr(user_id, 'debt_closed')
        markup = await main_menu(user_id)
        await safe_edit_message(call, text, markup)

    except Exception as e:
        print(f"❌ Ошибка в close_debt: {e}")
        try:
            await call.answer("❌ Ошибка закрытия долга")
        except:
            pass


# === ПРОДЛЕНИЕ СРОКА ДОЛГА ===

@router.callback_query(lambda c: c.data.startswith('extend_'))
async def extend_debt_start(call: CallbackQuery, state: FSMContext):
    """Начало продления срока долга"""
    try:
        debt_id = int(call.data.split('_')[1])
        user_id = call.from_user.id

        debt = await get_debt_by_id(debt_id)
        if not debt or debt['user_id'] != user_id:
            await call.message.answer(await tr(user_id, 'not_found_or_no_access'))
            return

        await state.update_data(extend_debt_id=debt_id)
        suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        prompt_text = await tr(user_id, 'due', suggest_date=suggest_date)
        await call.message.edit_text(prompt_text)
        await state.set_state(EditDebt.extend_due)

    except Exception as e:
        print(f"❌ Ошибка в extend_debt_start: {e}")
        try:
            await call.answer("❌ Ошибка продления")
        except:
            pass


@router.message(EditDebt.extend_due)
async def extend_debt_value(message: Message, state: FSMContext):
    """Обработка новой даты для продления"""
    user_id = message.from_user.id

    try:
        # Проверяем тип сообщения
        if not is_text_message(message):
            try:
                suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
                error_text = await tr(user_id, 'due_wrong', suggest_date=suggest_date)
                await message.answer(error_text)
                return
            except Exception as inner_e:
                print(f"❌ Ошибка при отправке сообщения об ошибке типа в продлении: {inner_e}")
                await state.clear()
                return

        try:
            data = await state.get_data()
            val = message.text.strip()

            try:
                date_obj = datetime.strptime(val, '%Y-%m-%d')
                if date_obj.date() < datetime.now().date():
                    await message.answer(await tr(user_id, 'date_in_past'))
                    return
            except ValueError:
                suggest_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
                error_text = await tr(user_id, 'due_wrong', suggest_date=suggest_date)
                await message.answer(error_text)
                return

            # Обновляем дату
            new_due = val  # Не добавляем 7 дней, используем точную дату
            await update_debt(data['extend_debt_id'], {'due': new_due})

            success_text = await tr(user_id, 'date_changed')
            markup = await main_menu(user_id)
            await message.answer(success_text, reply_markup=markup)
            await state.clear()

        except Exception as process_e:
            print(f"❌ Ошибка обработки продления: {process_e}")
            await state.clear()
            try:
                error_text = await tr(user_id, 'update_error')
                markup = await main_menu(user_id)
                await message.answer(error_text, reply_markup=markup)
            except:
                pass

    except Exception as e:
        print(f"❌ Критическая ошибка в extend_debt_value: {e}")
        try:
            await state.clear()
            error_text = await tr(user_id, 'update_error')
            markup = await main_menu(user_id)
            await message.answer(error_text, reply_markup=markup)
        except:
            pass


# === ОЧИСТКА ВСЕХ ДОЛГОВ ===

@router.callback_query(F.data == 'clear_all')
async def clear_all_confirm(call: CallbackQuery, state: FSMContext):
    """Подтверждение очистки всех долгов"""
    try:
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

        confirm_text = await tr(user_id, 'clear_all_confirm')
        await call.message.edit_text(confirm_text, reply_markup=kb)

    except Exception as e:
        print(f"❌ Ошибка в clear_all_confirm: {e}")
        try:
            await call.answer("❌ Ошибка")
        except:
            pass


@router.callback_query(F.data == 'confirm_clear_all')
async def clear_all(call: CallbackQuery, state: FSMContext):
    """Очистить все долги"""
    try:
        user_id = call.from_user.id
        await clear_user_debts(user_id)

        text = await tr(user_id, 'all_deleted')
        markup = await main_menu(user_id)
        await safe_edit_message(call, text, markup)

    except Exception as e:
        print(f"❌ Ошибка в clear_all: {e}")
        try:
            await call.answer("❌ Ошибка очистки")
        except:
            pass


@router.callback_query(F.data == 'cancel_action')
async def cancel_action(call: CallbackQuery, state: FSMContext):
    """Отмена действия"""
    try:
        user_id = call.from_user.id
        text = await tr(user_id, 'cancelled')  # Используем правильный ключ перевода
        markup = await main_menu(user_id)
        await safe_edit_message(call, text, markup)

    except Exception as e:
        print(f"❌ Ошибка в cancel_action: {e}")
        try:
            await call.answer("❌ Ошибка отмены")
        except:
            pass
