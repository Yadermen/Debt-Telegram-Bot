from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from datetime import datetime, timedelta
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select

from app.database.connection import get_db
from app.database.crud import (
    add_reminder, get_user_reminders,
    get_user_data, enable_debt_reminders, disable_debt_reminders,
    set_debt_reminder_time, update_reminder_text, create_currency_reminder,
    delete_currency_reminders, get_reminder_by_id, set_user_currency_time, get_user_currency_time
)
from app.database.models import Reminder
from app.keyboards import menu_button, main_menu
from app.keyboards.texts import tr
from app.keyboards.callbacks import CallbackData, DynamicCallbacks
from aiogram.filters import Command
import pytz
from app.config import ADMIN_IDS  # Импортируй свой список админов
from app.utils import safe_edit_message

router = Router()


# --- Хелпер для безопасного редактирования ---
async def safe_edit_text(message, text: str, reply_markup=None) -> bool:
    try:
        await message.edit_text(text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            print("[LOG] safe_edit_text: сообщение не изменилось, пропускаем")
            return False
        raise

def is_admin(user_id: int) -> bool:
    """Проверка является ли пользователь админом"""
    return user_id in ADMIN_IDS

# --- FSM состояния ---
class ReminderForm(StatesGroup):
    text = State()
    due = State()
    repeat = State()


class ReminderEditForm(StatesGroup):
    text = State()


class DebtReminderForm(StatesGroup):
    time = State()


# --- Кнопка отмены ---
async def cancel_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=await tr(user_id, "cancel_btn"),
                                  callback_data=CallbackData.BACK_MAIN_REMINDER)]
        ]
    )



# --- Главное меню напоминаний ---
async def reminders_main_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 " + await tr(user_id, "debts_btn"),
                                  callback_data=CallbackData.DEBT_REMINDERS)],
            [InlineKeyboardButton(text="💱 " + await tr(user_id, "currency_btn"),
                                  callback_data=CallbackData.CURRENCY_REMINDERS)],
            [InlineKeyboardButton(text="➕ " + await tr(user_id, "add_reminder_btn"),
                                  callback_data=CallbackData.ADD_REMINDER)],
            [InlineKeyboardButton(text="📋 " + await tr(user_id, "my_reminders_btn"),
                                  callback_data=CallbackData.MY_REMINDERS)],
            [InlineKeyboardButton(text="⬅️ " + await tr(user_id, "back_btn"),
                                  callback_data=CallbackData.BACK_MAIN)],
        ]
    )

@router.callback_query(F.data == CallbackData.BACK_MAIN_REMINDER)
async def back_main_reminder(call: CallbackQuery, state: FSMContext):
    # убираем "часики"
    await call.answer()

    try:
        await state.clear()
        # просто удаляем сообщение с меню
        await call.message.delete()
    except Exception as e:
        print(f"❌ Ошибка в back_main: {e}")
        try:
            await call.answer("❌ Ошибка при удалении сообщения", show_alert=True)
        except:
            pass


@router.callback_query(F.data == CallbackData.REMINDERS_MENU)
async def open_reminders_menu(callback: CallbackQuery):
    async with get_db() as session:
        user_id = callback.from_user.id
        user_data = await get_user_data(user_id)

        # --- Долги ---
        debt_time = user_data.get("notify_time")
        debt_text = (
            await  tr(user_id, "reminder_status_active", time=debt_time)
            if debt_time else
            await tr(user_id, "menu.debts_off")
        )

        # --- Валюта ---
        currency_time = await get_user_currency_time(session, user_id)
        currency_text = (
            await tr(user_id, "menu.currency_on", time=currency_time)
            if currency_time else
            await tr(user_id, "menu.currency_off")
        )

        # --- Итоговый текст ---
        text = f"{debt_text}\n{currency_text}"

        kb = await reminders_main_kb(user_id)

        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                pass
            else:
                raise

        await callback.answer()





