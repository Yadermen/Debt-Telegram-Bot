import asyncio

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, and_, func, delete
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from .models import *
from .connection import get_db


async def get_user_data(user_id: int) -> Dict[str, Any]:
    """Получить данные пользователя с его долгами"""
    async with get_db() as session:
        # Получаем или создаем пользователя
        user = await get_or_create_user(user_id, session)

        # Получаем активные долги пользователя
        result = await session.execute(
            select(Debt)
            .where(and_(Debt.user_id == user_id, Debt.is_active == True))
            .order_by(Debt.id)
        )
        debt_rows = result.scalars().all()

        # Преобразуем в словари
        debts = []
        for debt in debt_rows:
            debts.append({
                'id': debt.id,
                'person': debt.person,
                'amount': debt.amount,
                'currency': debt.currency,
                'direction': debt.direction,
                'date': debt.date,
                'due': debt.due,
                'comment': debt.comment,
                'closed': debt.closed
            })

        return {
            'lang': user.lang,
            'notify_time': user.notify_time,
            'debts': debts
        }


async def get_or_create_user(
        user_id: int,
        session: AsyncSession = None,
        default_lang: str = "ru"
) -> User:
    """Получить пользователя или создать если не существует"""
    if session is None:
        async with get_db() as session:
            return await get_or_create_user(user_id, session, default_lang=default_lang)

    # Ищем пользователя
    result = await session.execute(
        select(User).where(and_(User.user_id == user_id, User.is_active == True))
    )
    user = result.scalar_one_or_none()

    if not user:
        # Создаем нового пользователя
        user = User(user_id=user_id, lang=default_lang, notify_time='09:00')
        session.add(user)
        await session.flush()  # Чтобы получить ID
        await session.commit()  # ДОБАВЛЕН КОММИТ

    return user


async def get_due_debts_for_reminders(today_date: str):
    """
    Получить долги для напоминаний (просроченные или истекающие сегодня)

    Args:
        today_date: Текущая дата в формате 'YYYY-MM-DD'

    Returns:
        List[dict]: Список долгов с полями user_id, person, amount, currency, due, direction
    """
    try:
        async with get_db() as session:
            result = await session.execute(
                select(Debt)
                .where(and_(
                    Debt.closed == False,
                    Debt.is_active == True,
                    Debt.due <= today_date
                ))
                .order_by(Debt.due.asc(), Debt.user_id)
            )

            debt_rows = result.scalars().all()

            # Преобразуем в список словарей
            debts = []
            for debt in debt_rows:
                debts.append({
                    'user_id': debt.user_id,
                    'person': debt.person,
                    'amount': debt.amount,
                    'currency': debt.currency if debt.currency else 'UZS',
                    'due': debt.due,
                    'direction': debt.direction if debt.direction else 'owed',
                    'comment': debt.comment if debt.comment else ''
                })

            return debts

    except Exception as e:
        print(f"❌ Ошибка получения долгов для напоминаний: {e}")
        return []


async def save_user_lang(user_id: int, lang: str) -> None:
    """Сохранить язык пользователя"""
    async with get_db() as session:
        user = await get_or_create_user(user_id, session)
        user.lang = lang
        await session.commit()  # ДОБАВЛЕН КОММИТ


async def save_user_notify_time(user_id: int, notify_time: str) -> None:
    """Сохранить время уведомлений пользователя"""
    async with get_db() as session:
        user = await get_or_create_user(user_id, session)
        user.notify_time = notify_time
        await session.commit()  # ДОБАВЛЕН КОММИТ


async def get_user_by_id(user_id: int) -> Optional[User]:
    """Получить пользователя по ID"""
    async with get_db() as session:
        result = await session.execute(
            select(User).where(and_(User.user_id == user_id, User.is_active == True))
        )
        return result.scalar_one_or_none()


