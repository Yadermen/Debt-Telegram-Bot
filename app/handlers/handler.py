import asyncio
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from dotenv import load_dotenv
import aiosqlite
from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz


@dp.message(Command('start'))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT lang FROM users WHERE user_id = ?', (user_id,))
        user_row = await cursor.fetchone()
        if not user_row:
            # Новый пользователь — предлагаем выбрать язык, не создаём запись сразу
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=LANGS['ru']['lang_ru'], callback_data='setlang_ru')],
                [InlineKeyboardButton(text=LANGS['uz']['lang_uz'], callback_data='setlang_uz')],
            ])
            await message.answer(LANGS['ru']['choose_lang'], reply_markup=kb)
            return
    user_data = await get_user_data(user_id)
    await message.answer(await tr(user_id, 'welcome'), reply_markup=await main_menu(user_id))

# --- Обработчик смены языка ---
@dp.callback_query(lambda c: c.data.startswith('setlang_'))
async def set_language(call: CallbackQuery):
    lang = call.data.split('_')[1]
    user_id = call.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT lang FROM users WHERE user_id = ?', (user_id,))
        user_row = await cursor.fetchone()
        if not user_row:
            # Новый пользователь — создаём запись с выбранным языком
            await db.execute('INSERT INTO users (user_id, lang, notify_time) VALUES (?, ?, ?)', (user_id, lang, '09:00'))
            await db.commit()
        else:
            await save_user_lang(user_id, lang)
    await call.message.edit_text(LANGS[lang]['welcome'], reply_markup=await main_menu(user_id))
