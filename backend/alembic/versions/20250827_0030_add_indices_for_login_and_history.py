"""
add indices for fast login and history queries

Revision ID: 20250827_0030
Revises: 20250827_0020
Create Date: 2025-08-27 00:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20250827_0030'
down_revision = '20250827_0020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users: functional index on lower(name) with phone for fast equality lookup
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_lower_name_phone ON users (lower(name), phone)")

    # appointments: composite indexes for per-user queries
    op.execute("CREATE INDEX IF NOT EXISTS ix_appointments_user_created_at ON appointments (user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_appointments_user_when ON appointments (user_id, \"when\")")

    # slots: speed up lookups by doctor and time window
    op.execute("CREATE INDEX IF NOT EXISTS ix_slots_doctor_start_end ON slots (doctor_id, start, \"end\")")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_slots_doctor_start_end")
    op.execute("DROP INDEX IF EXISTS ix_appointments_user_when")
    op.execute("DROP INDEX IF EXISTS ix_appointments_user_created_at")
    op.execute("DROP INDEX IF EXISTS ix_users_lower_name_phone")