async def get_active_debts(user_id: int) -> List[Debt]:
    """Получить активные долги пользователя"""
    async with get_db() as session:
        result = await session.execute(
            select(Debt)
            .where(and_(
                Debt.user_id == user_id,
                Debt.is_active == True,
                Debt.closed == False
            ))
            .order_by(Debt.id)
        )
        return result.scalars().all()


async def soft_delete_debt(debt_id: int, user_id: int = None) -> bool:
    """Мягкое удаление долга (установка is_active = False)"""
    async with get_db() as session:
        query = update(Debt).where(Debt.id == debt_id)

        # Если указан user_id, добавляем проверку владельца
        if user_id is not None:
            query = query.where(Debt.user_id == user_id)

        result = await session.execute(query.values(is_active=False))
        await session.commit()  # ДОБАВЛЕН КОММИТ
        return result.rowcount > 0


async def soft_delete_user(user_id: int) -> bool:
    """Мягкое удаление пользователя (установка is_active = False)"""
    async with get_db() as session:
        result = await session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(is_active=False)
        )
        await session.commit()  # ДОБАВЛЕН КОММИТ
        return result.rowcount > 0


# === DEBT OPERATIONS ===

async def add_debt(user_id: int, debt: dict) -> int:
    """Добавить новый долг"""
    async with get_db() as session:
        try:
            # ИСПРАВЛЕНО: Сначала получаем или создаем пользователя
            user = await get_or_create_user(user_id, session)

            new_debt = Debt(
                user_id=user_id,
                person=debt['person'],
                amount=debt['amount'],
                currency=debt.get('currency', 'UZS'),
                direction=debt['direction'],
                date=debt['date'],
                due=debt['due'],
                comment=debt.get('comment', ''),
                closed=debt.get('closed', False)
            )
            session.add(new_debt)
            await session.flush()  # Чтобы получить ID
            await session.commit()  # ДОБАВЛЕН КОММИТ

            print(f"✅ Долг успешно сохранен с ID: {new_debt.id}")
            return new_debt.id
        except Exception as e:
            print(f"❌ Ошибка при сохранении долга: {e}")
            await session.rollback()
            raise


async def update_debt(debt_id: int, updates: dict) -> bool:
    """Обновить долг"""
    async with get_db() as session:
        try:
            result = await session.execute(
                update(Debt)
                .where(and_(Debt.id == debt_id, Debt.is_active == True))
                .values(**updates)
            )
            await session.commit()  # ДОБАВЛЕН КОММИТ
            return result.rowcount > 0
        except Exception as e:
            print(f"❌ Ошибка при обновлении долга {debt_id}: {e}")
            await session.rollback()
            raise


async def delete_debt(debt_id: int) -> bool:
    """Мягкое удаление долга (soft delete)"""
    return await soft_delete_debt(debt_id, None)  # None означает любого пользователя


async def clear_user_debts(user_id: int) -> bool:
    """Мягкое удаление всех долгов пользователя"""
    async with get_db() as session:
        try:
            result = await session.execute(
                update(Debt)
                .where(and_(Debt.user_id == user_id, Debt.is_active == True))
                .values(is_active=False)
            )
            await session.commit()  # ДОБАВЛЕН КОММИТ
            return result.rowcount > 0
        except Exception as e:
            print(f"❌ Ошибка при очистке долгов пользователя {user_id}: {e}")
            await session.rollback()
            raise


async def get_debt_by_id(debt_id: int) -> Optional[Dict[str, Any]]:
    """Получить долг по ID"""
    async with get_db() as session:
        result = await session.execute(
            select(Debt).where(and_(Debt.id == debt_id, Debt.is_active == True))
        )
        debt = result.scalar_one_or_none()

        if debt:
            return {
                'id': debt.id,
                'user_id': debt.user_id,
                'person': debt.person,
                'amount': debt.amount,
                'currency': debt.currency,
                'direction': debt.direction,
                'date': debt.date,
                'due': debt.due,
                'comment': debt.comment,
                'closed': debt.closed
            }
        return None


