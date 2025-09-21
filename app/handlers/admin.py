from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime
import asyncio
import os
import traceback

from app.database import (
    get_all_users,
    get_user_count,
    get_active_debts_count,
    save_scheduled_message,
)
from app.states import AdminBroadcast
from app.utils.broadcast import send_broadcast_to_all_users, send_scheduled_broadcast_with_stats

# Пытаемся импортировать планировщик (если есть)
try:
    from app.utils.scheduler import scheduler  # ожидается объект с полем .scheduler (APScheduler)
except Exception as e:
    print(f"[admin.py] ⚠️ Не удалось импортировать scheduler: {e}")
    scheduler = None

router = Router()
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []
print(f"[admin.py] ✅ ADMIN_IDS: {ADMIN_IDS}")


# ============================ Вспомогательные ============================

def is_admin(user_id: int) -> bool:
    res = user_id in ADMIN_IDS
    print(f"[is_admin] {user_id} -> {res}")
    return res


async def get_admin_stats_safely():
    print("[get_admin_stats_safely] Получаем статистику")
    user_count, active_debts = 0, 0
    for _ in range(3):
        try:
            user_count = await get_user_count()
            break
        except Exception as e:
            print(f"[get_admin_stats_safely] Ошибка user_count: {e}")
            await asyncio.sleep(0.1)
    for _ in range(3):
        try:
            active_debts = await get_active_debts_count()
            break
        except Exception as e:
            print(f"[get_admin_stats_safely] Ошибка active_debts: {e}")
            await asyncio.sleep(0.1)
    return user_count, active_debts


def build_broadcast_menu(data: dict) -> InlineKeyboardMarkup:
    print(f"[build_broadcast_menu] data={data}")
    rows = [[InlineKeyboardButton(text="⚙️ Настроить кнопки", callback_data="setup_buttons")]]
    if data.get("broadcast_photo"):
        rows.append([
            InlineKeyboardButton(text="🔄 Изменить фото", callback_data="add_broadcast_photo"),
            InlineKeyboardButton(text="🗑 Удалить фото", callback_data="remove_broadcast_photo"),
        ])
    else:
        rows.append([InlineKeyboardButton(text="📷 Добавить фото", callback_data="add_broadcast_photo")])
    rows.append([
        InlineKeyboardButton(text="📤 Отправить сейчас", callback_data="send_broadcast_now"),
        InlineKeyboardButton(text="⏰ Запланировать", callback_data="schedule_broadcast"),
    ])
    rows.append([InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_buttons_preview_kb(buttons: list[dict]) -> InlineKeyboardMarkup:
    print(f"[build_buttons_preview_kb] buttons={buttons}")
    kb_rows = []
    # Показываем текущие кнопки (кликабельные URL, чисто для визуализации)
    for idx, btn in enumerate(buttons):
        title = f"{idx+1}. {btn.get('text', 'Без текста')}"
        url = btn.get("url") or "https://example.com"
        kb_rows.append([InlineKeyboardButton(text=title, url=url)])
    kb_rows.append([
        InlineKeyboardButton(text="➕ Добавить", callback_data="add_button"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data="remove_button_prompt"),
    ])
    kb_rows.append([InlineKeyboardButton(text="✅ Готово", callback_data="buttons_done")])
    return InlineKeyboardMarkup(inline_keyboard=kb_rows)


def build_final_keyboard(buttons: list[dict]) -> InlineKeyboardMarkup | None:
    print(f"[build_final_keyboard] buttons={buttons}")
    if not buttons:
        return None
    rows = []
    for btn in buttons:
        text = (btn.get("text") or "").strip()
        url = (btn.get("url") or "").strip()
        if text and url:
            rows.append([InlineKeyboardButton(text=text, url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


async def safe_edit_or_send(call: CallbackQuery, text: str):
    """Если текущее сообщение текстовое — редактируем, иначе отправляем новое."""
    try:
        if call.message.text:
            return await call.message.edit_text(text)
        else:
            return await call.message.answer(text)
    except Exception as e:
        print(f"[safe_edit_or_send] edit_text/answer failed: {e}")
        try:
            return await call.message.answer(text)
        except Exception as e2:
            print(f"[safe_edit_or_send] answer failed too: {e2}")


def log_exc(prefix: str, e: Exception):
    print(f"{prefix}: {e}")
    traceback.print_exc()


# ============================ Главная панель ============================

@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    print(f"[admin_panel] /admin от {message.from_user.id}")
    await state.clear()
    if not is_admin(message.from_user.id):
        return await message.answer("Нет доступа")
    user_count, active_debts = await get_admin_stats_safely()
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👥 Пользователи ({user_count})", callback_data="admin_users")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
    ])
    await message.answer(f"📊 Пользователей: {user_count}\n📄 Активных долгов: {active_debts}", reply_markup=kb)


@router.callback_query(F.data == "admin_back")
async def admin_back(call: CallbackQuery, state: FSMContext):
    print(f"[admin_back] от {call.from_user.id}")
    await call.answer()

    if not is_admin(call.from_user.id):
        return

    await state.clear()
    user_count, active_debts = await get_admin_stats_safely()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👥 Пользователи ({user_count})", callback_data="admin_users")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
    ])

    text = f"📊 Пользователей: {user_count}\n📄 Активных долгов: {active_debts}"

    # Безопасно: если текущее сообщение текстовое — редактируем, иначе шлём новое
    try:
        if call.message.text:
            await call.message.edit_text(text, reply_markup=kb)
        else:
            await call.message.answer(text, reply_markup=kb)
    except Exception as e:
        print(f"[admin_back] edit_text error: {e}")
        await call.message.answer(text, reply_markup=kb)



# ============================ Пользователи и статистика ============================

@router.callback_query(F.data == "admin_users")
async def admin_users_list(call: CallbackQuery):
    print(f"[admin_users_list] от {call.from_user.id}")
    await call.answer()
    if not is_admin(call.from_user.id):
        return
    try:
        users = await get_all_users()
        cnt = len(users) if users else 0
        print(f"[admin_users_list] users={cnt}")
        if not users:
            return await safe_edit_or_send(call, "Пользователей нет")
        text = "\n\n".join([f"{i+1}. ID: {u['user_id']}" for i, u in enumerate(users[:10])])
        if len(users) > 10:
            text += f"\n... и ещё {len(users)-10}"
        await safe_edit_or_send(call, text)
    except Exception as e:
        log_exc("[admin_users_list] error", e)
        await safe_edit_or_send(call, "❌ Ошибка получения списка пользователей")


@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    print(f"[admin_stats] от {call.from_user.id}")
    await call.answer()
    if not is_admin(call.from_user.id):
        return

    user_count, active_debts = await get_admin_stats_safely()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_back")]
    ])

    await safe_edit_or_send(
        call,
        f"📊 Пользователей: {user_count}\n📄 Активных долгов: {active_debts}"
    )
    await call.message.answer("Выбериfте действие:", reply_markup=kb)


