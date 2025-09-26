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
from app.keyboards.callbacks import CallbackData
from app.keyboards.keyboards import main_menu
import re

router = Router()

DEESEEK_API_KEY = config.DEESEEK_API_KEY
DEESEEK_API_URL = config.DEESEEK_API_URL or "https://api.deepseek.com/v1/chat/completions"

# -----------------------------
# Pydantic schema для валидации JSON от ИИ
# -----------------------------

cancel_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="❌ Отмена", callback_data=CallbackData.BACK)]
])

exit_kb = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="⬅️ В меню", callback_data=CallbackData.BACK)]
])
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
        return datetime.fromisoformat(v.replace("Z","")).date().isoformat()


# -----------------------------
# Вызов DeepSeek
# -----------------------------
def extract_json(content: str) -> str:
    """Убираем ```json ... ``` обёртку, если модель её вернула"""
    cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", content.strip())
    cleaned = re.sub(r"```$", "", cleaned.strip())
    return cleaned.strip()

async def call_deepseek(user_text: str) -> dict | None:
    today = datetime.now().date().isoformat()

    system_prompt = (
        f"Ты помощник по финансовым записям. Возьми текст пользователя (на любом языке) и верни СТРОГО JSON с полями:\n"
        "- who_owes: me или i\n"
        "- counterparty_name: строка\n"
        "- amount: число больше 0\n"
        "- currency: одно из USD, EUR, UZS\n"
        "- due_date: в формате YYYY-MM-DD\n"
        "- description: строка\n\n"
        f"Сегодняшняя дата: {today}. "
        "Если пользователь пишет относительные даты (например: завтра, послезавтра, через неделю), "
        "всегда конвертируй их в абсолютную дату в формате YYYY-MM-DD относительно сегодняшней даты.\n\n"
        "Если данных недостаточно, ставь null, но всегда возвращай JSON. "
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
            print("🧹 После очистки:", cleaned)
            parsed = json.loads(cleaned)
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
        return datetime.fromisoformat(text.replace("Z","")).date().isoformat()
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
# Callback handler
# -----------------------------
@router.callback_query(F.data == CallbackData.AI_DEBT_ADD)
async def add_debt_ai_callback(call: CallbackQuery):
    print("📲 Нажата кнопка AI_DEBT_ADD")
    await call.answer()
    await call.message.answer(
        "Введите данные свободным текстом:\n"
        "- направление (‘я должен’ или ‘мне должны’)\n"
        "- контрагент (имя/название)\n"
        "- сумма и валюта (например: 250 USD)\n"
        "- срок (YYYY-MM-DD)\n"
        "- описание (необязательно)",
        reply_markup=cancel_kb
    )

@router.callback_query(F.data == CallbackData.BACK)
async def back_to_main(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.answer()
    markup = await main_menu(call.from_user.id)   # ✅ передаём user_id
    await call.message.answer(
        "🔙 Главное меню",
        reply_markup=markup
    )





# -----------------------------
# Message handler
# -----------------------------
@router.message()
async def ai_message_handler(m: Message):
    print("💬 Получено сообщение:", m.text)

    parsed = await call_deepseek(m.text)
    if not parsed:
        print("⚠️ Не удалось распознать данные")
        await m.answer("Не удалось распознать данные. Попробуйте сформулировать проще.", reply_markup=cancel_kb)
        return

    parsed = normalize_fields(parsed)

    try:
        debt = DebtAI(**parsed)
        print("✅ Валидация прошла:", debt)
    except ValidationError as e:
        print("❌ Ошибка валидации:", e.errors())
        errors = [f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors()]
        await m.answer(f"Не удалось распознать данные. Попробуйте написать проще: я должен Ивану 100 USD до YYYY-MM-DD ", reply_markup=cancel_kb )
        return

    # --- Формируем JSON под твою модель Debt ---
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
    print("📦 Готовый debt_json:", debt_json)

    # --- Сохраняем через CRUD ---
    new_debt = await crud.create_debt_from_ai(debt_json)
    print("💾 Результат сохранения:", new_debt)

    if new_debt:
        await m.answer(
            "✅ Долг записан:\n"
            f"- Контрагент: {new_debt['person']}\n"
            f"- Сумма: {new_debt['amount']} {new_debt['currency']}\n"
            f"- Срок: {new_debt['due']}\n"
            f"- Направление: {'мне должны' if new_debt['direction']=='owed' else 'я должен'}\n"
            f"- Комментарий: {new_debt['comment'] or '—'}",
            reply_markup=exit_kb
        )
    else:
        await m.answer("❌ Ошибка при сохранении долга", reply_markup=cancel_kb)
