"""add holidays and attendance_corrections

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-10-06 12:00:00.000000

- holidays: company holidays declared by HR for one date (D-034). The fixed mandatory
  national holidays stay in code (attendance_service.COMPANY_HOLIDAYS).
- attendance_corrections: employee requests to correct one day's attendance, approved by
  the manager or HR/Admin, never by the requester (D-033).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'holidays',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('holiday_date', sa.Date(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('holiday_date'),
    )
    op.create_table(
        'attendance_corrections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('employee_id', sa.Integer(), nullable=False),
        sa.Column('attendance_date', sa.Date(), nullable=False),
        sa.Column('attendance_id', sa.Integer(), nullable=True),
        sa.Column('requested_in_time', sa.Time(), nullable=False),
        sa.Column('requested_out_time', sa.Time(), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('requested_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('review_note', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id']),
        sa.ForeignKeyConstraint(['attendance_id'], ['attendance.id']),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_attendance_corrections_employee_id'), 'attendance_corrections', ['employee_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_attendance_corrections_employee_id'), table_name='attendance_corrections')
    op.drop_table('attendance_corrections')
    op.drop_table('holidays')
