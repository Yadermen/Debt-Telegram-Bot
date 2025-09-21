from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from datetime import datetime
from aiogram.exceptions import TelegramBadRequest

from app.database.connection import get_db
from app.database.crud import (
    add_reminder, get_user_reminders,
    get_user_data, enable_debt_reminders, disable_debt_reminders,
    set_debt_reminder_time, update_reminder_text, create_currency_reminder,
    delete_currency_reminders, get_reminder_by_id, set_user_currency_time, get_user_currency_time
)
from app.keyboards.texts import tr
from app.keyboards.callbacks import CallbackData, DynamicCallbacks

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
def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data=CallbackData.REMINDERS_MENU)]]
    )


# --- Главное меню напоминаний ---
async def reminders_main_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 " + await tr(user_id, "debts_btn"),
                                  callback_data=CallbackData.DEBT_REMINDERS)],
            [InlineKeyboardButton(text="💱 " + await tr(user_id, "currency_btn"),
                                  callback_data=CallbackData.CURRENCY_REMINDERS)],
            [InlineKeyboardButton(text="➕ Добавить напоминание", callback_data=CallbackData.ADD_REMINDER)],
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
        print(debt_time)
        debt_text = f"✅ Напоминание долгов в {debt_time}" if debt_time else "❌ Напоминания о долгах выключены"

        # --- Валюта ---
        currency_time = await get_user_currency_time(session, user_id)
        print("currency_time:", currency_time)
        currency_text = f"✅ Курс валют ежедневно в {currency_time}" if currency_time else "❌ Напоминания о курсе валют выключены"

        # --- Итоговый текст ---
        text = f"{debt_text}\n{currency_text}"

        kb = await reminders_main_kb(user_id)

        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e).lower():
                # Игнорируем ситуацию, когда текст не изменился
                pass
            else:
                raise

        await callback.answer()




# --- Долговые напоминания ---
@router.callback_query(F.data == CallbackData.DEBT_REMINDERS)
async def open_debt_reminders(callback: CallbackQuery):
    # ОСТАВЛЯЮ ТВОЮ КРАСИВУЮ КЛАВИАТУРУ, НЕ МЕНЯЮ РАЗМЕТКУ
    kb = await debt_reminders_kb(callback.from_user.id)  # используй свою функцию/клаву как у тебя было
    text = await tr(callback.from_user.id, "debt_reminders_text")  # или твой текст, как было

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
    await callback.message.answer("Введите время напоминания (например: 09:00)", reply_markup=cancel_kb())
    await state.set_state(DebtReminderForm.time)
    print(f"[LOG] Запрос времени долгового напоминания для user={callback.from_user.id}")
    await callback.answer()


@router.message(DebtReminderForm.time)
async def process_debt_time(message: types.Message, state: FSMContext):
    if message.text.lower() in ("отмена", "cancel"):
        await state.clear()
        print(f"[LOG] Отмена установки времени долгового напоминания user={message.from_user.id}")
        await message.answer("❌ Настройка отменена")
        return

    try:
        t = datetime.strptime(message.text.strip(), "%H:%M").time()
    except ValueError:
        await message.answer("❌ Неверный формат. Введите время в формате ЧЧ:ММ")
        return

    async with get_db() as session:
        await set_debt_reminder_time(session, message.from_user.id, t.strftime("%H:%M"))
        print(f"[LOG] Установлено время долгового напоминания user={message.from_user.id}, time={t.strftime('%H:%M')}")

    # Добавляем кнопку «Назад» в меню долговых напоминаний
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=CallbackData.DEBT_REMINDERS)]
        ]
    )

    await message.answer(f"✅ Время напоминания установлено: {t.strftime('%H:%M')}", reply_markup=kb)
    await state.clear()



# --- Валютные напоминания ---
@router.callback_query(F.data == CallbackData.CURRENCY_REMINDERS)
async def open_currency_reminders(callback: CallbackQuery):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🌅 Утро (07:00)", callback_data=CallbackData.ENABLE_MORNING_RATES)],
            [InlineKeyboardButton(text="🌆 Вечер (17:00)", callback_data=CallbackData.ENABLE_EVENING_RATES)],
            [InlineKeyboardButton(text="❌ Отключить", callback_data=CallbackData.DISABLE_CURRENCY_RATES)],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=CallbackData.REMINDERS_MENU)],
        ]
    )
    print(f"[LOG] Открыто меню валютных напоминаний для user={callback.from_user.id}")
    await safe_edit_text(callback.message, "Настройка напоминаний о курсе валют", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == CallbackData.ENABLE_MORNING_RATES)
async def enable_morning_rates(callback: CallbackQuery):
    async with get_db() as session:
        await set_user_currency_time(session, callback.from_user.id, "07:00")
    await callback.answer("🌅 Напоминание о курсе валют установлено на 07:00")
    await open_currency_reminders(callback)