async def get_open_debts(user_id: int) -> List[Dict[str, Any]]:
    """Получить открытые (незакрытые) долги пользователя"""
    async with get_db() as session:
        result = await session.execute(
            select(Debt)
            .where(and_(
                Debt.user_id == user_id,
                Debt.closed == False,
                Debt.is_active == True
            ))
            .order_by(Debt.id)
        )
        debt_rows = result.scalars().all()

        debts = []
        for debt in debt_rows:
            debts.append({
                'id': debt.id,
                'person': debt.person,
                'amount': debt.amount,
                'currency': debt.currency,
                'direction': debt.direction,
                'date': debt.date,
                'due': debt.due,
                'comment': debt.comment,
                'closed': debt.closed
            })
        return debts


async def get_due_debts(user_id: int, days_until_due: int) -> List[Dict[str, Any]]:
    """Получить долги, которые истекают через указанное количество дней"""
    target_date = (datetime.now() + timedelta(days=days_until_due)).strftime('%Y-%m-%d')

    async with get_db() as session:
        result = await session.execute(
            select(Debt)
            .where(and_(
                Debt.user_id == user_id,
                Debt.closed == False,
                Debt.is_active == True,
                Debt.due == target_date
            ))
            .order_by(Debt.id)
        )
        debt_rows = result.scalars().all()

        debts = []
        for debt in debt_rows:
            debts.append({
                'id': debt.id,
                'person': debt.person,
                'amount': debt.amount,
                'currency': debt.currency,
                'direction': debt.direction,
                'date': debt.date,
                'due': debt.due,
                'comment': debt.comment,
                'closed': debt.closed
            })
        return debts


# === USER STATISTICS ===

async def get_all_users_with_notifications() -> List[Dict[str, Any]]:
    """Получить всех пользователей с настроенными уведомлениями"""
    async with get_db() as session:
        result = await session.execute(
            select(User.user_id, User.notify_time)
            .where(and_(
                User.notify_time.isnot(None),
                User.is_active == True
            ))
        )
        rows = result.all()

        users = []
        for row in rows:
            users.append({
                'user_id': row.user_id,
                'notify_time': row.notify_time
            })
        return users


async def get_all_users() -> List[Dict[str, Any]]:
    """Получить всех активных пользователей"""
    try:
        async with get_db() as session:
            result = await session.execute(
                select(User)
                .where(User.is_active == True)
                .order_by(User.user_id)
            )
            users_rows = result.scalars().all()

            users = []
            for user in users_rows:
                users.append({
                    'user_id': user.user_id,
                    'lang': user.lang,
                    'notify_time': user.notify_time,
                    'currency_notify_time': user.currency_notify_time  # ✅ ДОБАВЬ ЭТУ СТРОКУ
                })
            return users
    except Exception as e:
        print(f"❌ Ошибка получения списка пользователей: {e}")
        return []


async def get_user_count() -> int:
    """Получить количество активных пользователей"""
    try:
        async with get_db() as session:
            result = await session.execute(
                select(func.count(User.user_id))
                .where(User.is_active == True)
            )
            count = result.scalar()
            return count if count is not None else 0
    except Exception as e:
        print(f"❌ Ошибка получения количества пользователей: {e}")
        return 0


async def get_active_debts_count() -> int:
    """Получить количество активных долгов"""
    try:
        async with get_db() as session:
            result = await session.execute(
                select(func.count(Debt.id))
                .where(and_(
                    Debt.closed == False,
                    Debt.is_active == True
                ))
            )
            count = result.scalar()
            return count if count is not None else 0
    except Exception as e:
        print(f"❌ Ошибка получения количества активных долгов: {e}")
        return 0


# === SCHEDULED MESSAGES ===