# ============================ Создание рассылки: текст ============================

@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(call: CallbackQuery, state: FSMContext):
    print(f"[start_broadcast] от {call.from_user.id}")
    await call.answer()
    await state.set_state(AdminBroadcast.waiting_for_text)
    await state.update_data(broadcast_text=None, broadcast_photo=None, buttons=[])
    await safe_edit_or_send(call, "📢 Введите текст рассылки:")


@router.message(AdminBroadcast.waiting_for_text)
async def set_broadcast_text(message: Message, state: FSMContext):
    print(f"[set_broadcast_text] text='{message.text}'")
    await state.update_data(broadcast_text=message.text)
    kb = build_broadcast_menu(await state.get_data())
    await message.answer(f"📢 Текст:\n{message.text}", reply_markup=kb)


# ============================ Фото ============================

@router.callback_query(F.data == "add_broadcast_photo")
async def add_photo(call: CallbackQuery, state: FSMContext):
    print(f"[add_photo] от {call.from_user.id}")
    await call.answer()
    await state.set_state(AdminBroadcast.waiting_for_photo)
    await safe_edit_or_send(call, "📷 Отправьте фото для рассылки:")


@router.message(AdminBroadcast.waiting_for_photo, F.photo)
async def set_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    print(f"[set_photo] file_id={photo_id}")
    await state.update_data(broadcast_photo=photo_id)
    data = await state.get_data()

    # Предпросмотр с фото
    final_kb = build_final_keyboard(data.get("buttons", []))
    await message.answer_photo(photo_id, caption=f"📢 Предпросмотр:\n\n{data.get('broadcast_text') or ''}", reply_markup=final_kb)
    print("[set_photo] отправлен предпросмотр с фото")

    # Меню ниже
    menu_kb = build_broadcast_menu(data)
    await message.answer("⚙️ Меню рассылки:", reply_markup=menu_kb)
    print("[set_photo] отправлено меню рассылки")

    await state.set_state(AdminBroadcast.waiting_for_text)
    print("[set_photo] состояние -> waiting_for_text")



