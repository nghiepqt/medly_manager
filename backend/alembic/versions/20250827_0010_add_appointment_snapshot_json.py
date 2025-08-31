"""add appointment snapshot json

Revision ID: 20250827_0010
Revises: 20250825_0002
Create Date: 2025-08-27
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '20250827_0010'
down_revision: Union[str, None] = '20250825_0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add created_at with server default now() for existing rows
    op.add_column('appointments', sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=True))
    # Add conversation_id nullable + FK
    op.add_column('appointments', sa.Column('conversation_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_appointments_conversation', 'appointments', 'conversations', ['conversation_id'], ['id'], ondelete='SET NULL'
    )
    # Add JSONB content snapshot
    op.add_column('appointments', sa.Column('content', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # Indexes
    op.create_index('ix_appointments_created_at', 'appointments', ['created_at'])
    op.create_index('ix_appointments_when', 'appointments', ['when'])


def downgrade() -> None:
    op.drop_index('ix_appointments_when', table_name='appointments')
    op.drop_index('ix_appointments_created_at', table_name='appointments')
    op.drop_constraint('fk_appointments_conversation', 'appointments', type_='foreignkey')
    op.drop_column('appointments', 'content')
    op.drop_column('appointments', 'conversation_id')
    op.drop_column('appointments', 'created_at')
