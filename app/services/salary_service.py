"""
app/services/salary_service.py
------------------------------
Service layer for salary management business logic and database operations.

Contains reusable Python functions for:
- Retrieving salary records for the authenticated employee (with strict data isolation)
- Retrieving salary records for a specific employee (with employee existence validation)
- Retrieving salary records for a specific month and year
- Payroll register for a month
- Payroll engine: generate_payroll() computes monthly salary rows from the salary
  structure (employees.monthly_gross_salary), attendance and leave (D-021)
- Overtime pay rates shared with the overtime Excel report (KI-015)

This module is independent of FastAPI HTTP concerns (no Request, HTTPException,
or status codes) so that it can be safely invoked by both API routers and AI/tool agents.
"""

import calendar
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from sqlalchemy import distinct, func
from sqlalchemy.orm import Session

from app.database.models import (
    Attendance,
    AttendanceStatus,
    Employee,
    EmployeeStatus,
    Leave,
    LeaveStatus,
    LeaveType,
    Salary,
)
from app.services.attendance_service import STANDARD_WORKING_MINUTES, working_days_between
from app.services.holiday_service import get_declared_holiday_dates

# ---------------------------------------------------------------------------
# Payroll rules (PROJECT_DECISIONS.md D-021 — the PRD is silent on formulas)
# ---------------------------------------------------------------------------

BASIC_SHARE_OF_GROSS = 0.35      # basic pay = 35 % of monthly gross
PF_RATE_OF_BASIC = 0.12          # employee PF = 12 % of earned basic
OVERTIME_MULTIPLIER = 1.5        # overtime paid at 1.5x the normal hourly rate
HOURS_PER_WORKING_DAY = STANDARD_WORKING_MINUTES / 60   # 8 h


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


class PayrollPeriodError(SalaryServiceError):
    """Raised when payroll is requested for an invalid or future period."""
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


# ---------------------------------------------------------------------------
# Payroll Sheet
# ---------------------------------------------------------------------------

def get_latest_payroll_period(db: Session) -> Optional[Tuple[int, int]]:
    """(month, year) of the most recent salary records, or None if there are none."""
    row = db.query(Salary.year, Salary.month).order_by(Salary.year.desc(), Salary.month.desc()).first()
    return (row[1], row[0]) if row else None


def get_payroll_periods(db: Session) -> List[Tuple[int, int]]:
    """Sorted (year, month) pairs that have salary records."""
    return sorted((int(y), int(m)) for y, m in db.query(Salary.year, Salary.month).distinct().all())