@router.callback_query(F.data == CallbackData.ENABLE_EVENING_RATES)
async def enable_evening_rates(callback: CallbackQuery):
    async with get_db() as session:
        await set_user_currency_time(session, callback.from_user.id, "17:00")
    await callback.answer("🌆 Напоминание о курсе валют установлено на 17:00")
    await open_currency_reminders(callback)

@router.callback_query(F.data == CallbackData.DISABLE_CURRENCY_RATES)
async def disable_currency_rates(callback: CallbackQuery):
    async with get_db() as session:
        await set_user_currency_time(session, callback.from_user.id, None)
    await callback.answer("❌ Напоминания о курсе валют отключены")
    await open_currency_reminders(callback)




# --- Мои напоминания ---
@router.callback_query(F.data == CallbackData.MY_REMINDERS)
async def open_my_reminders(callback: CallbackQuery):
    async with get_db() as session:
        reminders = await get_user_reminders(session, callback.from_user.id)

    if not reminders:
        text = "У вас пока нет напоминаний."
    else:
        text = "Мои напоминания:\n\n"

    kb_rows = []
    for r in reminders:
        kb_rows.append([
            InlineKeyboardButton(
                text=f"⏰ {r.text}",
                callback_data=DynamicCallbacks.reminder_action("view", r.id)
            )
        ])

    kb_rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=CallbackData.REMINDERS_MENU)])
    kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    print(f"[LOG] Открыт список напоминаний для user={callback.from_user.id}, count={len(reminders)})")
    await safe_edit_text(callback.message, text, reply_markup=kb)
    await callback.answer()


# --- Парсер callback-данных для напоминаний ---
def parse_reminder_callback(data: str):
    # Ожидаемый формат: reminder_view_<id> / reminder_edit_<id> / reminder_delete_<id>
    if not data.startswith("reminder_"):
        return None, None
    try:
        _, action, rid = data.split("_", 2)
        return action, int(rid)
    except Exception:
        return None, None


# --- Карточка напоминания (просмотр/редактирование/удаление) ---
@router.callback_query(F.data.startswith("reminder_"))
async def reminder_card_handler(callback: CallbackQuery, state: FSMContext):
    action, rid = parse_reminder_callback(callback.data)
    if not action or not rid:
        await callback.answer()
        return

    user_id = callback.from_user.id

    if action == "view":
        async with get_db() as session:
            r = await get_reminder_by_id(session, rid, user_id)
        if not r:
            await callback.answer("Напоминание не найдено")
            return

        repeat_text = {"none": "Без повтора", "daily": "Ежедневно", "monthly": "Ежемесячно"}.get(r.repeat, r.repeat)
        text = f"⏰ {r.text}\n🕒 {r.due}\n🔁 {repeat_text}"

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✏️ Изменить", callback_data=DynamicCallbacks.reminder_action("edit", rid)),
                    InlineKeyboardButton(text="❌ Удалить", callback_data=DynamicCallbacks.reminder_action("delete", rid)),
                ],
                [InlineKeyboardButton(text="⬅️ Назад", callback_data=CallbackData.MY_REMINDERS)]
            ]
        )
        print(f"[LOG] Открыта карточка напоминания id={rid} для user={user_id}")
        await safe_edit_text(callback.message, text, reply_markup=kb)
        await callback.answer()

    elif action == "edit":
        await state.update_data(reminder_id=rid)
        print(f"[LOG] Начато редактирование напоминания id={rid} для user={user_id}")
        await callback.message.answer("Введите новый текст напоминания или напишите «отмена»")
        await state.set_state(ReminderEditForm.text)
        await callback.answer("Изменить напоминание")

    elif action == "delete":
        async with get_db() as session:
            r = await get_reminder_by_id(session, rid, user_id)
            if r:
                await session.delete(r)
                await session.commit()
                print(f"[LOG] Удалено напоминание id={rid} для user={user_id}")

        await callback.answer("Удалено")
        await open_my_reminders(callback)


# --- FSM редактирования текста напоминания ---
# BEGIN PATCH: back button after reminder edit
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@router.message(ReminderEditForm.text)
async def edit_text(message: types.Message, state: FSMContext):
    if message.text.lower().strip() in ("отмена", "cancel"):
        await state.clear()
        await message.answer("❌ Редактирование отменено")
        return

    data = await state.get_data()
    rid = data.get("reminder_id")
    if not rid:
        await message.answer("Что-то пошло не так. Попробуйте ещё раз.")
        await state.clear()
        return

    async with get_db() as session:
        r = await update_reminder_text(session, rid, message.from_user.id, message.text.strip())

    if not r:
        await message.answer("Напоминание не найдено")
        await state.clear()
        return

    # Добавляем кнопку Назад в "Мои напоминания"
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=CallbackData.MY_REMINDERS)]
        ]
    )
    await message.answer("✅ Текст обновлён", reply_markup=back_kb)
    await state.clear()
# END PATCH



