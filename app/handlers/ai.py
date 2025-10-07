import os
import json
from datetime import datetime, timezone, timedelta

import httpx
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from pydantic import BaseModel, Field, ValidationError, field_validator
from dateutil.parser import isoparse

from app import config
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from app.database import crud
from app.keyboards import tr
from app.keyboards.callbacks import CallbackData
from app.keyboards.keyboards import main_menu
import re
from aiogram.fsm.state import State, StatesGroup

router = Router()

DEESEEK_API_KEY = config.DEESEEK_API_KEY
DEESEEK_API_URL = config.DEESEEK_API_URL or "https://api.deepseek.com/v1/chat/completions"


# -----------------------------
# FSM
# -----------------------------
class DebtFSM(StatesGroup):
    waiting_for_input = State()


async def cancel_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=await tr(user_id, 'cancel_btn'),
                callback_data=CallbackData.BACK
            )]
        ]
    )


async def exit_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=await tr(user_id, 'to_menu'),
                callback_data=CallbackData.BACK
            )]
        ]
    )


# -----------------------------
# Pydantic schema
# -----------------------------
class DebtAI(BaseModel):
    who_owes: str = Field(..., description="me | i")
    counterparty_name: str
    amount: float
    currency: str
    due_date: str
    description: str | None = ""

    @field_validator("who_owes")
    def valid_who_owes(cls, v):
        if v not in {"me", "i"}:
            raise ValueError("who_owes must be 'me' or 'i'")
        return v

    @field_validator("counterparty_name")
    def non_empty_counterparty(cls, v):
        if not v or not v.strip():
            raise ValueError("counterparty_name required")
        return v.strip()

    @field_validator("amount")
    def positive_amount(cls, v):
        if v is None or v <= 0:
            raise ValueError("amount must be > 0")
        return v

    @field_validator("currency")
    def currency_in_list(cls, v):
        allowed = {"USD", "EUR", "UZS"}
        v2 = v.strip().upper()
        if v2 not in allowed:
            raise ValueError(f"currency must be one of {allowed}")
        return v2

    @field_validator("due_date")
    def iso_date(cls, v):
        try:
            isoparse(v)
        except Exception:
            raise ValueError("due_date must be ISO YYYY-MM-DD")
        return datetime.fromisoformat(v.replace("Z", "")).date().isoformat()


# -----------------------------
# DeepSeek call
# -----------------------------
def extract_json(content: str) -> str:
    """Убираем ```json ... ``` обёртку, если модель её вернула"""
    cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", content.strip())
    cleaned = re.sub(r"```$", "", cleaned.strip())
    return cleaned.strip()


async def call_deepseek(user_text: str) -> list[dict] | None:
    today = datetime.now().date().isoformat()

    system_prompt = (
        f"Ты помощник по финансовым записям. Возьми текст пользователя (на любом языке) "
        f"и верни СТРОГО JSON-МАССИВ (список) объектов, максимум 10 элементов. "
        f"Каждый объект должен содержать:\n"
        "- who_owes: me или i\n"
        "- counterparty_name: строка\n"
        "- amount: число больше 0\n"
        "- currency: одно из USD, EUR, UZS\n"
        "- due_date: в формате YYYY-MM-DD\n"
        "- description: строка\n\n"
        f"Сегодняшняя дата: {today}. "
        "Если пользователь пишет относительные даты (например: завтра, через неделю), "
        "всегда конвертируй их в абсолютную дату.\n\n"
        "Если данных недостаточно, ставь null, но всегда возвращай JSON-МАССИВ. "
        "Никаких комментариев, только JSON."
    )

    print("📤 Отправляю запрос в DeepSeek...")
    print("➡️ User text:", user_text)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            DEESEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEESEEK_API_KEY}",
                "HTTP-Referer": "https://yourdomain.com",
                "X-Title": "DebtBot"
            },
            json={
                "model": "deepseek/deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text}
                ],
                "temperature": 0.2
            }
        )
        print("📥 Ответ от API:", resp.status_code)
        resp.raise_for_status()
        data = resp.json()
        print("📦 JSON от API:", json.dumps(data, ensure_ascii=False, indent=2))

        content = data["choices"][0]["message"]["content"]
        print("📝 Контент от модели:", content)

        try:
            cleaned = extract_json(content)
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                parsed = [parsed]
            print("✅ Успешно распарсили JSON:", parsed)
            return parsed
        except Exception as e:
            print("❌ Ошибка парсинга JSON:", e)
            return None


