from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from contextlib import asynccontextmanager
from app.config import DB_PATH
from .models import Base

DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

# Создаем асинхронный движок без пула соединений для SQLite
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    # Для SQLite убираем настройки пула
    pool_pre_ping=False,
    connect_args={'check_same_thread': False}
)

# ИСПРАВЛЕНО: Используем async_sessionmaker вместо scoped_session
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
    autocommit=False
)


async def init_db():
    """Инициализация базы данных - создание таблиц"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_db():
    """Исправленный контекстный менеджер для получения сессии базы данных"""
    session = AsyncSessionLocal()
    try:
        yield session
        # Коммитим только если есть pending изменения
        if session.dirty or session.new or session.deleted:
            await session.commit()
    except Exception as e:
        # Откатываем транзакцию при ошибке
        try:
            await session.rollback()
        except Exception:
            pass  # Игнорируем ошибки отката
        raise e
    finally:
        # Безопасно закрываем сессию
        try:
            # Проверяем, не закрыта ли уже сессия
            if session.is_active:
                await session.close()
        except Exception as close_error:
            print(f"⚠️ Предупреждение при закрытии сессии: {close_error}")
            # Пытаемся принудительно закрыть
            try:
                await session.invalidate()
            except Exception:
                pass