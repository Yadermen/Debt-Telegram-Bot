import re
from urllib.parse import urlparse

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime
import asyncio
import os
import traceback

from sqlalchemy import select

from app.database import (
    get_all_users,
    get_user_count,
    get_active_debts_count,
    save_scheduled_message, get_db,
)
from app.database.crud import get_referrals, create_referral, deactivate_referral, get_referral_stats, \
    get_referral_by_id, activate_referral
from app.database.models import Referral
from app.keyboards import CallbackData
from app.states import AdminBroadcast, AdminReferral
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

def kb_admin_referrals() -> InlineKeyboardMarkup:
    """Главное меню рефералок"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список", callback_data="referrals_list")],
        [InlineKeyboardButton(text="➕ Создать", callback_data="referral_create")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="referrals_stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
    ])

def kb_cancel_photo():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_photo")]
    ])

def kb_back_to_referrals() -> InlineKeyboardMarkup:
    """Кнопка назад в меню рефералок"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_referrals")]
    ])

def kb_admin_main() -> InlineKeyboardMarkup:
    """Главное меню админки"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🎯 Реферальные ссылки", callback_data="admin_referrals")],
        [InlineKeyboardButton(text="🌐 Веб‑админка", url="http://79.133.183.213:5000/admin")],
        [InlineKeyboardButton(text="🏠Главное меню", callback_data=CallbackData.BACK_MAIN)],
    ])
def kb_back_to_admin() -> InlineKeyboardMarkup:
    """Кнопка возврата в главное меню админки"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 В админ‑панель", callback_data="admin_back")]
    ])
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

def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc and "." in result.netloc])
    except:
        return False

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
    user_id = message.from_user.id

    if message.chat.type == "private":
        # пробуем удалить команду /admin
        try:
            await message.delete()
        except Exception as e:
            print(f"Ошибка при удалении /admin: {e}")

        # пробуем удалить предыдущее сообщение (обычно это меню)
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=message.message_id - 1)
        except Exception as e:
            print(f"Ошибка при удалении предыдущего сообщения: {e}")
    print(f"[admin_panel] /admin от {message.from_user.id}")
    await state.clear()
    if not is_admin(message.from_user.id):
        return await message.answer("Нет доступа")
    user_count, active_debts = await get_admin_stats_safely()

    await message.answer(f"📊 Пользователей: {user_count}\n📄 Активных долгов: {active_debts}", reply_markup=kb_admin_main())


@router.callback_query(F.data == "admin_back")
async def admin_back(call: CallbackQuery, state: FSMContext):
    print(f"[admin_back] от {call.from_user.id}")
    await call.answer()

    if not is_admin(call.from_user.id):
        return

    await state.clear()
    user_count, active_debts = await get_admin_stats_safely()


    text = f"📊 Пользователей: {user_count}\n📄 Активных долгов: {active_debts}"

    # Безопасно: если текущее сообщение текстовое — редактируем, иначе шлём новое
    try:
        if call.message.text:
            await call.message.edit_text(text, reply_markup=kb_admin_main())
        else:
            await call.message.answer(text, reply_markup=kb_admin_main())
    except Exception as e:
        print(f"[admin_back] edit_text error: {e}")
        await call.message.answer(text, reply_markup=kb_admin_main())



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


@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(call: CallbackQuery, state: FSMContext):
    print(f"[start_broadcast] от {call.from_user.id}")
    await call.answer()
    await state.set_state(AdminBroadcast.waiting_for_text)
    await state.update_data(broadcast_text=None, broadcast_photo=None, buttons=[])

    msg = await safe_edit_or_send(call, "📢 Введите текст рассылки:")
    # сохраняем id подсказки
    await state.update_data(last_bot_msg=msg.message_id)



