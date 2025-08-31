"""init schema

Revision ID: 20250825_0001
Revises: 
Create Date: 2025-08-25
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20250825_0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table('hospitals',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False, unique=True)
    )
    op.create_table('departments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('hospital_id', sa.Integer(), sa.ForeignKey('hospitals.id', ondelete=None), nullable=False)
    )
    op.create_unique_constraint('uq_department_hospital_name', 'departments', ['hospital_id', 'name'])

    op.create_table('doctors',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('department_id', sa.Integer(), sa.ForeignKey('departments.id'), nullable=False)
    )

    op.create_table('users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False, unique=True)
    )

    op.create_table('appointments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('doctor_id', sa.Integer(), sa.ForeignKey('doctors.id'), nullable=False),
        sa.Column('when', sa.DateTime(), nullable=False),
        sa.Column('need', sa.Text(), nullable=True),
        sa.Column('symptoms', sa.Text(), nullable=True)
    )

    op.create_table('slots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('doctor_id', sa.Integer(), sa.ForeignKey('doctors.id'), nullable=False),
        sa.Column('start', sa.DateTime(), nullable=False),
        sa.Column('end', sa.DateTime(), nullable=False),
        sa.Column('is_busy', sa.Boolean(), nullable=False, server_default=sa.text('false'))
    )
    op.create_unique_constraint('uq_slot_unique', 'slots', ['doctor_id', 'start', 'end'])

    op.create_table('conversations',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False)
    )


def downgrade() -> None:
    op.drop_table('conversations')
    op.drop_constraint('uq_slot_unique', 'slots', type_='unique')
    op.drop_table('slots')
    op.drop_table('appointments')
    op.drop_table('users')
    op.drop_table('doctors')
    op.drop_constraint('uq_department_hospital_name', 'departments', type_='unique')
    op.drop_table('departments')
    op.drop_table('hospitals')
