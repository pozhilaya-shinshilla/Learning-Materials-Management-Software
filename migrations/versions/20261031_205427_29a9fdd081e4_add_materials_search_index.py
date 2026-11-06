"""add materials search index (full-text GIN)

Revision ID: 29a9fdd081e4
Revises: 4a8c6f486877
Create Date: 2026-10-31 20:54:27.026070+00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "29a9fdd081e4"
down_revision: str | Sequence[str] | None = "4a8c6f486877"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema.

    Alembic не умеет сравнивать индексы по выражениям, поэтому индекс создан вручную. Выражение
    должно совпадать с `material_search_vector()` в `src/database/models.py`: иначе PostgreSQL
    не станет использовать индекс для запросов поиска.
    """
    op.create_index(
        "ix_materials_search_vector",
        "materials",
        [sa.text("to_tsvector('russian'::regconfig, title || ' ' || description)")],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_materials_search_vector", table_name="materials", postgresql_using="gin")
