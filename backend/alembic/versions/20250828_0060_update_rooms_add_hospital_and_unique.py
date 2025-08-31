"""
add hospital_id to rooms and make (hospital_id, code) unique

Revision ID: 20250828_0060
Revises: 20250827_0050
Create Date: 2025-08-28
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20250828_0060'
down_revision: Union[str, None] = '20250827_0050'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) Add column hospital_id (nullable for backfill)
    op.add_column('rooms', sa.Column('hospital_id', sa.Integer(), nullable=True))
    # 2) Add FK to hospitals
    op.create_foreign_key('fk_rooms_hospital', 'rooms', 'hospitals', ['hospital_id'], ['id'])

    # 3) Backfill hospital_id using departments.hospital_id
    op.execute(
        """
        UPDATE rooms r
        SET hospital_id = d.hospital_id
        FROM departments d
        WHERE r.department_id = d.id AND r.hospital_id IS NULL
        """
    )

    # 4) Make column non-null
    op.alter_column('rooms', 'hospital_id', existing_type=sa.Integer(), nullable=False)

    # 5) Replace unique(department_id, code) with unique(hospital_id, code)
    # Drop old constraint if exists
    try:
        op.drop_constraint('uq_room_department_code', 'rooms', type_='unique')
    except Exception:
        pass
    op.create_unique_constraint('uq_room_hospital_code', 'rooms', ['hospital_id', 'code'])


def downgrade() -> None:
    # Reverse unique to department_id, code
    try:
        op.drop_constraint('uq_room_hospital_code', 'rooms', type_='unique')
    except Exception:
        pass
    op.create_unique_constraint('uq_room_department_code', 'rooms', ['department_id', 'code'])

    # Drop FK and column
    try:
        op.drop_constraint('fk_rooms_hospital', 'rooms', type_='foreignkey')
    except Exception:
        pass
    op.drop_column('rooms', 'hospital_id')
