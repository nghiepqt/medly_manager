"""drop conversation_id from appointments

Revision ID: 20250827_0020
Revises: 20250827_0010
Create Date: 2025-08-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20250827_0020'
down_revision: Union[str, None] = '20250827_0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop FK if exists, then drop column
    bind = op.get_bind()
    insp = sa.inspect(bind)
    # Best-effort: try drop FK by known name
    try:
        op.drop_constraint('fk_appointments_conversation', 'appointments', type_='foreignkey')
    except Exception:
        pass
    # Drop the column if it exists
    cols = [c['name'] for c in insp.get_columns('appointments')]
    if 'conversation_id' in cols:
        op.drop_column('appointments', 'conversation_id')


def downgrade() -> None:
    op.add_column('appointments', sa.Column('conversation_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_appointments_conversation', 'appointments', 'conversations', ['conversation_id'], ['id'], ondelete='SET NULL')