# -----------------------------
# Helpers
# -----------------------------
def natural_to_date(text: str) -> str:
    try:
        isoparse(text)
        return datetime.fromisoformat(text.replace("Z", "")).date().isoformat()
    except Exception:
        return (datetime.now(timezone.utc) + timedelta(days=14)).date().isoformat()


def normalize_fields(parsed: dict) -> dict:
    print("🔧 Нормализация полей:", parsed)
    out = dict(parsed)
    if "currency" in out and out["currency"]:
        out["currency"] = str(out["currency"]).upper()
    if "due_date" in out and out["due_date"]:
        out["due_date"] = natural_to_date(str(out["due_date"]))
    print("✅ После нормализации:", out)
    return out


# -----------------------------
# Callback handlers
# -----------------------------
@router.callback_query(F.data == CallbackData.AI_DEBT_ADD)
async def add_debt_ai_callback(call: CallbackQuery, state: FSMContext):
    print("📲 Нажата кнопка AI_DEBT_ADD")
    await state.set_state(DebtFSM.waiting_for_input)
    await call.answer()
    await call.message.answer(
        await tr(call.from_user.id, 'ai_debt_input_hint'),
        reply_markup=await cancel_kb(call.from_user.id)
    )


@router.callback_query(F.data == CallbackData.BACK)
async def back_to_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer()
    markup = await main_menu(call.from_user.id)
    await call.message.answer(
        await tr(call.from_user.id, 'ai_main_menu'),
        reply_markup=markup
    )


# -----------------------------
# Message handler
# -----------------------------
@router.message(DebtFSM.waiting_for_input)
async def ai_message_handler(m: Message, state: FSMContext):
    print("💬 Получено сообщение:", m.text)

    parsed_list = await call_deepseek(m.text)
    if not parsed_list:
        await m.answer(
            await tr(m.from_user.id, 'ai_parse_failed'),
            reply_markup=await cancel_kb(m.from_user.id)
        )
        return

    all_debts_jsons = []
    failed = []

    for idx, parsed in enumerate(parsed_list[:10], start=1):
        parsed = normalize_fields(parsed)
        try:
            debt = DebtAI(**parsed)
        except ValidationError as e:
            print(f"❌ Ошибка валидации {idx}:", e.errors())
            failed.append((idx, e.errors()))
            continue

        debt_json = {
            "user_id": m.from_user.id,
            "person": debt.counterparty_name,
            "amount": int(debt.amount),
            "currency": debt.currency,
            "direction": "owed" if debt.who_owes == "me" else "owe",
            "date": datetime.utcnow().date().isoformat(),
            "due": debt.due_date,
            "comment": debt.description or ""
        }
        all_debts_jsons.append(debt_json)

    # --- Сохраняем все долги одним вызовом ---
    new_debts = await crud.create_debts_from_ai(all_debts_jsons)
    print("💾 Результат сохранения:", new_debts)

    # --- Выводим пользователю каждый долг отдельно ---
    if new_debts:
        total = len(new_debts)
        for idx, d in enumerate(new_debts, start=1):
            # если это последний долг — даём кнопку выхода
            reply_markup = await exit_kb(m.from_user.id) if idx == total else None

            await m.answer(
                await tr(
                    m.from_user.id,
                    'ai_debt_saved',
                    person=d['person'],
                    amount=d['amount'],
                    currency=d['currency'],
                    due=d['due'],
                    direction='мне должны' if d['direction'] == 'owed' else 'я должен',
                    comment=d['comment'] or '—'
                ),
                reply_markup=reply_markup
            )

    if failed:
        text = "⚠️ Не удалось сохранить некоторые долги:\n\n"
        for i, err in failed:
            details = "; ".join(
                [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in err]
            )
            text += f"{i}) Ошибка валидации: {details}\n"
        await m.answer(text, reply_markup=await cancel_kb(m.from_user.id))

    await state.clear()