# --- Долговые напоминания ---
@router.callback_query(F.data == CallbackData.DEBT_REMINDERS)
async def open_debt_reminders(callback: CallbackQuery):
    kb = await debt_reminders_kb(callback.from_user.id)
    text = await tr(callback.from_user.id, "debt_reminders_text")

    try:
        await callback.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e).lower():
            pass
        else:
            raise

    await callback.answer()


@router.callback_query(F.data == CallbackData.TOGGLE_DEBT_REMINDERS)
async def toggle_debt_reminders(callback: CallbackQuery):
    user_data = await get_user_data(callback.from_user.id)
    enabled_now = user_data.get("notify_time") is not None

    async with get_db() as session:
        if enabled_now:
            await disable_debt_reminders(session, callback.from_user.id)
            print(f"[LOG] Выключены долговые напоминания для user={callback.from_user.id}")
        else:
            await enable_debt_reminders(session, callback.from_user.id, default_time="09:00")
            print(f"[LOG] Включены долговые напоминания для user={callback.from_user.id}, время=09:00")

    await open_debt_reminders(callback)



@router.callback_query(F.data == CallbackData.SETUP_REMINDER_TIME)
async def setup_reminder_time(callback: CallbackQuery, state: FSMContext):
    sent_message = await callback.message.answer(
        await tr(callback.from_user.id, "notify_time"),
        reply_markup=await cancel_kb(callback.from_user.id)
    )

    # Сохраняем ID сообщения бота
    await state.update_data(bot_message_id=sent_message.message_id)
    await state.set_state(DebtReminderForm.time)
    print(f"[LOG] Запрос времени долгового напоминания для user={callback.from_user.id}")
    await callback.answer()


@router.message(DebtReminderForm.time)
async def process_debt_time(message: types.Message, state: FSMContext):
    if message.text.lower() in ("отмена", "cancel"):
        await state.clear()
        print(f"[LOG] Отмена установки времени долгового напоминания user={message.from_user.id}")
        await message.answer(await tr(message.from_user.id, "cancelled"))
        return

    try:
        t = datetime.strptime(message.text.strip(), "%H:%M").time()
    except ValueError:
        await message.answer(await tr(message.from_user.id, "notify_wrong"))
        return

    async with get_db() as session:
        await set_debt_reminder_time(session, message.from_user.id, t.strftime("%H:%M"))
        print(f"[LOG] Установлено время долгового напоминания user={message.from_user.id}, time={t.strftime('%H:%M')}")

    # Получаем ID предыдущего сообщения бота
    data = await state.get_data()
    prev_bot_msg_id = data.get("bot_message_id")

    # Удаляем сообщение пользователя и предыдущее сообщение бота
    if message.chat.type == "private":
        try:
            await message.delete()
            if prev_bot_msg_id:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=prev_bot_msg_id)
        except Exception as e:
            print(f"Ошибка при удалении: {e}")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ " + await tr(message.from_user.id, "back_btn"),
                                  callback_data=CallbackData.BACK_MAIN_REMINDER)]
        ]
    )

    await message.answer(
        await tr(message.from_user.id, "notify_set") + t.strftime("%H:%M"),
        reply_markup=kb
    )
    await state.clear()


# --- Валютные напоминания ---
@router.callback_query(F.data == CallbackData.CURRENCY_REMINDERS)
async def open_currency_reminders(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=await tr(callback.from_user.id, "enable_currency_morning"),
                                  callback_data=CallbackData.ENABLE_MORNING_RATES)],
            [InlineKeyboardButton(text=await tr(callback.from_user.id, "enable_currency_evening"),
                                  callback_data=CallbackData.ENABLE_EVENING_RATES)],
            [InlineKeyboardButton(text=await tr(callback.from_user.id, "disable_currency"),
                                  callback_data=CallbackData.DISABLE_CURRENCY_RATES)],
            [InlineKeyboardButton(text="⬅️ " + await tr(callback.from_user.id, "back_btn"),
                                  callback_data=CallbackData.REMINDERS_MENU)],
        ]
    )
    print(f"[LOG] Открыто меню валютных напоминаний для user={callback.from_user.id}")
    await safe_edit_text(callback.message, await tr(callback.from_user.id, "currency_reminders_text"), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == CallbackData.ENABLE_MORNING_RATES)