@router.message(AdminBroadcast.waiting_for_text)
async def set_broadcast_text(message: Message, state: FSMContext):
    text = (message.text or "").strip()

    try: await message.delete()
    except: pass

    data = await state.get_data()

    # удаляем старый предпросмотр
    if preview_id := data.get("preview_msg_id"):
        try:
            await message.bot.delete_message(message.chat.id, preview_id)
        except: pass

    # удаляем старую подсказку
    if last_bot := data.get("last_bot_msg"):
        try:
            await message.bot.delete_message(message.chat.id, last_bot)
        except: pass

    if not text or len(text) < 5:
        msg = await message.answer("❌ Текст слишком короткий, введите минимум 5 символов")
        await state.update_data(last_bot_msg=msg.message_id)
        return

    await state.update_data(broadcast_text=text)

    # новый предпросмотр
    kb = build_final_keyboard(data.get("buttons", []))
    preview = await message.answer(f"📢 Предпросмотр:\n\n{text}", reply_markup=kb)
    await state.update_data(preview_msg_id=preview.message_id)

    # меню
    menu_kb = build_broadcast_menu(await state.get_data())
    menu_msg = await message.answer("⚙️ Меню рассылки:", reply_markup=menu_kb)
    await state.update_data(last_bot_msg=menu_msg.message_id)



# ============================ Фото ============================