# --- Создание пользовательских напоминаний (полный FSM + отмена + логи) ---
@router.callback_query(F.data == CallbackData.ADD_REMINDER)
async def start_add_reminder(callback: CallbackQuery, state: FSMContext):
    print(f"[LOG] ADD_REMINDER: клик по кнопке, user={callback.from_user.id}")
    # Важно: создаём новое сообщение, чтобы не конфликтовать с edit_text
    await callback.message.answer("Введите текст напоминания", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data=CallbackData.REMINDERS_MENU)]]
    ))
    await state.set_state(ReminderForm.text)
    print(f"[LOG] ADD_REMINDER: установлен state=ReminderForm.text, user={callback.from_user.id}")
    await callback.answer()


@router.message(ReminderForm.text)
async def process_text(message: types.Message, state: FSMContext):
    print(f"[LOG] ADD_REMINDER[TEXT]: вход, user={message.from_user.id}, text={message.text!r}")
    if message.text.lower().strip() in ("отмена", "cancel"):
        await state.clear()
        print(f"[LOG] ADD_REMINDER[TEXT]: отмена, user={message.from_user.id}")
        await message.answer("❌ Создание отменено")
        return

    text = message.text.strip()
    if not text:
        await message.answer("❌ Текст пустой. Введите текст напоминания или «отмена».", reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data=CallbackData.REMINDERS_MENU)]]
        ))
        return

    await state.update_data(text=text)
    print(f"[LOG] ADD_REMINDER[TEXT]: сохранён текст, user={message.from_user.id}")
    await message.answer("Введите дату и время в формате YYYY-MM-DD HH:MM", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data=CallbackData.REMINDERS_MENU)]]
    ))
    await state.set_state(ReminderForm.due)
    print(f"[LOG] ADD_REMINDER: установлен state=ReminderForm.due, user={message.from_user.id}")


@router.message(ReminderForm.due)
async def process_due(message: types.Message, state: FSMContext):
    print(f"[LOG] ADD_REMINDER[DUE]: вход, user={message.from_user.id}, due_text={message.text!r}")
    if message.text.lower().strip() in ("отмена", "cancel"):
        await state.clear()
        print(f"[LOG] ADD_REMINDER[DUE]: отмена, user={message.from_user.id}")
        await message.answer("❌ Создание отменено")
        return

    try:
        due = datetime.strptime(message.text.strip(), "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer("❌ Неверный формат. Введите дату и время: YYYY-MM-DD HH:MM", reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data=CallbackData.REMINDERS_MENU)]]
        ))
        return

    await state.update_data(due=due)
    print(f"[LOG] ADD_REMINDER[DUE]: сохранена дата/время={due.isoformat(' ')}, user={message.from_user.id}")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Без повтора", callback_data=CallbackData.REPEAT_NO)],
            [InlineKeyboardButton(text="Ежедневно", callback_data=CallbackData.REPEAT_DAILY)],
            [InlineKeyboardButton(text="Ежемесячно", callback_data=CallbackData.REPEAT_MONTHLY)],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=CallbackData.REMINDERS_MENU)],
        ]
    )
    await message.answer("Выберите повтор", reply_markup=kb)
    await state.set_state(ReminderForm.repeat)
    print(f"[LOG] ADD_REMINDER: установлен state=ReminderForm.repeat, user={message.from_user.id}")


@router.callback_query(
    F.data.in_({CallbackData.REPEAT_NO, CallbackData.REPEAT_DAILY, CallbackData.REPEAT_MONTHLY}),
    ReminderForm.repeat
)
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

    print(f"[LOG] ADD_REMINDER[REPEAT]: вход, user={callback.from_user.id}, repeat={repeat}, data_present={bool(text and due)}")

    if not text or not due:
        await state.clear()
        print(f"[LOG] ADD_REMINDER[REPEAT]: нет text/due в state, user={callback.from_user.id}")
        await callback.answer("Произошла ошибка, попробуйте снова.")
        return

    async with get_db() as session:
        r = await add_reminder(session, user_id=callback.from_user.id, text=text, due=due, repeat=repeat)

    print(f"[LOG] ADD_REMINDER: создано напоминание id={getattr(r, 'id', None)}, user={callback.from_user.id}, repeat={repeat}, due={due.isoformat(' ')}")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=CallbackData.REMINDERS_MENU)]
        ]
    )
    repeat_human = "Без повтора" if repeat == "none" else ("Ежедневно" if repeat == "daily" else "Ежемесячно")
    await safe_edit_text(
        callback.message,
        f"✅ Напоминание создано\n\n📝 {text}\n🕒 {due}\n🔁 {repeat_human}",
        reply_markup=kb
    )
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

    toggle_text = "❌ Отключить напоминания" if enabled else "⏰ Включить напоминания"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=toggle_text, callback_data=CallbackData.TOGGLE_DEBT_REMINDERS)],
            [InlineKeyboardButton(text="⚙ Установить время", callback_data=CallbackData.SETUP_REMINDER_TIME)],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=CallbackData.REMINDERS_MENU)],
        ]
    )
    return kb