async def enable_morning_rates(callback: CallbackQuery):
    async with get_db() as session:
        await set_user_currency_time(session, callback.from_user.id, "07:00")
    await callback.answer(await tr(callback.from_user.id, "reminder_status_currency_morning"))
    await open_currency_reminders(callback)


@router.callback_query(F.data == CallbackData.ENABLE_EVENING_RATES)
async def enable_evening_rates(callback: CallbackQuery):
    async with get_db() as session:
        await set_user_currency_time(session, callback.from_user.id, "17:00")
    await callback.answer(await tr(callback.from_user.id, "reminder_status_currency_evening"))
    await open_currency_reminders(callback)


@router.callback_query(F.data == CallbackData.DISABLE_CURRENCY_RATES)
async def disable_currency_rates(callback: CallbackQuery):
    async with get_db() as session:
        await set_user_currency_time(session, callback.from_user.id, None)
    await callback.answer(await tr(callback.from_user.id, "currency_reminder_status"))
    await open_currency_reminders(callback)




# --- Мои напоминания ---
@router.callback_query(F.data == CallbackData.MY_REMINDERS)
async def open_my_reminders(callback: CallbackQuery):
    async with get_db() as session:
        reminders = await get_user_reminders(session, callback.from_user.id)

    if not reminders:
        text = await tr(callback.from_user.id, "no_reminders")
    else:
        text = await tr(callback.from_user.id, "list_title") + "\n\n"

    kb_rows = []
    for r in reminders:
        kb_rows.append([
            InlineKeyboardButton(
                text=f"⏰ {r.text}",
                callback_data=DynamicCallbacks.reminder_action("view", r.id)
            )
        ])

    kb_rows.append([InlineKeyboardButton(text="⬅️ " + await tr(callback.from_user.id, "back_btn"),
                                         callback_data=CallbackData.REMINDERS_MENU)])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    print(f"[LOG] Открыт список напоминаний для user={callback.from_user.id}, count={len(reminders)})")
    await safe_edit_text(callback.message, text, reply_markup=kb)
    await callback.answer()


# --- Карточка напоминания ---
@router.callback_query(F.data.startswith("reminder_"))
async def reminder_card_handler(callback: CallbackQuery, state: FSMContext):
    try:
        _, action, rid = callback.data.split("_", 2)
        rid = int(rid)
    except Exception:
        await callback.answer()
        return

    user_id = callback.from_user.id

    if action == "view":
        async with get_db() as session:
            r = await get_reminder_by_id(session, rid, user_id)
        if not r:
            await callback.answer(await tr(user_id, "not_found_or_no_access"))
            return

        repeat_text = {
            "none": await tr(user_id, "repeat_none"),
            "daily": await tr(user_id, "repeat_daily"),
            "monthly": await tr(user_id, "repeat_monthly")
        }.get(r.repeat, r.repeat)

        text = f"⏰ {r.text}\n🕒 {r.due}\n🔁 {repeat_text}"

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=await tr(user_id, "edit"),
                                         callback_data=DynamicCallbacks.reminder_action("edit", rid)),
                    InlineKeyboardButton(text=await tr(user_id, "delete"),
                                         callback_data=DynamicCallbacks.reminder_action("delete", rid)),
                ],
                [InlineKeyboardButton(text="⬅️ " + await tr(user_id, "back_btn"),
                                      callback_data=CallbackData.MY_REMINDERS)]
            ]
        )
        await safe_edit_text(callback.message, text, reply_markup=kb)
        await callback.answer()

    elif action == "edit":
        await state.update_data(reminder_id=rid)
        await callback.message.answer(await tr(user_id, "edit_reminder_text"))
        await state.set_state(ReminderEditForm.text)
        await callback.answer(await tr(user_id, "edit"))

    elif action == "delete":
        async with get_db() as session:
            r = await get_reminder_by_id(session, rid, user_id)
            if r:
                await session.delete(r)
                await session.commit()
        await callback.answer(await tr(user_id, "reminder_deleted"))
        await open_my_reminders(callback)