# ==== Удаление фото: сразу новый предпросмотр без фото + меню ====
@router.callback_query(F.data == "remove_broadcast_photo")
async def remove_photo(call: CallbackQuery, state: FSMContext):
    print(f"[remove_photo] от {call.from_user.id}")
    await call.answer()

    # 1) Удаляем фото из state
    await state.update_data(broadcast_photo=None)
    data = await state.get_data()
    print(f"[remove_photo] фото сброшено. state={data}")

    # 2) Сразу шлём новый предпросмотр БЕЗ фото и ниже — меню
    await render_preview_and_menu(call.message, data)

    # 3) Возвращаемся в состояние ожидания текста (общий режим)
    await state.set_state(AdminBroadcast.waiting_for_text)
    print("[remove_photo] состояние -> waiting_for_text")



# ==== Helper: предпросмотр + меню (без фото) ====
async def render_preview_and_menu(message: Message, data: dict):
    print(f"[render_preview_and_menu] data={data}")
    text = (data.get("broadcast_text") or "").strip()
    buttons = data.get("buttons", [])
    final_kb = build_final_keyboard(buttons)
    menu_kb = build_broadcast_menu(data)

    # Предпросмотр без фото
    await message.answer(f"📢 Предпросмотр:\n\n{text}", reply_markup=final_kb)
    print("[render_preview_and_menu] отправлен предпросмотр (без фото)")

    # Меню управления рассылкой
    await message.answer("⚙️ Меню рассылки:", reply_markup=menu_kb)
    print("[render_preview_and_menu] отправлено меню рассылки")



# ============================ Конструктор кнопок ============================

@router.callback_query(F.data == "setup_buttons")
async def setup_buttons(call: CallbackQuery, state: FSMContext):
    print(f"[setup_buttons] от {call.from_user.id}")
    await call.answer()
    data = await state.get_data()
    print(f"[setup_buttons] state={data}")
    buttons = data.get("buttons", [])
    kb = build_buttons_preview_kb(buttons)
    # Пишем заголовок отдельно, а потом — сообщение с клавиатурой
    await safe_edit_or_send(call, "⚙️ Конструктор кнопок\nТекущие кнопки ниже. Добавьте, удалите или завершите.")
    await call.message.answer("📋 Текущие кнопки:", reply_markup=kb)


@router.callback_query(F.data == "add_button")
async def add_button(call: CallbackQuery, state: FSMContext):
    print(f"[add_button] от {call.from_user.id}")
    await call.answer()
    await state.set_state(AdminBroadcast.waiting_for_button_text)
    await call.message.answer("✏️ Введите текст кнопки:")


@router.message(AdminBroadcast.waiting_for_button_text)
async def button_text(message: Message, state: FSMContext):
    print(f"[button_text] text='{message.text}'")
    await state.update_data(current_button_text=message.text)
    await state.set_state(AdminBroadcast.waiting_for_button_url)
    await message.answer("🔗 Введите ссылку кнопки (http:// или https://):")


@router.message(AdminBroadcast.waiting_for_button_url)
async def button_url(message: Message, state: FSMContext):
    url = (message.text or "").strip()
    print(f"[button_url] url='{url}'")
    if not (url.startswith("http://") or url.startswith("https://")):
        await message.answer("❌ Неверный URL. Укажите ссылку, начиная с http:// или https://")
        return

    data = await state.get_data()
    btn_text = (data.get("current_button_text") or "").strip()
    if not btn_text:
        print("[button_url] пустой текст кнопки — сбрасываю в waiting_for_text")
        await state.set_state(AdminBroadcast.waiting_for_text)
        await state.update_data(current_button_text=None)
        await message.answer("❌ Текст кнопки пуст. Нажмите «Добавить» и начните заново.")
        return

    buttons = data.get("buttons", [])
    buttons.append({"text": btn_text, "url": url})
    await state.update_data(buttons=buttons, current_button_text=None)
    print(f"[button_url] добавлено: '{btn_text}' -> '{url}', итог кнопок={len(buttons)}")

    kb = build_buttons_preview_kb(buttons)
    await message.answer("✅ Кнопка добавлена. Текущие кнопки:", reply_markup=kb)
    await state.set_state(AdminBroadcast.waiting_for_text)


