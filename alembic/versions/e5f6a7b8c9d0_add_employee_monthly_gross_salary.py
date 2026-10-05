"""add employees.monthly_gross_salary (salary structure for the payroll engine)

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-10-05 13:00:00.000000

The payroll engine (salary_service.generate_payroll, PROJECT_DECISIONS D-021)
needs each employee's monthly gross salary. Existing employees are backfilled
from their most recent salary record.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('employees', sa.Column('monthly_gross_salary', sa.Numeric(12, 2), nullable=True))

    # Backfill from the latest salary record of each employee
    bind = op.get_bind()
    latest = bind.execute(sa.text(
        """
        SELECT s.employee_id, s.gross_salary
        FROM salary s
        JOIN (
            SELECT employee_id, MAX(year * 100 + month) AS period
            FROM salary GROUP BY employee_id
        ) last ON last.employee_id = s.employee_id AND (s.year * 100 + s.month) = last.period
        """
    )).all()
    for employee_id, gross in latest:
        bind.execute(
            sa.text("UPDATE employees SET monthly_gross_salary = :g WHERE id = :i AND monthly_gross_salary IS NULL"),
            {"g": gross, "i": employee_id},
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('employees', 'monthly_gross_salary')