# --- FSM редактирования текста напоминания ---
@router.message(ReminderEditForm.text)
async def edit_text(message: types.Message, state: FSMContext):
    if message.text.lower().strip() in ("отмена", "cancel"):
        await state.clear()
        await message.answer(await tr(message.from_user.id, "cancelled"))
        return

    data = await state.get_data()
    rid = data.get("reminder_id")
    if not rid:
        await message.answer(await tr(message.from_user.id, "db_error"))
        await state.clear()
        return

    async with get_db() as session:
        r = await update_reminder_text(session, rid, message.from_user.id, message.text.strip())

    if not r:
        await message.answer(await tr(message.from_user.id, "not_found_or_no_access"))
        await state.clear()
        return

    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ " + await tr(message.from_user.id, "back_btn"),
                                  callback_data=CallbackData.MY_REMINDERS)]
        ]
    )
    sent_message = await message.answer(await tr(message.from_user.id, "reminder_updated"), reply_markup=back_kb)
    await state.clear()

    if message.chat.type == "private":
        try:
            await message.delete()
            await sent_message.delete()
        except Exception as e:
            print(f"Ошибка при удалении: {e}")


# --- Создание пользовательских напоминаний ---
@router.callback_query(F.data == CallbackData.ADD_REMINDER)
async def start_add_reminder(callback: CallbackQuery, state: FSMContext):
    sent_message = await callback.message.answer(await tr(callback.from_user.id, "start_add"),
                                                 reply_markup=await cancel_kb(callback.from_user.id))

    # Сохраняем ID первого сообщения бота
    await state.update_data(bot_message_id=sent_message.message_id)
    await state.set_state(ReminderForm.text)
    await callback.answer()

@router.callback_query(F.data == CallbackData.BACK_MAIN_REMINDER)
async def back_main_reminder(call: CallbackQuery, state: FSMContext):
        await call.answer(text="")
        """Возврат в главное меню"""
        # 1. Сразу убираем "часики"
        await call.answer()

        try:
            await state.clear()
            text = await tr(call.from_user.id, 'choose_action')
            markup = await main_menu(call.from_user.id)
            await call.send_message(text=text, reply_markup=markup)
        except Exception as e:
            print(f"❌ Ошибка в back_main: {e}")
            try:
                await call.answer("❌ Ошибка перехода в меню", show_alert=True)
            except:
                pass


@router.message(ReminderForm.text)
async def process_text(message: types.Message, state: FSMContext):
    if message.text.lower().strip() in ("отмена", "cancel"):
        await state.clear()
        await message.answer(await tr(message.from_user.id, "process_cancelled"))
        return

    text = message.text.strip()
    if not text:
        sent_message = await message.answer(await tr(message.from_user.id, "text_only_please"),
                                            reply_markup=await cancel_kb(message.from_user.id))
        if message.chat.type == "private":
            try:
                await message.delete()
                await sent_message.delete()
            except Exception as e:
                print(f"Ошибка при удалении: {e}")
        return

    # Сначала сохраняем текст в state
    await state.update_data(text=text)

    # Получаем ID предыдущего сообщения бота (если есть)
    data = await state.get_data()
    prev_bot_msg_id = data.get("bot_message_id")

    # Удаляем сообщение пользователя и предыдущее сообщение бота
    if message.chat.type == "private":
        try:
            await message.delete()
            if prev_bot_msg_id:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=prev_bot_msg_id)
        except Exception as e:
            print(f"Ошибка при удалении: {e}")

    # Отправляем новое сообщение
    sent_message = await message.answer(await tr(message.from_user.id, "ask_due"),
                                        reply_markup=await cancel_kb(message.from_user.id))

    # Сохраняем ID нового сообщения бота
    await state.update_data(bot_message_id=sent_message.message_id)
    await state.set_state(ReminderForm.due)