def list_payroll(
    db: Session,
    month: Optional[int] = None,
    year: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Salary sheet for one month joined with employee info.
    Defaults to the latest month that has salary records.

    Raises:
        InvalidSalaryFilterError: invalid month/year.
    """
    if month is not None and not 1 <= month <= 12:
        raise InvalidSalaryFilterError("Month must be an integer between 1 and 12.")
    if month is None or year is None:
        latest = get_latest_payroll_period(db)
        if latest:
            month = month or latest[0]
            year = year or latest[1]
    if month is None or year is None:
        return {"month": month, "year": year, "items": []}

    rows = (
        db.query(Salary, Employee)
        .join(Employee, Employee.id == Salary.employee_id)
        .filter(Salary.month == month, Salary.year == year)
        .order_by(Employee.name.asc())
        .all()
    )
    items = [
        {
            "id": sal.id,
            "employee_id": emp.id,
            "employee_name": emp.name,
            "employee_code": emp.employee_code,
            "department": emp.department,
            "designation": emp.designation,
            "month": sal.month,
            "year": sal.year,
            "gross_salary": float(sal.gross_salary),
            "pf": float(sal.pf),
            "deductions": float(sal.deductions),
            "overtime_amount": float(sal.overtime_amount),
            "net_salary": float(sal.net_salary),
            "paid_at": sal.paid_at,
        }
        for sal, emp in rows
    ]
    return {"month": month, "year": year, "items": items}



# ---------------------------------------------------------------------------
# Mark as paid (locks the row, D-021 / D-036)
# ---------------------------------------------------------------------------

def mark_paid(
    db: Session,
    salary_ids: Iterable[int],
    paid_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Set paid_at on unpaid salary rows. Paid rows are locked: the payroll engine skips them and
    attendance for that month can no longer be corrected. There is no "unpay" (D-036).

    Returns {"marked": [ids], "already_paid": [ids], "not_found": [ids], "paid_at": datetime}.
    """
    ids = list(dict.fromkeys(int(i) for i in salary_ids))
    paid_at = paid_at or datetime.now().replace(microsecond=0)
    rows = {s.id: s for s in db.query(Salary).filter(Salary.id.in_(ids or [-1])).all()}
    marked, already_paid, not_found = [], [], []
    for sid in ids:
        row = rows.get(sid)
        if row is None:
            not_found.append(sid)
        elif row.paid_at is not None:
            already_paid.append(sid)
        else:
            row.paid_at = paid_at
            marked.append(sid)
    db.commit()
    return {"marked": marked, "already_paid": already_paid, "not_found": not_found, "paid_at": paid_at}


# ---------------------------------------------------------------------------
# Payroll Engine (D-021)
# ---------------------------------------------------------------------------

def _money(value: float) -> float:
    return round(float(value) + 1e-9, 2)


def month_bounds(month: int, year: int) -> Tuple[date, date]:
    if not 1 <= month <= 12:
        raise PayrollPeriodError("Month must be between 1 and 12.")
    if year < 2000 or year > 2100:
        raise PayrollPeriodError("Year must be between 2000 and 2100.")
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def get_monthly_gross(db: Session, employee: Employee) -> Optional[float]:
    """Salary structure: employees.monthly_gross_salary, else the latest salary row's gross."""
    if employee.monthly_gross_salary is not None:
        return float(employee.monthly_gross_salary)
    latest = (
        db.query(Salary)
        .filter(Salary.employee_id == employee.id)
        .order_by(Salary.year.desc(), Salary.month.desc())
        .first()
    )
    return float(latest.gross_salary) if latest else None


def overtime_hourly_rate(
    monthly_gross: float, month: int, year: int, extra_holidays: Optional[Set[date]] = None
) -> float:
    """Overtime pay per hour = gross / (working days x 8 h) x 1.5 (pass declared holidays as `extra_holidays`)."""
    first, last = month_bounds(month, year)
    working_days = len(working_days_between(first, last, extra_holidays)) or 1
    return monthly_gross / (working_days * HOURS_PER_WORKING_DAY) * OVERTIME_MULTIPLIER


def calculate_payroll(db: Session, employee: Employee, month: int, year: int) -> Optional[Dict[str, Any]]:
    """
    Compute one employee's salary for a month (pure calculation, nothing is saved).

    Returns None when the employee has no salary structure.

        working_days    = Mon-Fri minus national + declared company holidays (D-034)
        per_day         = gross / working_days
        LOP days        = absent days + 0.5 x half days + approved unpaid-leave working days
                          not already marked absent / half day (days without any attendance
                          record are NOT deducted)
        lop_deduction   = per_day x LOP days
        earned basic    = gross x 35 % x (working_days - LOP days) / working_days
        pf              = 12 % x earned basic
        overtime_amount = overtime minutes / 60 x (gross / (working_days x 8)) x 1.5
        net             = gross + overtime_amount - pf - lop_deduction
    """
    gross = get_monthly_gross(db, employee)
    if gross is None:
        return None
    first, last = month_bounds(month, year)
    holidays = get_declared_holiday_dates(db, first, last)
    working = working_days_between(first, last, holidays)
    working_set = set(working)
    working_days = len(working)

    records = (
        db.query(Attendance)
        .filter(
            Attendance.employee_id == employee.id,
            Attendance.attendance_date >= first,
            Attendance.attendance_date <= last,
        )
        .all()
    )
    by_day = {r.attendance_date: r for r in records}
    absent_days = sum(
        1 for r in records if r.status == AttendanceStatus.ABSENT.value and r.attendance_date in working_set
    )
    half_days = sum(
        1 for r in records if r.status == AttendanceStatus.HALF_DAY.value and r.attendance_date in working_set
    )
    overtime_minutes = sum(r.overtime_minutes or 0 for r in records)

    unpaid_days = 0
    unpaid_leaves = (
        db.query(Leave)
        .filter(
            Leave.employee_id == employee.id,
            Leave.leave_type == LeaveType.UNPAID.value,
            Leave.status == LeaveStatus.APPROVED.value,
            Leave.from_date <= last,
            Leave.to_date >= first,
        )
        .all()
    )
    for lv in unpaid_leaves:
        for day in working_days_between(max(lv.from_date, first), min(lv.to_date, last), holidays):
            rec = by_day.get(day)
            if rec is None or rec.status not in (AttendanceStatus.ABSENT.value, AttendanceStatus.HALF_DAY.value):
                unpaid_days += 1

    lop_days = min(absent_days + 0.5 * half_days + unpaid_days, working_days)
    per_day = gross / working_days if working_days else 0.0
    lop_deduction = _money(per_day * lop_days)
    paid_days = working_days - lop_days
    earned_basic = gross * BASIC_SHARE_OF_GROSS * (paid_days / working_days if working_days else 0)
    pf = _money(earned_basic * PF_RATE_OF_BASIC)
    overtime_amount = _money(overtime_minutes / 60 * overtime_hourly_rate(gross, month, year, holidays))
    net = _money(gross + overtime_amount - pf - lop_deduction)

    return {
        "employee_id": employee.id,
        "employee_name": employee.name,
        "employee_code": employee.employee_code,
        "department": employee.department,
        "month": month,
        "year": year,
        "gross_salary": _money(gross),
        "working_days": working_days,
        "paid_days": round(paid_days, 2),
        "absent_days": absent_days,
        "half_days": half_days,
        "unpaid_leave_days": unpaid_days,
        "lop_days": round(lop_days, 2),
        "lop_deduction": lop_deduction,
        "pf": pf,
        "overtime_minutes": overtime_minutes,
        "overtime_amount": overtime_amount,
        "deductions": lop_deduction,
        "net_salary": net,
    }


def generate_payroll(
    db: Session,
    month: int,
    year: int,
    employee_ids: Optional[Iterable[int]] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Create or update salary rows for a month. Idempotent per (employee, month, year):
    an existing unpaid row is updated in place, a row with paid_at set is locked and
    skipped, and a new row is created otherwise — never duplicated.

    Covers active employees (or exactly the given `employee_ids`). Future months are
    rejected; the current month is allowed but flagged `provisional`.

    Raises:
        PayrollPeriodError: invalid or future period.
    """
    first, last = month_bounds(month, year)
    today = today or date.today()
    if first > today:
        raise PayrollPeriodError("Payroll cannot be generated for a future month.")
    provisional = last >= today

    query = db.query(Employee)
    if employee_ids is not None:
        query = query.filter(Employee.id.in_(list(employee_ids) or [-1]))
    else:
        query = query.filter(Employee.status == EmployeeStatus.ACTIVE.value)
    employees = query.order_by(Employee.name.asc()).all()

    created, updated, skipped, items = 0, 0, [], []
    for emp in employees:
        if emp.joining_date and emp.joining_date > last:
            skipped.append({"employee_id": emp.id, "employee_name": emp.name, "reason": "Joined after this month."})
            continue
        calc = calculate_payroll(db, emp, month, year)
        if calc is None:
            skipped.append({
                "employee_id": emp.id,
                "employee_name": emp.name,
                "reason": "No salary structure (set the monthly gross salary on the employee).",
            })
            continue
        existing = (
            db.query(Salary)
            .filter(Salary.employee_id == emp.id, Salary.month == month, Salary.year == year)
            .first()
        )
        if existing and existing.paid_at is not None:
            skipped.append({
                "employee_id": emp.id,
                "employee_name": emp.name,
                "reason": f"Already paid on {existing.paid_at.date()} - locked.",
            })
            continue
        values = {
            "gross_salary": calc["gross_salary"],
            "pf": calc["pf"],
            "deductions": calc["deductions"],
            "overtime_amount": calc["overtime_amount"],
            "net_salary": calc["net_salary"],
        }
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
            updated += 1
            calc["action"] = "updated"
        else:
            db.add(Salary(employee_id=emp.id, month=month, year=year, paid_at=None, **values))
            created += 1
            calc["action"] = "created"
        items.append(calc)

    db.commit()
    return {
        "month": month,
        "year": year,
        "working_days": len(working_days_between(first, last, get_declared_holiday_dates(db, first, last))),
        "provisional": provisional,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "items": items,
    }