@router.callback_query(F.data == "add_broadcast_photo")
async def add_photo(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(AdminBroadcast.waiting_for_photo)

    # удаляем старое сообщение
    try:
        await call.message.delete()
    except: pass

    # подсказка с кнопкой отмены
    msg = await call.message.answer("📷 Отправьте фото для рассылки:", reply_markup=kb_cancel_photo())
    await state.update_data(last_bot_msg=msg.message_id)


@router.message(AdminBroadcast.waiting_for_photo, F.photo)
async def set_photo(message: Message, state: FSMContext):
    try: await message.delete()
    except: pass

    data = await state.get_data()

    # удаляем старый предпросмотр и меню
    if preview_id := data.get("preview_msg_id"):
        try: await message.bot.delete_message(message.chat.id, preview_id)
        except: pass
    if last_bot := data.get("last_bot_msg"):
        try: await message.bot.delete_message(message.chat.id, last_bot)
        except: pass

    # сохраняем фото
    photo_id = message.photo[-1].file_id
    await state.update_data(broadcast_photo=photo_id)

    # новый предпросмотр
    final_kb = build_final_keyboard(data.get("buttons", []))
    preview = await message.answer_photo(photo_id, caption=f"📢 Предпросмотр:\n\n{data.get('broadcast_text') or ''}", reply_markup=final_kb)
    await state.update_data(preview_msg_id=preview.message_id)

    # новое меню
    menu_kb = build_broadcast_menu(await state.get_data())
    menu_msg = await message.answer("⚙️ Меню рассылки:", reply_markup=menu_kb)
    await state.update_data(last_bot_msg=menu_msg.message_id)

    await state.set_state(AdminBroadcast.waiting_for_text)




@router.message(AdminBroadcast.waiting_for_photo, F.text)
async def wrong_input_photo(message: Message, state: FSMContext):
    # удаляем сообщение пользователя
    try: await message.delete()
    except: pass

    data = await state.get_data()
    # удаляем старую подсказку
    if last_bot := data.get("last_bot_msg"):
        try: await message.bot.delete_message(message.chat.id, last_bot)
        except: pass

    # показываем ошибку с кнопкой отмены
    msg = await message.answer("❌ Пожалуйста, отправьте фото", reply_markup=kb_cancel_photo())
    await state.update_data(last_bot_msg=msg.message_id)


@router.callback_query(F.data == "cancel_photo")
async def cancel_photo(call: CallbackQuery, state: FSMContext):
    await call.answer()

    # удаляем подсказку/ошибку
    try: await call.message.delete()
    except: pass

    # возвращаем меню рассылки
    data = await state.get_data()
    menu_kb = build_broadcast_menu(data)
    msg = await call.message.answer("⚙️ Меню рассылки:", reply_markup=menu_kb)
    await state.update_data(last_bot_msg=msg.message_id)

    await state.set_state(AdminBroadcast.waiting_for_text)

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
    data = await state.get_data()
    await render_preview_and_menu(call.message, state, data)

    # 3) Возвращаемся в состояние ожидания текста (общий режим)
    await state.set_state(AdminBroadcast.waiting_for_text)
    print("[remove_photo] состояние -> waiting_for_text")



# ==== Helper: предпросмотр + меню (без фото) ====
async def render_preview_and_menu(message: Message, state: FSMContext, data: dict):
    print(f"[render_preview_and_menu] data={data}")
    text = (data.get("broadcast_text") or "").strip()
    buttons = data.get("buttons", [])
    final_kb = build_final_keyboard(buttons)
    menu_kb = build_broadcast_menu(data)

    # удаляем старый предпросмотр, если был
    if preview_id := data.get("preview_msg_id"):
        try:
            await message.bot.delete_message(message.chat.id, preview_id)
        except: pass

    # удаляем старое меню, если было
    if last_bot := data.get("last_bot_msg"):
        try:
            await message.bot.delete_message(message.chat.id, last_bot)
        except: pass

    # новый предпросмотр
    preview = await message.answer(f"📢 Предпросмотр:\n\n{text}", reply_markup=final_kb)
    await state.update_data(preview_msg_id=preview.message_id)
    print("[render_preview_and_menu] отправлен предпросмотр (без фото)")

    # новое меню
    menu_msg = await message.answer("⚙️ Меню рассылки:", reply_markup=menu_kb)
    await state.update_data(last_bot_msg=menu_msg.message_id)
    print("[render_preview_and_menu] отправлено меню рассылки")




# ============================ Конструктор кнопок ============================

@router.callback_query(F.data == "setup_buttons")
async def setup_buttons(call: CallbackQuery, state: FSMContext):
    await call.answer()

    # ❌ удаляем старое сообщение
    try:
        await call.message.delete()
    except Exception as e:
        print(f"Ошибка при удалении: {e}")

    # ✅ отправляем новое
    data = await state.get_data()
    buttons = data.get("buttons", [])
    kb = build_buttons_preview_kb(buttons)


    await call.message.answer("📋 Текущие кнопки:", reply_markup=kb)



@router.callback_query(F.data == "add_button")
async def add_button(call: CallbackQuery, state: FSMContext):
    await call.answer()

    # удаляем прошлое сообщение бота (то, на которое нажали)
    try:
        await call.message.delete()
    except Exception as e:
        print(f"Ошибка при удалении сообщения: {e}")

    # переводим FSM в ожидание текста кнопки
    await state.set_state(AdminBroadcast.waiting_for_button_text)

    # отправляем новое сообщение‑подсказку
    msg = await call.message.answer("✏️ Введите текст кнопки:")
    await state.update_data(last_bot_msg=msg.message_id)

@router.message(AdminBroadcast.waiting_for_button_text)
async def button_text(message: Message, state: FSMContext):
    user_input = (message.text or "").strip()

    try: await message.delete()
    except: pass

    data = await state.get_data()
    if last_bot := data.get("last_bot_msg"):
        try: await message.bot.delete_message(message.chat.id, last_bot)
        except: pass

    if not user_input:
        msg = await message.answer("❌ Текст кнопки не может быть пустым")
        await state.update_data(last_bot_msg=msg.message_id)
        return

    await state.update_data(current_button_text=user_input)
    await state.set_state(AdminBroadcast.waiting_for_button_url)
    msg = await message.answer("🔗 Введите ссылку кнопки (http:// или https://):")
    await state.update_data(last_bot_msg=msg.message_id)


@router.message(AdminBroadcast.waiting_for_button_url)
async def button_url(message: Message, state: FSMContext):
    url = (message.text or "").strip()

    try: await message.delete()
    except: pass

    data = await state.get_data()
    if last_bot := data.get("last_bot_msg"):
        try: await message.bot.delete_message(message.chat.id, last_bot)
        except: pass

    if not is_valid_url(url):
        msg = await message.answer("❌ Неверный URL. Укажите корректную ссылку (http/https).")
        await state.update_data(last_bot_msg=msg.message_id)
        return

    data = await state.get_data()
    btn_text = (data.get("current_button_text") or "").strip()
    if not btn_text:
        await state.set_state(AdminBroadcast.waiting_for_text)
        await state.update_data(current_button_text=None)
        msg = await message.answer("❌ Текст кнопки пуст. Нажмите «Добавить» и начните заново.")
        await state.update_data(last_bot_msg=msg.message_id)
        return

    buttons = data.get("buttons", [])
    buttons.append({"text": btn_text, "url": url})
    await state.update_data(buttons=buttons, current_button_text=None)

    kb = build_buttons_preview_kb(buttons)
    msg = await message.answer("✅ Кнопка добавлена. Текущие кнопки:", reply_markup=kb)
    await state.update_data(last_bot_msg=msg.message_id)
    await state.set_state(AdminBroadcast.waiting_for_text)


@router.callback_query(F.data == "remove_button_prompt")
async def remove_button_prompt(call: CallbackQuery, state: FSMContext):
    print(f"[remove_button_prompt] от {call.from_user.id}")
    await call.answer()
    try:
        await call.message.delete()
    except Exception as e:
        print(f"Ошибка при удалении сообщения: {e}")
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
    try:
        await call.message.delete()
    except Exception as e:
        print(f"Ошибка при удалении сообщения: {e}")
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

    # удаляем сообщение, на которое нажали
    try:
        await call.message.delete()
    except Exception as e:
        print(f"Ошибка при удалении сообщения: {e}")

    data = await state.get_data()
    text = data.get("broadcast_text", "") or ""
    photo_id = data.get("broadcast_photo")
    final_kb = build_final_keyboard(data.get("buttons", []))
    menu_kb = build_broadcast_menu(data)

    # удаляем старый предпросмотр, если был
    if preview_id := data.get("preview_msg_id"):
        try:
            await call.bot.delete_message(call.message.chat.id, preview_id)
        except: pass

    # удаляем старое меню, если было
    if last_bot := data.get("last_bot_msg"):
        try:
            await call.bot.delete_message(call.message.chat.id, last_bot)
        except: pass

    # новый предпросмотр
    if photo_id:
        preview = await call.message.answer_photo(photo_id, caption=f"📢 Предпросмотр:\n\n{text}", reply_markup=final_kb)
        print("[buttons_done] отправлен предпросмотр с фото")
    else:
        preview = await call.message.answer(f"📢 Предпросмотр:\n\n{text}", reply_markup=final_kb)
        print("[buttons_done] отправлен предпросмотр без фото")
    await state.update_data(preview_msg_id=preview.message_id)

    # новое меню
    menu_msg = await call.message.answer("⚙️ Что делаем дальше?", reply_markup=menu_kb)
    await state.update_data(last_bot_msg=menu_msg.message_id)
    print("[buttons_done] меню после предпросмотра отправлено")

    await state.set_state(AdminBroadcast.waiting_for_text)



# ============================ Отправка сейчас ============================

@router.callback_query(F.data == "send_broadcast_now")
async def send_now(call: CallbackQuery, state: FSMContext):
    await call.answer()

    # 1️⃣ Достаём данные
    data = await state.get_data()
    text = data.get("broadcast_text")
    if not text:
        await call.message.answer("Добавьте текст рассылки.")
        return

    photo_id = data.get("broadcast_photo")
    buttons = data.get("buttons", [])
    markup = build_final_keyboard(buttons)

    # 2️⃣ Удаляем предпросмотр и меню, если они были
    if preview_id := data.get("preview_msg_id"):
        try:
            await call.bot.delete_message(call.message.chat.id, preview_id)
        except: pass
    if last_bot := data.get("last_bot_msg"):
        try:
            await call.bot.delete_message(call.message.chat.id, last_bot)
        except: pass

    # 3️⃣ Сбрасываем состояние
    await state.clear()

    # 4️⃣ Показываем статус (временное сообщение)


    # 5️⃣ Отправляем рассылку
    try:
        res = await send_broadcast_to_all_users(text, photo_id, call.from_user.id)
    except Exception as e:
        log_exc("[send_now] ошибка отправки", e)
        res = None

    # 6️⃣ Разбираем результат
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

    # 7️⃣ Удаляем статусное сообщение

    # 8️⃣ Отправляем результат отдельным сообщением
    menu_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Новая рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔙 В админ-панель", callback_data="admin_back")]
    ])
    await call.message.answer(result_text, reply_markup=menu_kb)


