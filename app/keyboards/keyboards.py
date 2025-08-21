@dp.startup()
async def on_startup(dispatcher):
    await init_db()
    if not scheduler.running:
        scheduler.start()
    await schedule_all_reminders()
    # Добавляем задачу проверки запланированных сообщений каждую минуту
    scheduler.add_job(check_scheduled_messages, 'interval', minutes=1, id='check_scheduled_messages')

# --- Обновлённая функция schedule_all_reminders ---
async def schedule_all_reminders():
    scheduler.remove_all_jobs()
    try:
        users = await get_all_users_with_notifications()
    except Exception:
        return
    for user_info in users:
        t = user_info.get('notify_time', None)
        if not t:
            continue
        try:
            hour, minute = map(int, t.split(':'))
        except Exception:
            continue
        # id задачи уникален для каждого пользователя
        job_id = f'notify_{user_info["user_id"]}'
        # Удаляем старую задачу, если есть
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass
        scheduler.add_job(send_due_reminders, 'cron', hour=hour, minute=minute, id=job_id, args=[user_info["user_id"]])

# --- Функция для обработки запланированных сообщений каждую минуту ---
async def check_scheduled_messages():
    """Проверять запланированные сообщения каждую минуту"""
    await process_scheduled_messages()

# --- Функция для обработки запланированных сообщений ---
async def process_scheduled_messages():
    """Обработать все запланированные сообщения"""
    messages = await get_pending_scheduled_messages()
    for message in messages:
        sent = await send_scheduled_message(message)
        if sent:
            await delete_scheduled_message(message['id'])
        await asyncio.sleep(0.1)  # Небольшая задержка между отправками

# --- Удаление сообщения из scheduled_messages ---
async def delete_scheduled_message(message_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM scheduled_messages WHERE id = ?', (message_id,))
        await db.commit()

# --- Главное меню (двухколоночная разметка) ---
async def main_menu(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await tr(user_id, 'add_debt'), callback_data='add_debt'),
         InlineKeyboardButton(text=await tr(user_id, 'my_debts'), callback_data='my_debts')],
        [InlineKeyboardButton(text=await tr(user_id, 'clear_all'), callback_data='clear_all'),
         InlineKeyboardButton(text=await tr(user_id, 'reminders_menu'), callback_data='reminders_menu')],
        [InlineKeyboardButton(text=await tr(user_id, 'how_to_use_btn'), callback_data='how_to_use')],
        [InlineKeyboardButton(text=await tr(user_id, 'change_lang'), callback_data='change_lang')]
    ])

# --- Выбор языка из меню ---
@dp.callback_query(lambda c: c.data == 'change_lang')
async def change_lang_menu(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=LANGS['ru']['lang_ru'], callback_data='setlang_ru')],
        [InlineKeyboardButton(text=LANGS['uz']['lang_uz'], callback_data='setlang_uz')],
        [InlineKeyboardButton(text=await tr(user_id, 'to_menu'), callback_data='back_main')],
    ])
    await call.message.edit_text(await tr(user_id, 'choose_lang'), reply_markup=kb)

# --- Обработчик /start ---

# --- Клавиатуры ---
async def currency_keyboard(user_id):
    # Валюты можно оставить как есть, если не требуется перевод
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='USD', callback_data='cur_usd')],
        [InlineKeyboardButton(text='UZS', callback_data='cur_uzs')],
        [InlineKeyboardButton(text='EUR', callback_data='cur_eur')],
    ])

async def direction_keyboard(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await tr(user_id, 'dir_gave'), callback_data='dir_gave')],
        [InlineKeyboardButton(text=await tr(user_id, 'dir_took'), callback_data='dir_took')],
    ])

async def skip_comment_keyboard(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await tr(user_id, 'skip_comment'), callback_data='skip_comment')],
    ])

async def menu_button(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=await tr(user_id, 'to_menu'), callback_data='back_main')],
    ])

async def currency_edit_keyboard(debt_id, user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='USD', callback_data=f'editcur_USD_{debt_id}')],
        [InlineKeyboardButton(text='UZS', callback_data=f'editcur_UZS_{debt_id}')],
        [InlineKeyboardButton(text='EUR', callback_data=f'editcur_EUR_{debt_id}')],
        [InlineKeyboardButton(text=await tr(user_id, 'to_menu'), callback_data='back_main')],