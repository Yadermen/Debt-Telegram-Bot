# app/database/connection.py
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from .models import Base

load_dotenv()

# Получаем URL из переменных окружения или используем SQLite по умолчанию
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    # Fallback на SQLite если PostgreSQL не настроен
    from app.config import DB_PATH
    DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"
    print("⚠️ Используется SQLite (DATABASE_URL не найден)")
else:
    print(f"✅ Подключение к PostgreSQL: {DATABASE_URL.replace('secure_password_123', '***')}")

# Создаем движок с правильными настройками для PostgreSQL или SQLite
if DATABASE_URL.startswith('postgresql'):
    # Настройки для PostgreSQL
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
else:
    # Настройки для SQLite
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=False,
        connect_args={'check_same_thread': False}
    )

# Создаем фабрику сессий
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=True,
    autocommit=False
)


async def init_db():
    """Инициализация базы данных - создание таблиц"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Таблицы созданы/проверены")
    except Exception as e:
        print(f"❌ Ошибка создания таблиц: {e}")
        raise


async def test_connection():
    """Тестирование подключения к БД"""
    try:
        async with engine.begin() as conn:
            if DATABASE_URL.startswith('postgresql'):
                result = await conn.execute("SELECT version();")
                version = result.fetchone()[0]
                print(f"✅ PostgreSQL подключен: {version}")
            else:
                result = await conn.execute("SELECT sqlite_version();")
                version = result.fetchone()[0]
                print(f"✅ SQLite подключен: {version}")
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return False


@asynccontextmanager
async def get_db():
    """Контекстный менеджер для получения сессии базы данных"""
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
            if session.is_active:
                await session.close()
        except Exception as close_error:
            print(f"⚠️ Предупреждение при закрытии сессии: {close_error}")
            try:
                await session.invalidate()
            except Exception:
                pass