@router.message(ReminderForm.due)
async def process_due(message: types.Message, state: FSMContext):
    if message.text.lower().strip() in ("отмена", "cancel"):
        await state.clear()
        await message.answer(await tr(message.from_user.id, "process_cancelled"))
        return

    try:
        due = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer(await tr(message.from_user.id, "bad_due"),
                             reply_markup=await cancel_kb(message.from_user.id))
        return

    # Сначала сохраняем дату в state
    await state.update_data(due=due)

    # Получаем ID предыдущего сообщения бота
    data = await state.get_data()
    prev_bot_msg_id = data.get("bot_message_id")

    # Удаляем сообщение пользователя и предыдущее сообщение бота
    if message.chat.type == "private":
        try:
            await message.delete()
            if prev_bot_msg_id:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=prev_bot_msg_id)
        except Exception as e:
            print(f"Ошибка при удалении: {e}")

    # Отправляем следующее сообщение
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=await tr(message.from_user.id, "repeat_none"),
                                  callback_data=CallbackData.REPEAT_NO)],
            [InlineKeyboardButton(text=await tr(message.from_user.id, "repeat_daily"),
                                  callback_data=CallbackData.REPEAT_DAILY)],
            [InlineKeyboardButton(text=await tr(message.from_user.id, "repeat_monthly"),
                                  callback_data=CallbackData.REPEAT_MONTHLY)],
            [InlineKeyboardButton(text="⬅️ " + await tr(message.from_user.id, "back_btn"),
                                  callback_data=CallbackData.BACK_MAIN_REMINDER)],
        ]
    )
    sent_message = await message.answer(await tr(message.from_user.id, "ask_repeat"), reply_markup=kb)

    # Сохраняем ID нового сообщения бота
    await state.update_data(bot_message_id=sent_message.message_id)
    await state.set_state(ReminderForm.repeat)

@router.callback_query(lambda c: c.data.startswith("repeat_"))
async def process_repeat_cb(callback: CallbackQuery, state: FSMContext):
    repeat_map = {
        CallbackData.REPEAT_NO: "none",
        CallbackData.REPEAT_DAILY: "daily",
        CallbackData.REPEAT_MONTHLY: "monthly",
    }
    repeat = repeat_map.get(callback.data, "none")

    data = await state.get_data()
    text = data.get("text")
    due = data.get("due")

    if not text or not due:
        await state.clear()
        await callback.answer(await tr(callback.from_user.id, "db_error"))
        return

    async with get_db() as session:
        await add_reminder(session, user_id=callback.from_user.id, text=text, due=due, repeat=repeat)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ " + await tr(callback.from_user.id, "back_btn"),
                callback_data=CallbackData.BACK_MAIN_REMINDER
            )]
        ]
    )

    repeat_human = {
        "none": await tr(callback.from_user.id, "repeat_none"),
        "daily": await tr(callback.from_user.id, "repeat_daily"),
        "monthly": await tr(callback.from_user.id, "repeat_monthly")
    }.get(repeat, repeat)

    msg = await tr(
        callback.from_user.id,
        "reminder_created",
        text=text,
        datetime=due,
        repeat=repeat_human
    )

    await safe_edit_text(callback.message, msg, reply_markup=kb)

    await state.clear()
    await callback.answer()

async def debt_reminders_kb(user_id: int) -> InlineKeyboardMarkup:
    """
    Динамическая клавиатура для меню долговых напоминаний.
    Если уведомления включены — показываем кнопку "Отключить",
    если выключены — "Включить".
    """
    user_data = await get_user_data(user_id)
    enabled = user_data.get("notify_time") is not None

    toggle_text = (
        await tr(user_id, "disable_debt")
        if enabled else
        await tr(user_id, "enable_debt")
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=CallbackData.TOGGLE_DEBT_REMINDERS)],
            [InlineKeyboardButton(text="⚙ " + await tr(user_id, "set_time"),
                                  callback_data=CallbackData.SETUP_REMINDER_TIME)],
            [InlineKeyboardButton(text="⬅️ " + await tr(user_id, "back_btn"),
                                  callback_data=CallbackData.REMINDERS_MENU)],
        ]
    )
    return kb







