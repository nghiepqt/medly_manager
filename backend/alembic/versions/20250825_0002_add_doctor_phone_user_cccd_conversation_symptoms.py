"""add doctor.phone, user.cccd, conversation.symptoms

Revision ID: 20250825_0002
Revises: 20250825_0001
Create Date: 2025-08-25
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20250825_0002'
down_revision: Union[str, None] = '20250825_0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add phone to doctors
    with op.batch_alter_table('doctors') as batch_op:
        batch_op.add_column(sa.Column('phone', sa.String(length=10), nullable=True))

    # Add cccd to users
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('cccd', sa.String(length=12), nullable=True))
        batch_op.create_unique_constraint('uq_users_cccd', ['cccd'])

    # Add symptoms to conversations
    with op.batch_alter_table('conversations') as batch_op:
        batch_op.add_column(sa.Column('symptoms', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('conversations') as batch_op:
        batch_op.drop_column('symptoms')

    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('uq_users_cccd', type_='unique')
        batch_op.drop_column('cccd')

    with op.batch_alter_table('doctors') as batch_op:
        batch_op.drop_column('phone')