async def save_scheduled_message(user_id: int, text: str, photo_id: str = None, schedule_time: str = None) -> int:
    """Сохранить запланированное сообщение"""
    async with get_db() as session:
        try:
            new_message = ScheduledMessage(
                user_id=user_id,
                text=text,
                photo_id=photo_id,
                schedule_time=schedule_time
            )
            session.add(new_message)
            await session.flush()
            await session.commit()  # ДОБАВЛЕН КОММИТ
            return new_message.id
        except Exception as e:
            print(f"❌ Ошибка при сохранении запланированного сообщения: {e}")
            await session.rollback()
            raise


async def get_scheduled_messages(user_id: int = None, sent: bool = False) -> List[ScheduledMessage]:
    """Получить запланированные сообщения"""
    async with get_db() as session:
        query = select(ScheduledMessage).where(and_(
            ScheduledMessage.sent == sent,
            ScheduledMessage.is_active == True
        ))

        if user_id:
            query = query.where(ScheduledMessage.user_id == user_id)

        result = await session.execute(query.order_by(ScheduledMessage.created_at))
        return result.scalars().all()


async def mark_message_as_sent(message_id: int) -> bool:
    """Отметить сообщение как отправленное"""
    async with get_db() as session:
        try:
            result = await session.execute(
                update(ScheduledMessage)
                .where(and_(ScheduledMessage.id == message_id, ScheduledMessage.is_active == True))
                .values(sent=True)
            )
            await session.commit()  # ДОБАВЛЕН КОММИТ
            return result.rowcount > 0
        except Exception as e:
            print(f"❌ Ошибка при отметке сообщения как отправленного: {e}")
            await session.rollback()
            raise


async def get_pending_scheduled_messages() -> List[Dict[str, Any]]:
    """Получить все ожидающие отправки запланированные сообщения"""
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    async with get_db() as session:
        result = await session.execute(
            select(ScheduledMessage)
            .where(and_(
                ScheduledMessage.sent == False,
                ScheduledMessage.is_active == True,
                ScheduledMessage.schedule_time <= current_time
            ))
            .order_by(ScheduledMessage.schedule_time)
        )
        messages_rows = result.scalars().all()

        messages = []
        for message in messages_rows:
            messages.append({
                'id': message.id,
                'user_id': message.user_id,
                'text': message.text,
                'photo_id': message.photo_id,
                'schedule_time': message.schedule_time
            })
        return messages


async def delete_scheduled_message(message_id: int) -> bool:
    """Мягкое удаление запланированного сообщения"""
    async with get_db() as session:
        try:
            result = await session.execute(
                update(ScheduledMessage)
                .where(ScheduledMessage.id == message_id)
                .values(is_active=False)
            )
            await session.commit()  # ДОБАВЛЕН КОММИТ
            return result.rowcount > 0
        except Exception as e:
            print(f"❌ Ошибка при удалении запланированного сообщения: {e}")
            await session.rollback()
            raise


async def execute_query_safely(query_func, *args, **kwargs):
    """
    Безопасное выполнение запроса с обработкой ошибок сессии
    """
    max_retries = 3
    for attempt in range(max_retries):
        try:
            return await query_func(*args, **kwargs)
        except Exception as e:
            if "IllegalStateChangeError" in str(e) and attempt < max_retries - 1:
                print(f"⚠️ Повтор запроса после ошибки сессии (попытка {attempt + 1})")
                await asyncio.sleep(0.1)
                continue
            else:
                raise e

async def add_reminder(session: AsyncSession, user_id: int, text: str, due: datetime, repeat: str = "none"):
    reminder = Reminder(
        user_id=user_id,
        text=text,
        due=due,
        repeat=repeat,
        is_active=True,
        created_at=datetime.utcnow()
    )
    session.add(reminder)
    await session.commit()
    await session.refresh(reminder)
    return reminder



