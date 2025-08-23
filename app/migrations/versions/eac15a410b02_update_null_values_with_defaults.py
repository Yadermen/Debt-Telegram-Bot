"""update null values with defaults

Revision ID: [будет сгенерирован автоматически]
Revises: 2a7cc91966f4
Create Date: [будет сгенерирована автоматически]

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from datetime import datetime

# revision identifiers, used by Alembic.
revision: str = '[будет сгенерирован]'
down_revision: Union[str, Sequence[str], None] = '2a7cc91966f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Update NULL values with defaults."""

    # Обновляем таблицу debts
    debts_table = table('debts',
        column('is_active', sa.Boolean),
        column('created_at', sa.DateTime)
    )

    # Устанавливаем is_active = True для всех записей где NULL
    op.execute(
        debts_table.update()
        .where(debts_table.c.is_active.is_(None))
        .values(is_active=True)
    )

    # Устанавливаем created_at = текущее время для всех записей где NULL
    op.execute(
        "UPDATE debts SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
    )

    # Обновляем таблицу users
    users_table = table('users',
        column('is_active', sa.Boolean),
        column('created_at', sa.DateTime)
    )

    # Устанавливаем is_active = True для пользователей где NULL
    op.execute(
        users_table.update()
        .where(users_table.c.is_active.is_(None))
        .values(is_active=True)
    )

    # Устанавливаем created_at = текущее время для пользователей где NULL
    op.execute(
        "UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
    )

    # Обновляем таблицу scheduled_messages
    scheduled_table = table('scheduled_messages',
        column('is_active', sa.Boolean)
    )

    # Устанавливаем is_active = True для запланированных сообщений где NULL
    op.execute(
        scheduled_table.update()
        .where(scheduled_table.c.is_active.is_(None))
        .values(is_active=True)
    )

    print("✅ Все NULL значения обновлены значениями по умолчанию")


def downgrade() -> None:
    """Откат - возвращаем NULL значения (опционально)."""
    # При необходимости можно вернуть NULL значения
    # Но обычно это не требуется
    pass