"""add discipline_deleted and topic_deleted event types

Revision ID: 5b7d2c9e41aa
Revises: 29a9fdd081e4
Create Date: 2026-11-01 12:00:00.000000+00:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "5b7d2c9e41aa"
down_revision: str | Sequence[str] | None = "29a9fdd081e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Добавить в enum `event_type` значения для удаления дисциплин и тем."""
    # Новое значение enum нельзя использовать в той же транзакции, где оно добавлено,
    # поэтому команды выполняются вне транзакции миграции.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'discipline_deleted'")
        op.execute("ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'topic_deleted'")


def downgrade() -> None:
    """Значения enum в PostgreSQL удалить нельзя: откат ничего не меняет (они не мешают)."""
