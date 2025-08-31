"""
add hospital address column

Revision ID: 20250827_0040
Revises: 20250827_0030
Create Date: 2025-08-27 01:10:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250827_0040'
down_revision = '20250827_0030'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('hospitals', sa.Column('address', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('hospitals', 'address')
