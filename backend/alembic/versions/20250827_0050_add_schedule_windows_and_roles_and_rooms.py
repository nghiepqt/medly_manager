"""
add schedule_windows, doctor roles, rooms

Revision ID: 20250827_0050
Revises: 20250827_0040
Create Date: 2025-08-27 13:10:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20250827_0050'
down_revision = '20250827_0040'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # doctors.roles as JSONB
    op.add_column('doctors', sa.Column('roles', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # schedule_windows
    op.create_table(
        'schedule_windows',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('doctor_id', sa.Integer(), nullable=False),
        sa.Column('start', sa.DateTime(), nullable=False),
        sa.Column('end', sa.DateTime(), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(['doctor_id'], ['doctors.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('doctor_id', 'start', 'end', 'kind', name='uq_window_unique')
    )

    # rooms
    op.create_table(
        'rooms',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('department_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['department_id'], ['departments.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('department_id', 'code', name='uq_room_department_code')
    )


def downgrade() -> None:
    op.drop_table('rooms')
    op.drop_table('schedule_windows')
    op.drop_column('doctors', 'roles')