# ============================ Создание рассылки: текст ============================

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
    await call.message.answer("Выбериfте действие:", reply_markup=kb_back_to_referrals())




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
        msg = await safe_edit_or_send(call, text)
    except Exception as e:
        log_exc("[schedule_broadcast] prompt failed", e)
        msg = await call.message.answer(text)

    # сохраняем id подсказки бота, чтобы потом удалить
    await state.update_data(last_bot_msg=msg.message_id)



@router.message(AdminBroadcast.waiting_for_schedule_time)
async def set_schedule_time(message: Message, state: FSMContext):
    raw = (message.text or "").strip()

    try:
        await message.delete()
    except:
        pass

    data = await state.get_data()
    if last_bot := data.get("last_bot_msg"):
        try:
            await message.bot.delete_message(message.chat.id, last_bot)
        except:
            pass
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
                    args=[text, photo_id, message.from_user.id]
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


@router.callback_query(F.data == "admin_referrals")
async def admin_referrals(call: CallbackQuery, state: FSMContext):
    print(f"[admin_referrals] от {call.from_user.id}")
    await call.answer()
    if not is_admin(call.from_user.id):
        return

    # Удаляем сообщение, по которому кликнули
    try:
        await call.message.delete()
    except Exception as e:
        print(f"[admin_referrals] ошибка при удалении сообщения: {e}")


    await call.message.answer("🎯 Управление реферальными ссылками", reply_markup=kb_admin_referrals())


