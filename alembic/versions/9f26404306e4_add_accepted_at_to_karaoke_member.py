"""add_accepted_at_to_karaoke_member

Revision ID: 9f26404306e4
Revises: 6765d0be1f52
Create Date: 2026-09-18 02:39:49.434586

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f26404306e4"
down_revision: str | Sequence[str] | None = "6765d0be1f52"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("karaoke_member", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("karaoke_member", "accepted_at")
