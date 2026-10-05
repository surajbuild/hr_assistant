"""
scripts/generate_demo_month.py
------------------------------
Generate realistic demo attendance (and a few leave requests) for the CURRENT
month so the dashboard, daily sheet and "this month" AI questions have live
data (KNOWN_ISSUES KI-001). The Aug–Sep 2024 seed data is never touched.

Properties
- Idempotent: existing (employee, date) attendance rows are skipped, and a leave
  is only created when the employee has no overlapping leave already. Re-running
  the script is safe and adds nothing new.
- Deterministic: values are derived from a hash of (employee code, date), so a
  re-run after deleting a row recreates the same row.
- Uses the Python calculation engine (attendance_service.calculate_day_metrics)
  for late / working / overtime minutes — no hard-coded numbers.
- Weekends -> status "weekend"; fixed public holidays -> "holiday";
  approved leave days -> "leave"; today (before 18:00) -> checked in, not out.

Usage:
    python scripts/generate_demo_month.py                 # current month, up to today
    python scripts/generate_demo_month.py --month 2026-09 # a whole past month
    python scripts/generate_demo_month.py --dry-run       # show what would be created
"""

import argparse
import calendar
import hashlib
import os
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from app.database.connection import SessionLocal  # noqa: E402
from app.database.models import (  # noqa: E402
    Attendance,
    AttendanceStatus,
    Employee,
    EmployeeStatus,
    Leave,
    LeaveStatus,
    User,
    UserRole,
)
from app.services.attendance_service import (  # noqa: E402
    COMPANY_HOLIDAYS as PUBLIC_HOLIDAYS,
    HALF_DAY_THRESHOLD_MINUTES,
    calculate_day_metrics,
)

# Leave requests to create: (employee index in name order, type, working-day index, length, status, reason)
#   APPROVED leaves use working days already in the past (index 0 = most recent past working day);
#   PENDING / REJECTED leaves use upcoming working days (index 0 = next working day after today).
#   Entries that do not fit the month are skipped.
LEAVE_PLAN = [
    (0, "casual", 0, 1, LeaveStatus.APPROVED.value, "Family function"),
    (1, "sick", 3, 2, LeaveStatus.APPROVED.value, "Fever and cold"),
    (2, "earned", 6, 3, LeaveStatus.PENDING.value, "Short vacation"),
    (3, "casual", 2, 1, LeaveStatus.REJECTED.value, "Personal work during release week"),
    (4, "casual", 9, 1, LeaveStatus.PENDING.value, "Bank and documentation work"),
]