@router.callback_query(F.data == "referrals_list")
async def referrals_list(call: CallbackQuery):
    await call.answer()
    referrals = await get_referrals(active_only=False)
    if not referrals:
        return await call.message.edit_text(
            "❌ Рефералок нет",
            reply_markup=kb_back_to_referrals()
        )

    # Формируем список кнопок
    rows = []
    for r in referrals:
        rows.append([
            InlineKeyboardButton(
                text=f"{'✅' if r['is_active'] else '❌'} {r['code']}",
                callback_data=f"referral_view_{r['id']}"
            )
        ])
    # Добавляем кнопку "Назад"
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_referrals")])

    await call.message.edit_text(
        "📋 Выберите рефералку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )



@router.callback_query(F.data == "referral_create")
async def referral_create(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(AdminReferral.waiting_for_code)
    msg = await safe_edit_or_send(call, "✏️ Введите код для новой рефералки (например: promo2025)")
    await state.update_data(last_bot_msg=msg.message_id)



@router.message(AdminReferral.waiting_for_code)
async def referral_set_code(message: Message, state: FSMContext):
    raw_code = (message.text or "").strip()

    try:
        await message.delete()
    except:
        pass

    data = await state.get_data()
    if last_bot := data.get("last_bot_msg"):
        try:
            await message.bot.delete_message(message.chat.id, last_bot)
        except:
            pass

    # 🔎 Валидация
    if not raw_code:
        msg = await message.answer("❌ Код не может быть пустым. Введите снова:")
        await state.update_data(last_bot_msg=msg.message_id)
        return

    # Разрешаем только буквы, цифры, подчёркивание и дефис
    if not re.fullmatch(r"[A-Za-z0-9_-]+", raw_code):
        msg = await message.answer("❌ Код может содержать только латинские буквы, цифры, '_' и '-'. Введите снова:")
        await state.update_data(last_bot_msg=msg.message_id)
        return

    # Ограничение по длине
    if len(raw_code) < 3 or len(raw_code) > 50:
        msg = await message.answer("❌ Длина кода должна быть от 3 до 50 символов. Введите снова:")
        await state.update_data(last_bot_msg=msg.message_id)
        return

    # Проверка уникальности
    async with get_db() as session:
        exists = await session.scalar(select(Referral).where(Referral.code == raw_code))
    if exists:
        msg = await message.answer("❌ Такая рефералка уже существует. Введите другой код:")
        await state.update_data(last_bot_msg=msg.message_id)
        return

    # ✅ Всё ок — сохраняем в state
    await state.update_data(referral_code=raw_code)
    await state.set_state(AdminReferral.waiting_for_description)
    msg = await message.answer("📝 Введите описание (или '-' чтобы оставить пустым):")
    await state.update_data(last_bot_msg=msg.message_id)



@router.message(AdminReferral.waiting_for_description)
async def referral_set_description(message: Message, state: FSMContext):
    desc = (message.text or "").strip()

    try: await message.delete()
    except: pass

    data = await state.get_data()
    if last_bot := data.get("last_bot_msg"):
        try: await message.bot.delete_message(message.chat.id, last_bot)
        except: pass

    if desc == "-":
        desc = None

    code = data.get("referral_code")

    try:
        referral = await create_referral(code, desc)
        if referral:
            await message.answer(
                f"✅ Рефералка создана!\n\n"
                f"Ссылка: https://t.me//QarzNazoratBot?start={referral['code']}\n"
                f"Код: {referral['code']}\n"
                f"Описание: {referral['description'] or '-'}\n"
                f"Статус: {'Активна' if referral['is_active'] else 'Неактивна'}",
                reply_markup=kb_back_to_referrals()
            )
        else:
            await message.answer("❌ Ошибка при создании рефералки", reply_markup=kb_back_to_referrals())
    except Exception as e:
        log_exc("[referral_set_description] ошибка создания", e)
        await message.answer("❌ Ошибка при сохранении рефералки", reply_markup=kb_back_to_referrals())

    await state.clear()



@router.callback_query(F.data == "referrals_list")
async def referrals_list(call: CallbackQuery):
    await call.answer()
    referrals = await get_referrals(active_only=False)
    if not referrals:
        return await call.message.edit_text(
            "❌ Рефералок нет",
            reply_markup=kb_back_to_referrals()
        )

    rows = []
    for r in referrals:
        # теперь каждая кнопка ведёт в карточку конкретной рефералки
        rows.append([
            InlineKeyboardButton(
                text=f"{'✅' if r['is_active'] else '❌'} {r['code']}",
                callback_data=f"referral_view:{r['id']}"
            )
        ])
    rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_referrals")])

    await call.message.edit_text(
        "📋 Выберите рефералку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )








@router.callback_query(F.data.startswith("referral_stats_"))
async def referral_stats(call: CallbackQuery):
    await call.answer()
    rid = int(call.data.replace("referral_stats_", ""))
    stats = await get_referral_stats(rid)
    if not stats:
        return await call.message.edit_text("❌ Нет статистики", reply_markup=kb_back_to_referrals())

    text = (
        f"📊 Статистика по рефералке\n\n"
        f"Пользователей: {stats['users_count']}\n"
        f"Активных: {stats['active_users']}\n"
        f"Последний: {stats['last_joined'] or '-'}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"referral_view_{rid}")]
    ])

    await call.message.edit_text(text, reply_markup=kb)





async def render_referral_view(call: CallbackQuery, rid: int):
    referral = await get_referral_by_id(rid)
    if not referral:
        return await call.message.edit_text("❌ Рефералка не найдена", reply_markup=kb_back_to_referrals())

    stats = await get_referral_stats(rid)

    text = (
        f"🎯 Рефералка\n\n"
        f"Ссылка: https://t.me//QarzNazoratBot?start={referral['code']}\n"
        f"Код: {referral['code']}\n"
        f"Описание: {referral['description'] or '-'}\n"
        f"Статус: {'✅ Активна' if referral['is_active'] else '❌ Неактивна'}\n"
        f"📊 Пользователей: {stats['users_count']}"
    )

    action_button = (
        InlineKeyboardButton(text="🗑 Деактивировать", callback_data=f"referral_deactivate_{rid}")
        if referral["is_active"]
        else InlineKeyboardButton(text="✅ Активировать", callback_data=f"referral_activate_{rid}")
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [action_button],
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="referrals_list")],
    ])

    await call.message.edit_text(text, reply_markup=kb)