@router.callback_query(F.data == "remove_button_prompt")
async def remove_button_prompt(call: CallbackQuery, state: FSMContext):
    print(f"[remove_button_prompt] от {call.from_user.id}")
    await call.answer()
    data = await state.get_data()
    buttons = data.get("buttons", [])
    print(f"[remove_button_prompt] всего кнопок={len(buttons)}")
    if not buttons:
        await call.message.answer("Список кнопок пуст.")
        return

    rows = []
    for idx, btn in enumerate(buttons):
        rows.append([InlineKeyboardButton(text=f"🗑 Удалить {idx+1}. {btn.get('text','')}", callback_data=f"remove_button_{idx}")])
    rows.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="setup_buttons")])

    await call.message.answer("Выберите кнопку для удаления:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("remove_button_"))
async def remove_button(call: CallbackQuery, state: FSMContext):
    print(f"[remove_button] data='{call.data}'")
    await call.answer()
    idx_str = call.data.replace("remove_button_", "")
    try:
        idx = int(idx_str)
    except ValueError:
        await call.answer("Некорректный выбор")
        return

    data = await state.get_data()
    buttons = data.get("buttons", [])
    if 0 <= idx < len(buttons):
        removed = buttons.pop(idx)
        await state.update_data(buttons=buttons)
        await call.message.answer(f"🗑 Удалено: {removed.get('text')}")
        print(f"[remove_button] удалено индекс={idx}, осталось={len(buttons)}")
    else:
        await call.answer("Некорректный индекс")
        print("[remove_button] вне диапазона")
        return

    kb = build_buttons_preview_kb(buttons)
    await call.message.answer("Текущие кнопки:", reply_markup=kb)


@router.callback_query(F.data == "buttons_done")
async def buttons_done(call: CallbackQuery, state: FSMContext):
    print(f"[buttons_done] от {call.from_user.id}")
    await call.answer()
    data = await state.get_data()
    text = data.get("broadcast_text", "") or ""
    photo_id = data.get("broadcast_photo")
    final_kb = build_final_keyboard(data.get("buttons", []))
    menu_kb = build_broadcast_menu(data)

    # Предпросмотр для админа (как увидят пользователи)
    if photo_id:
        await call.message.answer_photo(photo_id, caption=f"📢 Предпросмотр:\n\n{text}", reply_markup=final_kb)
        print("[buttons_done] отправлен предпросмотр с фото")
    else:
        await call.message.answer(f"📢 Предпросмотр:\n\n{text}", reply_markup=final_kb)
        print("[buttons_done] отправлен предпросмотр без фото")

    # Панель управления после предпросмотра
    await call.message.answer("⚙️ Что делаем дальше?", reply_markup=menu_kb)
    print("[buttons_done] меню после предпросмотра отправлено")
    await state.set_state(AdminBroadcast.waiting_for_text)


# ============================ Отправка сейчас ============================

@router.callback_query(F.data == "send_broadcast_now")
async def send_now(call: CallbackQuery, state: FSMContext):
    print(f"[send_now] от {call.from_user.id}")
    await call.answer()

    # 1️⃣ Сначала достаём данные
    data = await state.get_data()
    text = data.get("broadcast_text")
    if not text:
        await call.message.answer("Добавьте текст рассылки.")
        return

    photo_id = data.get("broadcast_photo")
    buttons = data.get("buttons", [])
    markup = build_final_keyboard(buttons)

    # 2️⃣ Теперь можно сбросить состояние, чтобы не ловить лишние сообщения
    await state.clear()

    # 3️⃣ Сообщаем, что идёт отправка
    status = f"📤 Отправка рассылки ({'с фото' if photo_id else 'текст'})..."
    await safe_edit_or_send(call, status)

    # 4️⃣ Отправляем рассылку
    try:
        res = await send_broadcast_to_all_users(text, photo_id, call.from_user.id)
    except Exception as e:
        log_exc("[send_now] ошибка отправки", e)
        res = None

    # 5️⃣ Разбираем результат
    if isinstance(res, tuple) and len(res) >= 2:
        success, errors = res[0], res[1]
    elif isinstance(res, int):
        success, errors = res, 0
    else:
        success, errors = 0, 0

    delivered = (success or 0) + (errors or 0)
    pct = round((success / delivered) * 100, 1) if delivered > 0 else 0.0

    result_text = (
        "✅ Рассылка завершена!\n"
        f"✅ Успешно: {success}\n"
        f"❌ Ошибок: {errors}\n"
        f"📊 Доставка: {pct}%\n"
        f"🔘 Кнопок: {len(buttons)}\n"
        f"🖼 Фото: {'да' if photo_id else 'нет'}"
    )

    # 6️⃣ Показываем меню после рассылки
    menu_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Новая рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_back")]
    ])
    await call.message.answer(result_text, reply_markup=menu_kb)