# 🔍 Получить одно напоминание по id
async def get_reminder(session: AsyncSession, reminder_id: int):
    result = await session.execute(
        select(Reminder).where(Reminder.id == reminder_id)
    )
    return result.scalar_one_or_none()


# 🗑 Удалить напоминание
async def delete_reminder(reminder_id: int):
    """Удалить напоминание (soft delete)"""
    async with get_db() as session:
        try:
            # Получаем напоминание
            reminder = await session.get(Reminder, reminder_id)
            if not reminder:
                print(f"⚠️ Напоминание {reminder_id} не найдено")
                return False

            # Деактивируем
            reminder.is_active = False
            await session.commit()

            print(f"✅ Напоминание {reminder_id} деактивировано")
            return True

        except Exception as e:
            print(f"❌ Ошибка удаления напоминания {reminder_id}: {e}")
            await session.rollback()
            return False


# ✏️ Обновить напоминание
async def update_reminder(session: AsyncSession, reminder_id: int, **kwargs):
    await session.execute(
        update(Reminder)
        .where(Reminder.id == reminder_id)
        .values(**kwargs)
    )
    await session.commit()


# Включить напоминания (ставим дефолтное время)
async def enable_debt_reminders(session, user_id: int, default_time: str = "09:00"):
    user = await get_or_create_user(user_id, session)
    user.notify_time = default_time
    await session.commit()

# Выключить напоминания (ставим None)
async def disable_debt_reminders(session, user_id: int):
    user = await get_or_create_user(user_id, session)
    user.notify_time = None
    await session.commit()

# Установить конкретное время
async def set_debt_reminder_time(session, user_id: int, time_str: str):
    user = await get_or_create_user(user_id, session)
    user.notify_time = time_str
    await session.commit()

from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, time, timedelta
from .models import Reminder, User





async def get_user_reminders(session: AsyncSession, user_id: int):
    result = await session.execute(
        select(Reminder).where(
            Reminder.user_id == user_id,
            Reminder.is_active == True,
            getattr(Reminder, "system", False) == False  # если поля system нет, False == False
        ).order_by(Reminder.id.desc())
    )
    return result.scalars().all()

# Получить одно напоминание по id
async def get_reminder_by_id(session: AsyncSession, reminder_id: int, user_id: int):
    result = await session.execute(
        select(Reminder).where(Reminder.id == reminder_id, Reminder.user_id == user_id)
    )
    return result.scalars().first()

# Обновить текст напоминания
async def update_reminder_text(session: AsyncSession, reminder_id: int, user_id: int, new_text: str):
    r = await get_reminder_by_id(session, reminder_id, user_id)
    if r:
        r.text = new_text
        await session.commit()
        await session.refresh(r)
    return r

# Создать системное валютное напоминание (07:00 или 17:00)
async def create_currency_reminder(session: AsyncSession, user_id: int, hour: int):
    # Удалим предыдущие системные валютные напоминания
    await delete_currency_reminders(session, user_id)

    now = datetime.now()
    first_due = datetime.combine(now.date(), time(hour=hour, minute=0))
    if first_due <= now:
        first_due += timedelta(days=1)

    # Поле system=True — чтобы не показывать в списке
    r = Reminder(
        user_id=user_id,
        text="Курс валют",
        due=first_due,
        repeat="daily",
        is_active=True
    )
    # Если в модели есть колонка system — выставим
    if hasattr(r, "system"):
        setattr(r, "system", True)

    session.add(r)
    await session.commit()
    await session.refresh(r)
    return r

# Отключить (удалить) системные валютные напоминания
async def delete_currency_reminders(session: AsyncSession, user_id: int):
    # Если в модели есть колонка system — фильтруем по ней
    if hasattr(Reminder, "system"):
        await session.execute(
            delete(Reminder).where(
                Reminder.user_id == user_id,
                Reminder.is_active == True,
                Reminder.repeat == "daily",
                Reminder.text == "Курс валют",
                Reminder.system == True
            )
        )
    else:
        # Фоллбек, если поля system нет: ориентируемся по тексту и repeat
        await session.execute(
            delete(Reminder).where(
                Reminder.user_id == user_id,
                Reminder.is_active == True,
                Reminder.repeat == "daily",
                Reminder.text == "Курс валют"
            )
        )
    await session.commit()