# хендлер для открытия карточки
@router.callback_query(F.data.startswith("referral_view_"))
async def referral_view(call: CallbackQuery):
    rid = int(call.data.split("_")[2])
    await render_referral_view(call, rid)


# деактивация
@router.callback_query(F.data.startswith("referral_deactivate_"))
async def referral_deactivate(call: CallbackQuery):
    rid = int(call.data.split("_")[2])
    ok = await deactivate_referral(rid)
    await call.answer("✅ Деактивирована" if ok else "❌ Ошибка", show_alert=not ok)
    await render_referral_view(call, rid)


# активация
@router.callback_query(F.data.startswith("referral_activate_"))
async def referral_activate(call: CallbackQuery):
    rid = int(call.data.split("_")[2])
    ok = await activate_referral(rid)
    await call.answer("✅ Активирована" if ok else "❌ Ошибка", show_alert=not ok)
    await render_referral_view(call, rid)





@router.callback_query(F.data == "referrals_stats")
async def referrals_stats(call: CallbackQuery):
    await call.answer()
    referrals = await get_referrals(active_only=False)
    if not referrals:
        return await call.message.edit_text("❌ Рефералок нет", reply_markup=kb_back_to_referrals())

    text = "📊 Статистика по рефералкам:\n\n"
    for r in referrals[:10]:
        stats = await get_referral_stats(r["id"])
        text += f"Код: {r['code']} — Пользователей: {stats['users_count']}\n"
    if len(referrals) > 10:
        text += f"\n... и ещё {len(referrals)-10}"

    await call.message.edit_text(text, reply_markup=kb_back_to_referrals())


