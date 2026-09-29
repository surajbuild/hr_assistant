"""
app/services/salary_service.py
------------------------------
Service layer for salary management business logic and database operations.

Contains reusable Python functions for:
- Retrieving salary records for the authenticated employee (with strict data isolation)
- Retrieving salary records for a specific employee (with employee existence validation)
- Retrieving salary records for a specific month and year

This module is independent of FastAPI HTTP concerns (no Request, HTTPException,
or status codes) so that it can be safely invoked by both API routers and AI/tool agents.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.database.models import Employee, Salary


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class SalaryServiceError(Exception):
    """Base exception for salary service operations."""
    pass


class EmployeeNotFoundError(SalaryServiceError):
    """Raised when an operation targets an employee that does not exist."""
    pass


class InvalidSalaryFilterError(SalaryServiceError):
    """Raised when month or year filter is invalid."""
    pass


# ---------------------------------------------------------------------------
# Queries / Retrieval
# ---------------------------------------------------------------------------

def get_salary_by_employee_id(
    db: Session,
    employee_id: int,
) -> List[Salary]:
    """
    Retrieve all salary records belonging to a specific employee ID.

    Returns an empty list if no records exist.
    """
    return db.query(Salary).filter(Salary.employee_id == employee_id).all()


def get_my_salary(
    db: Session,
    employee_id: int,
) -> List[Salary]:
    """
    Retrieve salary records for the authenticated employee.

    Convenience wrapper around get_salary_by_employee_id.
    Ensures data isolation by strictly scoping to the authenticated employee's ID.
    """
    return get_salary_by_employee_id(db, employee_id=employee_id)


def get_salary_for_employee(
    db: Session,
    employee_id: int,
) -> List[Salary]:
    """
    Retrieve salary records for a specific employee ID.

    Validates that the target employee exists in the database.

    Raises:
        EmployeeNotFoundError: If the employee ID is not found.

    Returns:
        List[Salary]: The employee's salary records (or empty list if no records exist).
    """
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise EmployeeNotFoundError("Employee not found.")

    return get_salary_by_employee_id(db, employee_id=employee_id)


def get_salary_by_month(
    db: Session,
    employee_id: int,
    month: int,
    year: int,
) -> Optional[Salary]:
    """
    Retrieve a specific salary record for an employee for a given month and year.

    Returns None if no matching record is found.
    """
    return db.query(Salary).filter(
        Salary.employee_id == employee_id,
        Salary.month == month,
        Salary.year == year,
    ).first()


# ---------------------------------------------------------------------------
# Aggregation & Summary Calculations
# ---------------------------------------------------------------------------

def get_salary_summary(
    db: Session,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Calculate aggregated salary statistics across the organization.

    Computes:
      - total_records / record_count: Count of salary records included
      - total_employees / employee_count: Count of distinct employees included
      - total_gross_salary: Sum of gross_salary
      - total_pf: Sum of pf
      - total_deductions: Sum of deductions
      - total_overtime_amount: Sum of overtime_amount
      - total_net_salary: Sum of net_salary

    Supports optional month and year filtering.

    Raises:
        InvalidSalaryFilterError: If month is not in 1..12 or year <= 0.

    Returns:
        Dict[str, Any]: Aggregated summary metrics (zero totals if no records match).
    """
    if month is not None:
        if not isinstance(month, int) or month < 1 or month > 12:
            raise InvalidSalaryFilterError("Month must be an integer between 1 and 12.")

    if year is not None:
        if not isinstance(year, int) or year <= 0:
            raise InvalidSalaryFilterError("Year must be a positive integer.")

    query = db.query(
        func.count(Salary.id).label("total_records"),
        func.count(distinct(Salary.employee_id)).label("total_employees"),
        func.sum(Salary.gross_salary).label("total_gross_salary"),
        func.sum(Salary.pf).label("total_pf"),
        func.sum(Salary.deductions).label("total_deductions"),
        func.sum(Salary.overtime_amount).label("total_overtime_amount"),
        func.sum(Salary.net_salary).label("total_net_salary"),
    )

    if month is not None:
        query = query.filter(Salary.month == month)
    if year is not None:
        query = query.filter(Salary.year == year)

    result = query.one()

    total_records = int(result.total_records or 0)
    total_employees = int(result.total_employees or 0)
    total_gross = round(float(result.total_gross_salary or 0), 2)
    total_pf = round(float(result.total_pf or 0), 2)
    total_deductions = round(float(result.total_deductions or 0), 2)
    total_ot = round(float(result.total_overtime_amount or 0), 2)
    total_net = round(float(result.total_net_salary or 0), 2)

    return {
        "month": month,
        "year": year,
        "total_records": total_records,
        "total_employees": total_employees,
        "record_count": total_records,
        "employee_count": total_employees,
        "total_gross_salary": total_gross,
        "total_pf": total_pf,
        "total_deductions": total_deductions,
        "total_overtime_amount": total_ot,
        "total_net_salary": total_net,
    }
