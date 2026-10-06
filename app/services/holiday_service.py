"""
app/services/holiday_service.py
-------------------------------
Company holiday calendar (D-034).

Two kinds of holiday, both paid non-working days:
- national: the fixed mandatory national holidays in attendance_service.COMPANY_HOLIDAYS
            (recur every year, defined in code, cannot be removed)
- company:  one-off dates HR declares (Diwali, Holi, ...) stored in the `holidays` table

Declared holidays are excluded from payroll working days (salary_service) and are not charged
against leave balances (leave_service.count_leave_days), exactly like national holidays.

This module is independent of FastAPI HTTP concerns so it can be used by routers and AI tools.
"""

from datetime import date
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database.models import Holiday
from app.services.attendance_service import COMPANY_HOLIDAYS


# ---------------------------------------------------------------------------
# Domain Exceptions
# ---------------------------------------------------------------------------

class HolidayServiceError(Exception):
    """Base exception for holiday operations."""


class HolidayNotFoundError(HolidayServiceError):
    """The holiday does not exist."""


class HolidayConflictError(HolidayServiceError):
    """The date already is a holiday (declared or national)."""


class InvalidHolidayError(HolidayServiceError):
    """The holiday is not valid (weekend, empty name)."""


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------

def get_declared_holiday_dates(
    db: Session,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> Set[date]:
    """Dates of HR-declared holidays (optionally within [start, end]) — pass as `extra_holidays`."""
    query = db.query(Holiday.holiday_date)
    if start:
        query = query.filter(Holiday.holiday_date >= start)
    if end:
        query = query.filter(Holiday.holiday_date <= end)
    return {row[0] for row in query.all()}


def national_holidays(year: int) -> List[Dict[str, Any]]:
    return [
        {"id": None, "date": date(year, month, day), "name": name, "kind": "national"}
        for (month, day), name in COMPANY_HOLIDAYS.items()
    ]


def list_holidays(db: Session, year: int) -> List[Dict[str, Any]]:
    """National + declared holidays of one calendar year, sorted by date."""
    declared = (
        db.query(Holiday)
        .filter(Holiday.holiday_date >= date(year, 1, 1), Holiday.holiday_date <= date(year, 12, 31))
        .all()
    )
    items = national_holidays(year) + [
        {"id": h.id, "date": h.holiday_date, "name": h.name, "kind": "company"} for h in declared
    ]
    for item in items:
        item["weekday"] = item["date"].strftime("%A")
    return sorted(items, key=lambda i: i["date"])


# ---------------------------------------------------------------------------
# Mutations (HR / Admin)
# ---------------------------------------------------------------------------

def create_holiday(db: Session, *, holiday_date: date, name: str, created_by: Optional[int]) -> Holiday:
    """
    Declare a company holiday.

    Raises:
        InvalidHolidayError: empty name or a Saturday/Sunday (already a non-working day).
        HolidayConflictError: the date is a national holiday or already declared.
    """
    name = (name or "").strip()
    if not name:
        raise InvalidHolidayError("Holiday name is required.")
    if holiday_date.weekday() >= 5:
        raise InvalidHolidayError("This date is a weekend — it is already a non-working day.")
    national = COMPANY_HOLIDAYS.get((holiday_date.month, holiday_date.day))
    if national:
        raise HolidayConflictError(f"{holiday_date} is already a national holiday ({national}).")
    if db.query(Holiday.id).filter(Holiday.holiday_date == holiday_date).first():
        raise HolidayConflictError(f"{holiday_date} is already a company holiday.")

    holiday = Holiday(holiday_date=holiday_date, name=name, created_by=created_by)
    db.add(holiday)
    try:
        db.commit()
    except IntegrityError as exc:  # concurrent insert of the same date
        db.rollback()
        raise HolidayConflictError(f"{holiday_date} is already a company holiday.") from exc
    db.refresh(holiday)
    return holiday


def delete_holiday(db: Session, holiday_id: int) -> None:
    """
    Remove a declared holiday. Raises HolidayNotFoundError.
    (Payroll rows already generated for that month are not recalculated automatically —
    re-run payroll generation for unpaid months.)
    """
    holiday = db.query(Holiday).filter(Holiday.id == holiday_id).first()
    if not holiday:
        raise HolidayNotFoundError("Holiday not found.")
    db.delete(holiday)
    db.commit()
