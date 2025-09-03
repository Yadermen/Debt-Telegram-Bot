from sqlalchemy import Column, Integer, BigInteger, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    user_id = Column(BigInteger, primary_key=True)  # Изменено на BigInteger для Telegram ID
    lang = Column(String, default='ru')
    notify_time = Column(String, default='09:00')
    is_active = Column(Boolean, default=True)  # Для soft delete
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    debts = relationship("Debt", back_populates="user")
    scheduled_messages = relationship("ScheduledMessage", back_populates="user")


class Debt(Base):
    __tablename__ = 'debts'

    id = Column(Integer, primary_key=True, autoincrement=True)  # Обычный автоинкремент можно оставить Integer
    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)  # Изменено на BigInteger
    person = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(String, default='UZS')
    direction = Column(String, nullable=False)  # 'owe' или 'owed'
    date = Column(String, nullable=False)
    due = Column(String, nullable=False)
    comment = Column(Text, default='')
    closed = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)  # Для soft delete
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="debts")


class ScheduledMessage(Base):
    __tablename__ = 'scheduled_messages'

    id = Column(Integer, primary_key=True, autoincrement=True)  # Обычный автоинкремент можно оставить Integer
    user_id = Column(BigInteger, ForeignKey('users.user_id'), nullable=False)  # Изменено на BigInteger
    text = Column(Text, nullable=False)
    photo_id = Column(String, nullable=True)
    schedule_time = Column(String, nullable=False)
    sent = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="scheduled_messages")


def safe_str(value):
    """Безопасное преобразование в строку"""
    if value is None:
        return ""
    return str(value)