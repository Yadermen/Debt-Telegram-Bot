from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
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
from app.keyboards.texts import tr
from app.keyboards.callbacks import CallbackData, DynamicCallbacks
from aiogram.filters import Command
import pytz

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
                                  callback_data=CallbackData.REMINDERS_MENU)]
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
    await callback.message.answer(
        await tr(callback.from_user.id, "notify_time"),
        reply_markup=await cancel_kb(callback.from_user.id)
    )
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

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ " + await tr(message.from_user.id, "back_btn"),
                                  callback_data=CallbackData.DEBT_REMINDERS)]
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
    await message.answer(await tr(message.from_user.id, "reminder_updated"), reply_markup=back_kb)
    await state.clear()


# --- Создание пользовательских напоминаний ---
@router.callback_query(F.data == CallbackData.ADD_REMINDER)
async def start_add_reminder(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(await tr(callback.from_user.id, "start_add"), reply_markup=await cancel_kb(callback.from_user.id))
    await state.set_state(ReminderForm.text)
    await callback.answer()


@router.message(ReminderForm.text)
async def process_text(message: types.Message, state: FSMContext):
    if message.text.lower().strip() in ("отмена", "cancel"):
        await state.clear()
        await message.answer(await tr(message.from_user.id, "process_cancelled"))
        return

    text = message.text.strip()
    if not text:
        await message.answer(await tr(message.from_user.id, "text_only_please"), reply_markup=await cancel_kb(message.from_user.id))
        return

    await state.update_data(text=text)
    await message.answer(await tr(message.from_user.id, "ask_due"), reply_markup=await cancel_kb(message.from_user.id))
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
        await message.answer(await tr(message.from_user.id, "bad_due"), reply_markup=await cancel_kb(message.from_user.id))
        return

    await state.update_data(due=due)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=await tr(message.from_user.id, "repeat_none"), callback_data=CallbackData.REPEAT_NO)],
            [InlineKeyboardButton(text=await tr(message.from_user.id, "repeat_daily"), callback_data=CallbackData.REPEAT_DAILY)],
            [InlineKeyboardButton(text=await tr(message.from_user.id, "repeat_monthly"), callback_data=CallbackData.REPEAT_MONTHLY)],
            [InlineKeyboardButton(text="⬅️ " + await tr(message.from_user.id, "back_btn"),
                                  callback_data=CallbackData.REMINDERS_MENU)],
        ]
    )
    await message.answer(await tr(message.from_user.id, "ask_repeat"), reply_markup=kb)
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
                callback_data=CallbackData.REMINDERS_MENU
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


@router.message(Command("check_tasks"))
async def check_scheduled_tasks(message: types.Message):
    """Показать все запланированные задачи"""
    from app.utils.scheduler import scheduler

    jobs = scheduler.scheduler.get_jobs()

    # Считаем валютные задачи
    currency_jobs = [j for j in jobs if 'currency' in j.id]
    debt_jobs = [j for j in jobs if 'reminder' in j.id and 'currency' not in j.id]
    global_jobs = [j for j in jobs if 'global' in j.id or j.id == 'due_reminders']

    text = f"📋 Статистика задач:\n\n"
    text += f"💱 Валютных уведомлений: {len(currency_jobs)}\n"
    text += f"📥 Долговых напоминаний: {len(debt_jobs)}\n"
    text += f"🌐 Глобальных задач: {len(global_jobs)}\n"
    text += f"📊 Всего задач: {len(jobs)}\n\n"

    # Показываем валютные задачи для текущего пользователя
    user_currency = [j for j in currency_jobs if str(message.from_user.id) in j.id]
    if user_currency:
        text += f"✅ У тебя ЕСТЬ валютное уведомление:\n"
        for job in user_currency:
            if hasattr(job.trigger, 'hour'):
                text += f"  ⏰ Время: {job.trigger.hour:02d}:{job.trigger.minute:02d}\n"
    else:
        text += f"❌ У тебя НЕТ валютного уведомления!\n"

    await message.answer(text)



@router.message(Command("test_currency"))
async def test_currency_time(message: types.Message):
    """Установить валютное уведомление на следующую минуту (UTC+5)"""
    tz = pytz.timezone("Asia/Tashkent")

    # Берем текущее время в UTC+5 + 1 минута
    now = datetime.now(tz)
    test_time = now + timedelta(minutes=1)
    time_str = test_time.strftime("%H:%M")

    async with get_db() as session:
        await set_user_currency_time(session, message.from_user.id, time_str)

    await message.answer(
        f"✅ Валютное уведомление установлено на {time_str} (Asia/Tashkent)\n"
        f"⏰ Текущее время (UTC+5): {now.strftime('%H:%M')}\n"
        f"📱 Жди уведомление через ~1 минуту!"
    )

    # Перепланируем задачи
    from app.utils.scheduler import scheduler
    await scheduler.schedule_all_reminders()




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


@router.message(Command("debug_jobs"))
async def debug_jobs(message: types.Message):
    """Посмотреть детальную информацию о задачах"""
    from app.utils.scheduler import scheduler

    jobs = scheduler.scheduler.get_jobs()

    # Ищем валютную задачу для этого пользователя
    user_job = None
    for job in jobs:
        if f'user_currency_{message.from_user.id}' == job.id:
            user_job = job
            break

    if not user_job:
        await message.answer("❌ Валютная задача НЕ найдена!")
        return

    # Детальная инфа о задаче
    text = f"✅ Задача найдена!\n\n"
    text += f"🆔 ID: {user_job.id}\n"
    text += f"📝 Функция: {user_job.func.__name__}\n"
    text += f"⏰ Триггер: {user_job.trigger}\n"

    if hasattr(user_job.trigger, 'hour'):
        text += f"🕐 Час: {user_job.trigger.hour}\n"
        text += f"🕐 Минута: {user_job.trigger.minute}\n"

    if hasattr(user_job.trigger, 'timezone'):
        text += f"🌍 Timezone: {user_job.trigger.timezone}\n"

    # Следующий запуск
    next_run = user_job.next_run_time
    if next_run:
        text += f"\n⏭️ Следующий запуск:\n{next_run.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"

        # Текущее время в разных зонах
        from datetime import datetime
        import pytz

        now_utc = datetime.now(pytz.UTC)
        now_tashkent = datetime.now(pytz.timezone('Asia/Tashkent'))

        text += f"\n🕐 Сейчас (UTC): {now_utc.strftime('%H:%M:%S')}"
        text += f"\n🕐 Сейчас (Ташкент): {now_tashkent.strftime('%H:%M:%S')}"

    await message.answer(text)

async def check_reminders(bot):
    now = datetime.now().replace(second=0, microsecond=0)  # текущее время без секунд
    async with get_db() as session:
        # достаём все напоминания, у которых время <= сейчас
        result = await session.execute(
            select(Reminder).where(Reminder.due <= now)
        )
        reminders = result.scalars().all()

        for r in reminders:
            try:
                await bot.send_message(r.user_id, f"⏰ Напоминание: {r.text}")
                await session.delete(r)  # удаляем, если одноразовое
            except Exception as e:
                print(f"[ERROR] Не удалось отправить {r.id}: {e}")

        await session.commit()
