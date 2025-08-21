from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, and_, func
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from .models import User, Debt, ScheduledMessage
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


async def get_or_create_user(user_id: int, session: AsyncSession = None) -> User:
    """Получить пользователя или создать если не существует"""
    if session is None:
        async with get_db() as session:
            return await get_or_create_user(user_id, session)

    # Ищем пользователя
    result = await session.execute(
        select(User).where(and_(User.user_id == user_id, User.is_active == True))
    )
    user = result.scalar_one_or_none()

    if not user:
        # Создаем нового пользователя
        user = User(user_id=user_id, lang='ru', notify_time='09:00')
        session.add(user)
        await session.flush()  # Чтобы получить ID

    return user


async def save_user_lang(user_id: int, lang: str) -> None:
    """Сохранить язык пользователя"""
    async with get_db() as session:
        user = await get_or_create_user(user_id, session)
        user.lang = lang


async def save_user_notify_time(user_id: int, notify_time: str) -> None:
    """Сохранить время уведомлений пользователя"""
    async with get_db() as session:
        user = await get_or_create_user(user_id, session)
        user.notify_time = notify_time


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
        return result.rowcount > 0


async def soft_delete_user(user_id: int) -> bool:
    """Мягкое удаление пользователя (установка is_active = False)"""
    async with get_db() as session:
        result = await session.execute(
            update(User)
            .where(User.user_id == user_id)
            .values(is_active=False)
        )
        return result.rowcount > 0


# === DEBT OPERATIONS ===

async def add_debt(user_id: int, debt: dict) -> int:
    """Добавить новый долг"""
    async with get_db() as session:
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
        return new_debt.id


async def update_debt(debt_id: int, updates: dict) -> bool:
    """Обновить долг"""
    async with get_db() as session:
        result = await session.execute(
            update(Debt)
            .where(and_(Debt.id == debt_id, Debt.is_active == True))
            .values(**updates)
        )
        return result.rowcount > 0


async def delete_debt(debt_id: int) -> bool:
    """Мягкое удаление долга (soft delete)"""
    return await soft_delete_debt(debt_id, None)  # None означает любого пользователя


async def clear_user_debts(user_id: int) -> bool:
    """Мягкое удаление всех долгов пользователя"""
    async with get_db() as session:
        result = await session.execute(
            update(Debt)
            .where(and_(Debt.user_id == user_id, Debt.is_active == True))
            .values(is_active=False)
        )
        return result.rowcount > 0


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
    """Получить всех пользователей со статистикой"""
    async with get_db() as session:
        # Подзапрос для активных долгов
        active_debts_subq = (
            select(func.count(Debt.id))
            .where(and_(
                Debt.user_id == User.user_id,
                Debt.closed == False,
                Debt.is_active == True
            ))
        ).scalar_subquery()

        # Подзапрос для всех долгов
        total_debts_subq = (
            select(func.count(Debt.id))
            .where(and_(
                Debt.user_id == User.user_id,
                Debt.is_active == True
            ))
        ).scalar_subquery()

        result = await session.execute(
            select(
                User.user_id,
                User.lang,
                User.notify_time,
                active_debts_subq.label('active_debts'),
                total_debts_subq.label('total_debts')
            )
            .where(User.is_active == True)
            .order_by(User.user_id)
        )

        rows = result.all()
        users = []
        for row in rows:
            users.append({
                'user_id': row.user_id,
                'lang': row.lang,
                'notify_time': row.notify_time,
                'active_debts': row.active_debts or 0,
                'total_debts': row.total_debts or 0
            })
        return users


async def get_user_count() -> int:
    """Получить количество активных пользователей"""
    async with get_db() as session:
        result = await session.execute(
            select(func.count(User.user_id))
            .where(User.is_active == True)
        )
        return result.scalar() or 0


async def get_active_debts_count() -> int:
    """Получить количество активных долгов"""
    async with get_db() as session:
        result = await session.execute(
            select(func.count(Debt.id))
            .where(and_(
                Debt.closed == False,
                Debt.is_active == True
            ))
        )
        return result.scalar() or 0


# === SCHEDULED MESSAGES ===

async def save_scheduled_message(user_id: int, text: str, photo_id: str = None, schedule_time: str = None) -> int:
    """Сохранить запланированное сообщение"""
    async with get_db() as session:
        new_message = ScheduledMessage(
            user_id=user_id,
            text=text,
            photo_id=photo_id,
            schedule_time=schedule_time
        )
        session.add(new_message)
        await session.flush()
        return new_message.id


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
        result = await session.execute(
            update(ScheduledMessage)
            .where(and_(ScheduledMessage.id == message_id, ScheduledMessage.is_active == True))
            .values(sent=True)
        )
        return result.rowcount > 0


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
        result = await session.execute(
            update(ScheduledMessage)
            .where(ScheduledMessage.id == message_id)
            .values(is_active=False)
        )
        return result.rowcount > 0