# ============================ Планирование ============================

@router.callback_query(F.data == "schedule_broadcast")
async def schedule_broadcast(call: CallbackQuery, state: FSMContext):
    print(f"[schedule_broadcast] от {call.from_user.id}")
    await call.answer()
    await state.set_state(AdminBroadcast.waiting_for_schedule_time)
    text = (
        "⏰ Планирование рассылки\n\n"
        "Введите дату и время отправки в формате:\n"
        "YYYY-MM-DD HH:MM\n\n"
        "Например: 2025-01-15 14:30"
    )
    try:
        await safe_edit_or_send(call, text)
    except Exception as e:
        log_exc("[schedule_broadcast] prompt failed", e)
        await call.message.answer(text)


@router.message(AdminBroadcast.waiting_for_schedule_time)
async def set_schedule_time(message: Message, state: FSMContext):
    raw = (message.text or "").strip()
    print(f"[set_schedule_time] raw='{raw}'")
    try:
        schedule_time = datetime.strptime(raw, "%Y-%m-%d %H:%M")
        if schedule_time <= datetime.now():
            await message.answer("❌ Время должно быть в будущем.")
            return
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте: YYYY-MM-DD HH:MM")
        return

    data = await state.get_data()
    text = data.get("broadcast_text")
    if not text:
        print("[set_schedule_time] нет текста рассылки")
        await message.answer("Сначала добавьте текст рассылки.")
        await state.clear()
        return

    photo_id = data.get("broadcast_photo")
    buttons = data.get("buttons", [])
    final_kb = build_final_keyboard(buttons)

    try:
        users = await get_all_users()
        if not users:
            await message.answer("❌ Нет пользователей для рассылки.")
            await state.clear()
            return

        # Сохраняем задачи в БД (персонально)
        saved_count = 0
        for u in users:
            try:
                await save_scheduled_message(
                    u["user_id"],
                    text,
                    photo_id,
                    schedule_time.strftime("%Y-%m-%d %H:%M")
                )
                saved_count += 1
            except Exception as e:
                log_exc(f"[set_schedule_time] save_scheduled_message user_id={u.get('user_id')}", e)

        print(f"[set_schedule_time] сохранено задач: {saved_count}, run_date={schedule_time}")

        # Регистрируем job в планировщике, если доступен
        job_id = f"broadcast_{int(datetime.now().timestamp())}"
        if scheduler and getattr(scheduler, "scheduler", None):
            try:
                print("[set_schedule_time] добавляем job с клавиатурой (если поддерживается)")
                scheduler.scheduler.add_job(
                    send_scheduled_broadcast_with_stats,
                    "date",
                    run_date=schedule_time,
                    id=job_id,
                    args=[text, photo_id, message.from_user.id, final_kb]
                )
            except TypeError as e:
                log_exc("[set_schedule_time] add_job TypeError (без клавиатуры)", e)
                scheduler.scheduler.add_job(
                    send_scheduled_broadcast_with_stats,
                    "date",
                    run_date=schedule_time,
                    id=job_id,
                    args=[text, photo_id, message.from_user.id]
                )
            except Exception as e:
                log_exc("[set_schedule_time] add_job error", e)
        else:
            print("[set_schedule_time] ⚠️ Планировщик недоступен — используйте внешний обработчик отложенных сообщений.")

        confirm = (
            f"✅ Рассылка запланирована на {schedule_time.strftime('%d.%m.%Y %H:%M')}\n"
            f"👥 Получателей: {saved_count}\n"
            f"🖼 Фото: {'да' if photo_id else 'нет'}\n"
            f"🔘 Кнопок: {len(buttons)}"
        )
        await message.answer(confirm, reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_back")]
        ]))
        print("[set_schedule_time] подтверждение отправлено")
        await state.clear()
        print("[set_schedule_time] state очищен")
    except Exception as e:
        log_exc("[set_schedule_time] общая ошибка", e)
        await message.answer("❌ Ошибка при планировании рассылки")
        await state.clear()
        print("[set_schedule_time] state очищен после ошибки")
