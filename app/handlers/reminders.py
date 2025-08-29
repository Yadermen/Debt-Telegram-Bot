"""
Обработчики для напоминаний - исправленная версия с полной обработкой ошибок
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
import re

# Заменить все импорты в начале файла на:
try:
    from app.database import get_user_data, save_user_notify_time
    from app.keyboards import tr
    from app.states import SetNotifyTime
    from app.utils import safe_edit_message
    from app.utils.scheduler import schedule_all_reminders
except ImportError as e:
    print(f"❌ Ошибка импорта в reminders.py: {e}")

router = Router()


def is_text_message(message: Message) -> bool:
    """Проверить, что сообщение содержит только текст"""
    try:
        return message.content_type == 'text' and message.text and message.text.strip()
    except Exception as e:
        print(f"❌ Ошибка в is_text_message: {e}")
        return False


@router.callback_query(F.data == 'reminders_menu')
async def reminders_menu(call: CallbackQuery, state: FSMContext):
    """Меню напоминаний"""
    user_id = call.from_user.id
    try:
        await state.clear()

        try:
            user_data = await get_user_data(user_id)
        except Exception as db_e:
            print(f"❌ Ошибка получения данных пользователя: {db_e}")
            try:
                await call.message.answer(await tr(user_id, 'db_error'))
                return
            except Exception as msg_e:
                print(f"❌ Ошибка отправки сообщения об ошибке БД: {msg_e}")
                return

        current = user_data.get('notify_time', '09:00')

        try:
            text = await tr(user_id, 'reminder_time', time=current if current else '-')

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=await tr(user_id, 'reminder_change'),
                    callback_data='reminder_change_time'
                )],
                [InlineKeyboardButton(
                    text=await tr(user_id, 'to_menu'),
                    callback_data='back_main'
                )],
            ])

            await safe_edit_message(call, text, kb)
        except Exception as ui_e:
            print(f"❌ Ошибка формирования UI: {ui_e}")
            try:
                await call.answer("❌ Ошибка интерфейса")
            except:
                pass

    except Exception as e:
        print(f"❌ Критическая ошибка в reminders_menu: {e}")
        try:
            await call.answer("❌ Ошибка меню напоминаний")
        except:
            pass


@router.callback_query(F.data == 'reminder_change_time')
async def reminder_change_time(call: CallbackQuery, state: FSMContext):
    """Изменение времени напоминаний"""
    user_id = call.from_user.id

    try:
        prompt_text = await tr(user_id, 'notify_time')
        await call.message.edit_text(prompt_text)
        await state.set_state(SetNotifyTime.waiting_for_time)

    except Exception as e:
        print(f"❌ Ошибка в reminder_change_time: {e}")
        try:
            await call.answer("❌ Ошибка изменения времени")
        except:
            pass


@router.message(SetNotifyTime.waiting_for_time)
async def set_notify_time_handler(message: Message, state: FSMContext):
    """Установка времени уведомлений"""
    user_id = message.from_user.id

    try:
        # Проверяем тип сообщения
        if not is_text_message(message):
            try:
                error_text = await tr(user_id, 'notify_wrong')
                await message.answer(error_text)
                return
            except Exception as inner_e:
                print(f"❌ Ошибка при отправке сообщения об ошибке типа: {inner_e}")
                await state.clear()
                return

        time_text = message.text.strip()

        try:
            # Разрешаем разные форматы ввода: 9, 9:0, 9:00, 09:0, 09:00, 9:30, 09:30
            if ':' in time_text:
                parts = time_text.split(':')
                if len(parts) != 2:
                    raise ValueError("Неверный формат времени")
                hour = int(parts[0])
                minute = int(parts[1])
            else:
                hour = int(time_text)
                minute = 0

            # Проверяем корректность времени
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError("Время вне допустимого диапазона")

            # Форматируем время с ведущими нулями
            formatted_time = '{:02d}:{:02d}'.format(hour, minute)

        except (ValueError, TypeError) as time_e:
            print(f"❌ Ошибка валидации времени: {time_e}")
            try:
                await message.answer(await tr(user_id, 'notify_wrong'))
                return
            except Exception as msg_e:
                print(f"❌ Ошибка отправки сообщения об ошибке времени: {msg_e}")
                await state.clear()
                return

        try:
            await save_user_notify_time(user_id, formatted_time)
        except Exception as save_e:
            print(f"❌ Ошибка сохранения времени уведомлений: {save_e}")
            try:
                await message.answer(await tr(user_id, 'save_notify_error'))
                return
            except Exception as msg_e:
                print(f"❌ Ошибка отправки сообщения об ошибке сохранения: {msg_e}")
                await state.clear()
                return

        # Перепланируем все напоминания после изменения времени
        try:
            await schedule_all_reminders()
        except Exception as schedule_e:
            print(f"❌ Ошибка перепланирования напоминаний: {schedule_e}")
            # Не прерываем выполнение, так как время уже сохранено

        try:
            user_data = await get_user_data(user_id)
        except Exception as get_e:
            print(f"❌ Ошибка получения обновленных данных: {get_e}")
            user_data = {'notify_time': formatted_time}

        try:
            success_text = await tr(user_id, 'notify_set')
            time_info = await tr(user_id, 'reminder_time', time=user_data.get('notify_time', '-'))

            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=await tr(user_id, 'to_menu'),
                    callback_data='back_main'
                )],
            ])

            await message.answer(success_text + time_info, reply_markup=kb)
            await state.clear()

        except Exception as ui_e:
            print(f"❌ Ошибка формирования успешного ответа: {ui_e}")
            await state.clear()
            try:
                await message.answer("✅ Время уведомлений изменено")
            except:
                pass

    except Exception as e:
        print(f"❌ Критическая ошибка в set_notify_time_handler: {e}")
        try:
            await state.clear()
            error_text = await tr(user_id, 'system_error')
            await message.answer(error_text)
        except Exception as inner_e:
            print(f"❌ Критическая ошибка в обработке ошибки: {inner_e}")


async def reminder_debt_actions(debt_id: int, page: int, user_id: int) -> InlineKeyboardMarkup:
    """Кнопки для карточки долга в напоминаниях"""
    try:
        return InlineKeyboardMarkup(inline_keyboard=[
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
                text=await tr(user_id, 'to_menu'),
                callback_data='back_main'
            )]
        ])
    except Exception as e:
        print(f"❌ Ошибка в reminder_debt_actions: {e}")
        # Возвращаем базовую клавиатуру в случае ошибки
        try:
            return InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="В меню",
                    callback_data='back_main'
                )]
            ])
        except:
            return InlineKeyboardMarkup(inline_keyboard=[])