async def set_user_currency_time(session, user_id: int, value: str | None):
    user = await session.get(User, user_id)
    if not user:
        print('Нет юзера')
        return None
    user.currency_notify_time = value
    await session.commit()
    await session.refresh(user)
    print(vars(user))
    return user

async def get_user_currency_time(session, user_id: int) -> str | None:
    user = await session.get(User, user_id)
    if not user:
        return None
    return user.currency_notify_time
async def get_due_reminders(now):
    async with get_db() as session:
        result = await session.execute(
            select(Reminder).where(
                Reminder.due <= now,
                Reminder.repeat == "none",
                Reminder.is_active == True  # ← Добавьте эту проверку
            )
        )
        reminders = result.scalars().all()
        return [{
            'id': r.id,
            'user_id': r.user_id,
            'text': r.text,
            'due': r.due,
            'repeat': r.repeat,
            'is_active': r.is_active
        } for r in reminders]

async def get_due_repeating_reminders(now):
    async with get_db() as session:
        result = await session.execute(
            select(Reminder).where(
                Reminder.due <= now,
                Reminder.repeat != "none",
                Reminder.is_active == True  # ← Добавьте эту проверку
            )
        )
        reminders = result.scalars().all()
        return [{
            'id': r.id,
            'user_id': r.user_id,
            'text': r.text,
            'due': r.due,
            'repeat': r.repeat,
            'is_active': r.is_active
        } for r in reminders]
# обновить дату напоминания
async def update_reminder_due(reminder_id, new_due):
    async with get_db() as session:
        reminder = await session.get(Reminder, reminder_id)
        if reminder:
            reminder.due = new_due
            await session.commit()



# получить валютные настройки пользователя
async def get_user_currency_settings(user_id):
    async with get_db() as session:
        user = await session.get(User, user_id)
        if user and user.currency_base and user.currency_quote:
            return {"base": user.currency_base, "quote": user.currency_quote}
        return None


async def create_debts_from_ai(debts_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Создать несколько долгов (до 10) на основе JSON, полученного от ИИ.
    Ожидает список словарей с ключами:
    user_id, person, amount, currency, direction, date, due, comment
    """
    results: List[Dict[str, Any]] = []

    async with get_db() as session:
        try:
            for idx, debt_data in enumerate(debts_data[:10], start=1):
                # Проверим, что пользователь существует
                user = await session.get(User, debt_data["user_id"])
                if not user:
                    user = User(user_id=debt_data["user_id"])
                    session.add(user)
                    await session.flush()

                new_debt = Debt(
                    user_id=debt_data["user_id"],
                    person=debt_data["person"],
                    amount=debt_data["amount"],
                    currency=debt_data["currency"],
                    direction=debt_data["direction"],
                    date=debt_data.get("date", datetime.utcnow().date().isoformat()),
                    due=debt_data["due"],
                    comment=debt_data.get("comment", "")
                )
                session.add(new_debt)
                await session.flush()

                results.append({
                    'id': new_debt.id,
                    'user_id': new_debt.user_id,
                    'person': new_debt.person,
                    'amount': new_debt.amount,
                    'currency': new_debt.currency,
                    'direction': new_debt.direction,
                    'date': new_debt.date,
                    'due': new_debt.due,
                    'comment': new_debt.comment,
                    'closed': new_debt.closed
                })

            await session.commit()
            print(f"✅ Добавлено долгов: {len(results)}")
            return results

        except Exception as e:
            print(f"❌ Ошибка при создании долгов через ИИ: {e}")
            await session.rollback()
            return []