def _rand(code: str, day: date, salt: str = "") -> float:
    """Deterministic pseudo-random number in [0, 1) for (employee, day)."""
    digest = hashlib.sha256(f"{code}|{day.isoformat()}|{salt}".encode()).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _clock(minutes_after_midnight: int) -> time:
    return time(minutes_after_midnight // 60, minutes_after_midnight % 60)


def working_days(first: date, last: date):
    d = first
    while d <= last:
        if d.weekday() < 5 and (d.month, d.day) not in PUBLIC_HOLIDAYS:
            yield d
        d += timedelta(days=1)


def plan_day(code: str, day: date, now: datetime):
    """Return attendance kwargs for one employee-day (without employee_id)."""
    if day.weekday() >= 5:
        return {"status": AttendanceStatus.WEEKEND.value}
    if (day.month, day.day) in PUBLIC_HOLIDAYS:
        return {"status": AttendanceStatus.HOLIDAY.value}

    r = _rand(code, day)
    if r < 0.03:
        return {"status": AttendanceStatus.ABSENT.value}

    # arrival: mostly 08:50–09:12, ~12 % late (09:18–09:50)
    if r < 0.15:
        arrive = 9 * 60 + 18 + int(_rand(code, day, "late") * 32)
    else:
        arrive = 8 * 60 + 50 + int(_rand(code, day, "in") * 22)
    in_time = _clock(arrive)

    if day == now.date() and now.time() < time(18, 0):
        # Today, during working hours: checked in, not yet checked out
        if now.time() < in_time:
            return None  # has not arrived yet
        return {
            "status": AttendanceStatus.PRESENT.value,
            "in_time": in_time,
            "out_time": None,
            "working_minutes": 0,
            "late_minutes": calculate_day_metrics(in_time, in_time)["late_minutes"],
            "overtime_minutes": 0,
        }

    roll = _rand(code, day, "out")
    if roll < 0.04:
        leave_at = 13 * 60 + 15 + int(_rand(code, day, "half") * 30)            # half day
    elif roll < 0.22:
        leave_at = arrive + 9 * 60 + 30 + int(_rand(code, day, "ot") * 120)     # overtime: 30–150 min
    else:
        leave_at = arrive + 9 * 60 - int(_rand(code, day, "norm") * 12)         # ~8h worked, no OT
    out_time = _clock(leave_at)
    m = calculate_day_metrics(in_time, out_time)
    status = (
        AttendanceStatus.HALF_DAY.value if m["working_minutes"] < HALF_DAY_THRESHOLD_MINUTES else AttendanceStatus.PRESENT.value
    )
    return {"status": status, "in_time": in_time, "out_time": out_time, **m}


def approver_user_id(db, employee: Employee):
    if employee.manager and employee.manager.user:
        return employee.manager.user.id
    hr = db.query(User).filter(User.role == UserRole.HR.value, User.status == "active").order_by(User.id).first()
    return hr.id if hr else None


def generate(month: str = None, dry_run: bool = False) -> dict:
    now = datetime.now()
    if month:
        year, mon = (int(x) for x in month.split("-"))
    else:
        year, mon = now.year, now.month
    first = date(year, mon, 1)
    last = min(date(year, mon, calendar.monthrange(year, mon)[1]), now.date())
    if first > now.date():
        raise SystemExit("Refusing to generate attendance for a future month.")

    db = SessionLocal()
    created = {"attendance": 0, "skipped_existing": 0, "leaves": 0, "leaves_skipped": 0}
    try:
        employees = (
            db.query(Employee).filter(Employee.status == EmployeeStatus.ACTIVE.value).order_by(Employee.name).all()
        )

        # 1. Leave requests (before attendance, so approved leave days become "leave")
        month_last = date(year, mon, calendar.monthrange(year, mon)[1])
        all_wdays = list(working_days(first, month_last))
        past = [d for d in all_wdays if d < now.date()][::-1]       # most recent first
        future = [d for d in all_wdays if d > now.date()]
        for idx, leave_type, offset, length, status, reason in LEAVE_PLAN:
            pool = past if status == LeaveStatus.APPROVED.value else future
            if idx >= len(employees) or offset + length > len(pool):
                continue
            emp = employees[idx]
            days = sorted(pool[offset: offset + length])
            start, end = days[0], days[-1]
            overlap = (
                db.query(Leave)
                .filter(Leave.employee_id == emp.id, Leave.from_date <= end, Leave.to_date >= start)
                .first()
            )
            if overlap:
                created["leaves_skipped"] += 1
                continue
            created["leaves"] += 1
            if not dry_run:
                db.add(
                    Leave(
                        employee_id=emp.id,
                        leave_type=leave_type,
                        from_date=start,
                        to_date=end,
                        status=status,
                        reason=reason,
                        approved_by=approver_user_id(db, emp) if status in (LeaveStatus.APPROVED.value, LeaveStatus.REJECTED.value) else None,
                    )
                )
        if not dry_run:
            db.commit()

        approved = {}
        for lv in db.query(Leave).filter(
            Leave.status == LeaveStatus.APPROVED.value, Leave.from_date <= last, Leave.to_date >= first
        ):
            d = max(lv.from_date, first)
            while d <= min(lv.to_date, last):
                approved[(lv.employee_id, d)] = True
                d += timedelta(days=1)

        # 2. Attendance
        existing = {
            (a.employee_id, a.attendance_date)
            for a in db.query(Attendance.employee_id, Attendance.attendance_date).filter(
                Attendance.attendance_date >= first, Attendance.attendance_date <= last
            )
        }
        day = first
        while day <= last:
            for emp in employees:
                if day < emp.joining_date:
                    continue
                if (emp.id, day) in existing:
                    created["skipped_existing"] += 1
                    continue
                if (emp.id, day) in approved and day.weekday() < 5:
                    plan = {"status": AttendanceStatus.LEAVE.value}
                else:
                    plan = plan_day(emp.employee_code, day, now)
                if plan is None:
                    continue
                created["attendance"] += 1
                if not dry_run:
                    db.add(
                        Attendance(
                            employee_id=emp.id,
                            attendance_date=day,
                            in_time=plan.get("in_time"),
                            out_time=plan.get("out_time"),
                            working_minutes=plan.get("working_minutes", 0),
                            status=plan["status"],
                            late_minutes=plan.get("late_minutes", 0),
                            overtime_minutes=plan.get("overtime_minutes", 0),
                        )
                    )
            day += timedelta(days=1)
        if not dry_run:
            db.commit()
    finally:
        db.close()

    created["period"] = f"{first} to {last}"
    created["employees"] = len(employees)
    return created


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--month", help="YYYY-MM (default: current month)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    result = generate(args.month, args.dry_run)
    prefix = "[dry-run] would create" if args.dry_run else "Created"
    print(
        f"{prefix} {result['attendance']} attendance rows and {result['leaves']} leave requests "
        f"for {result['employees']} active employees ({result['period']}); "
        f"skipped {result['skipped_existing']} existing attendance rows and {result['leaves_skipped']} overlapping leaves."
    )