@router.message(Command("time"))
async def check_time(message: types.Message):
    """Показать текущее время в разных зонах"""
    utc_now = datetime.now(pytz.UTC)
    tashkent_tz = pytz.timezone('Asia/Tashkent')
    tashkent_now = datetime.now(tashkent_tz)
    local_now = datetime.now()

    text = f"""
🕐 **Проверка времени**

🌍 UTC: `{utc_now.strftime('%Y-%m-%d %H:%M:%S')}`
🇺🇿 Ташкент (UTC+5): `{tashkent_now.strftime('%Y-%m-%d %H:%M:%S')}`
💻 Сервер: `{local_now.strftime('%Y-%m-%d %H:%M:%S')}`

✅ Бот работает по времени: **{tashkent_tz}**
    """
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("test_currency"))
async def test_currency_notification(message: Message):
    """Установить валютное уведомление через 2 минуты"""
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Эта команда доступна только администраторам")
        return

    from app.utils.scheduler import scheduler
    from app.database.crud import set_user_currency_time
    from app.database.connection import get_db

    import pytz

    user_id = message.from_user.id
    job_id = f'user_currency_{user_id}'

    # Время по UTC+5 (Ташкент)
    tashkent_tz = pytz.timezone('Asia/Tashkent')
    now_utc5 = datetime.now(tashkent_tz)
    test_time = now_utc5 + timedelta(minutes=2)
    time_str = test_time.strftime("%H:%M")

    try:
        # Обновляем БД
        async with get_db() as session:
            await set_user_currency_time(session, user_id, time_str)

        # Перезапускаем все задачи чтобы применить изменения
        from app.utils.scheduler import schedule_all_reminders
        await schedule_all_reminders()

        await message.answer(
            f"✅ Валютное уведомление установлено на <b>{time_str}</b>\n"
            f"⏳ Ждите ~2 минуты\n\n"
            f"Задача: {job_id}"
        )

        # Проверяем что задача добавлена
        job = scheduler.scheduler.get_job(job_id)
        print(f"✅ Тест валютного уведомления: {user_id} -> {time_str}")
        print(f"📋 Задача в scheduler: {job is not None}")
        if job:
            print(f"   Next run: {job.next_run_time}")
            print(f"   Trigger: {job.trigger}")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
        print(f"❌ Ошибка теста: {e}")



@router.message(Command("check_jobs"))
async def check_jobs(message: Message):
    from app.utils.scheduler import scheduler
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Эта команда доступна только администраторам")
        return

    currency_jobs = [j for j in scheduler.scheduler.get_jobs() if 'currency' in j.id]

    text = f"💱 Валютных задач: {len(currency_jobs)}\n\n"
    for job in currency_jobs[:5]:  # Показываем только первые 5
        text += f"• {job.id}\n  Next: {job.next_run_time}\n\n"

    await message.answer(text)

async def check_reminders(bot):
    now = datetime.now().replace(second=0, microsecond=0)  # текущее время без секунд
    async with get_db() as session:
        result = await session.execute(
            select(Reminder).where(Reminder.due <= now)
        )
        reminders = result.scalars().all()

        for r in reminders:
            try:
                kb = await menu_button(r.user_id)  # формируем клавиатуру
                await bot.send_message(
                    r.user_id,
                    f"⏰ {r.text}",
                    reply_markup=kb
                )
                await session.delete(r)  # удаляем, если одноразовое
            except Exception as e:
                print(f"[ERROR] Не удалось отправить {r.id}: {e}")

        await session.commit()

