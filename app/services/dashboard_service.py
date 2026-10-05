"""
app/services/dashboard_service.py
---------------------------------
Business logic and analytics engine for the HR Dashboard (PRD Section 21).

Calculates:
- High-level KPIs: Total Employees, Present, Absent, On Leave, Late Count, Total Overtime.
- Department-wise attendance breakdown.
- Monthly attendance trends.
- Overtime analysis and leaderboard.
- Leave type distribution & recent applications.
"""

import calendar
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import case, func, desc
from sqlalchemy.orm import Session

from app.services import attendance_service, leave_service

from app.database.models import (
    Attendance,
    AttendanceStatus,
    Employee,
    EmployeeStatus,
    Leave,
    LeaveStatus,
    Salary,
    User,
    UserRole,
)


def get_dashboard_summary(
    db: Session,
    ref_date: Optional[date] = None,
) -> Dict[str, Any]:
    """
    Generate complete analytics summary for the HR Dashboard.

    If `ref_date` is not provided:
      1. Tries `date.today()`.
      2. If no attendance exists for today, falls back to the latest recorded
         attendance date in the database (e.g., 2024-09-30 in seed data)
         so the dashboard renders meaningful data immediately.
    """
    # 1. Determine effective reference date
    is_fallback = False
    if ref_date is None:
        today = date.today()
        today_has_records = (
            db.query(Attendance)
            .filter(Attendance.attendance_date == today)
            .first()
            is not None
        )
        if today_has_records:
            target_date = today
        else:
            latest_record = (
                db.query(Attendance.attendance_date)
                .order_by(Attendance.attendance_date.desc())
                .first()
            )
            if latest_record:
                target_date = latest_record[0]
                is_fallback = True
            else:
                target_date = today
    else:
        target_date = ref_date

    # 2. Total active employees
    total_employees = (
        db.query(Employee)
        .filter(Employee.status == EmployeeStatus.ACTIVE.value)
        .count()
    )

    # 3. Reference date attendance metrics
    day_records = (
        db.query(Attendance)
        .filter(Attendance.attendance_date == target_date)
        .all()
    )

    present_count = sum(
        1 for r in day_records if r.status in [AttendanceStatus.PRESENT.value, AttendanceStatus.HALF_DAY.value]
    )
    absent_count = sum(
        1 for r in day_records if r.status == AttendanceStatus.ABSENT.value
    )
    late_today_count = sum(
        1 for r in day_records if (r.late_minutes or 0) > 0
    )

    # Active leaves on target_date
    on_leave_count = (
        db.query(Leave)
        .filter(
            Leave.from_date <= target_date,
            Leave.to_date >= target_date,
            Leave.status == LeaveStatus.APPROVED.value,
        )
        .count()
    )

    # If day attendance records don't cover all employees, adjust absent count
    if total_employees > len(day_records) and len(day_records) > 0:
        recorded_emp_ids = {r.employee_id for r in day_records}
        unrecorded = total_employees - len(recorded_emp_ids)
        # unrecorded employees not on approved leave count towards absent
        absent_count += max(0, unrecorded - on_leave_count)

    # 4. Total Overtime Hours for the target month
    ref_month = target_date.month
    ref_year = target_date.year

    month_ot_minutes = (
        db.query(func.coalesce(func.sum(Attendance.overtime_minutes), 0))
        .filter(
            func.month(Attendance.attendance_date) == ref_month,
            func.year(Attendance.attendance_date) == ref_year,
        )
        .scalar()
    ) or 0
    total_overtime_hours = round(float(month_ot_minutes) / 60.0, 1)

    # 5. Department-wise Attendance breakdown (on target_date)
    departments = (
        db.query(Employee.department)
        .filter(Employee.status == EmployeeStatus.ACTIVE.value)
        .distinct()
        .all()
    )
    dept_names = [d[0] for d in departments]

    dept_attendance: List[Dict[str, Any]] = []
    for dept in sorted(dept_names):
        dept_emps = (
            db.query(Employee.id)
            .filter(Employee.department == dept, Employee.status == EmployeeStatus.ACTIVE.value)
            .all()
        )
        dept_emp_ids = [e[0] for e in dept_emps]
        dept_total = len(dept_emp_ids)

        dept_present = sum(
            1 for r in day_records if r.employee_id in dept_emp_ids and r.status in [AttendanceStatus.PRESENT.value, AttendanceStatus.HALF_DAY.value]
        )
        pct = round((dept_present / dept_total * 100), 1) if dept_total > 0 else 0.0

        dept_attendance.append({
            "department": dept,
            "total_employees": dept_total,
            "present": dept_present,
            "absent": max(0, dept_total - dept_present),
            "percentage": pct,
        })

    # 6. Overtime Leaderboard (Top employees with highest OT in target month)
    top_ot_query = (
        db.query(
            Employee.name,
            Employee.department,
            func.sum(Attendance.overtime_minutes).label("total_ot"),
        )
        .join(Attendance, Attendance.employee_id == Employee.id)
        .filter(
            func.month(Attendance.attendance_date) == ref_month,
            func.year(Attendance.attendance_date) == ref_year,
            Attendance.overtime_minutes > 0,
        )
        .group_by(Employee.id, Employee.name, Employee.department)
        .order_by(desc("total_ot"))
        .limit(5)
        .all()
    )

    overtime_leaders = [
        {
            "name": row[0],
            "department": row[1],
            "overtime_hours": round(float(row[2]) / 60.0, 1),
        }
        for row in top_ot_query
    ]

    # 7. Late Arrivals Leaderboard (Top employees with most late days in target month)
    late_query = (
        db.query(
            Employee.name,
            Employee.department,
            func.count(Attendance.id).label("late_count"),
            func.sum(Attendance.late_minutes).label("total_late_min"),
        )
        .join(Attendance, Attendance.employee_id == Employee.id)
        .filter(
            func.month(Attendance.attendance_date) == ref_month,
            func.year(Attendance.attendance_date) == ref_year,
            Attendance.late_minutes > 0,
        )
        .group_by(Employee.id, Employee.name, Employee.department)
        .order_by(desc("late_count"), desc("total_late_min"))
        .limit(5)
        .all()
    )

    late_leaders = [
        {
            "name": row[0],
            "department": row[1],
            "late_count": int(row[2]),
            "total_late_minutes": int(row[3] or 0),
        }
        for row in late_query
    ]

    # 8. Leave Type Distribution (Approved or Pending)
    leave_dist = (
        db.query(Leave.leave_type, func.count(Leave.id))
        .group_by(Leave.leave_type)
        .all()
    )
    leave_breakdown = [
        {"type": row[0].replace("_", " ").title(), "count": row[1]}
        for row in leave_dist
    ]

    # 9. Recent Leave Requests (Latest 5)
    recent_leaves_query = (
        db.query(Leave, Employee.name, Employee.department)
        .join(Employee, Leave.employee_id == Employee.id)
        .order_by(desc(Leave.from_date))
        .limit(5)
        .all()
    )
    recent_leaves = [
        {
            "id": l.id,
            "employee_name": emp_name,
            "department": emp_dept,
            "leave_type": l.leave_type.replace("_", " ").title(),
            "from_date": str(l.from_date),
            "to_date": str(l.to_date),
            "status": l.status.capitalize(),
            "reason": l.reason or "No reason provided",
        }
        for l, emp_name, emp_dept in recent_leaves_query
    ]

    return {
        "reference_date": str(target_date),
        "is_fallback_date": is_fallback,
        "month": target_date.strftime("%B %Y"),
        "kpis": {
            "total_employees": total_employees,
            "present_today": present_count,
            "absent_today": absent_count,
            "on_leave_today": on_leave_count,
            "late_today": late_today_count,
            "total_overtime_hours": total_overtime_hours,
        },
        "department_attendance": dept_attendance,
        "overtime_leaders": overtime_leaders,
        "late_leaders": late_leaders,
        "leave_breakdown": leave_breakdown,
        "recent_leaves": recent_leaves,
        "monthly_attendance": get_monthly_attendance_trend(db, target_date),
    }


# ---------------------------------------------------------------------------
# Monthly Attendance Trend (PRD §21 chart: "Monthly attendance")
# ---------------------------------------------------------------------------

def get_monthly_attendance_trend(
    db: Session,
    ref_date: date,
    months: int = 6,
    scope_ids: Optional[Set[int]] = None,
) -> List[Dict[str, Any]]:
    """
    Status counts per month for the `months` months ending at `ref_date`'s month
    (only months that have data are returned).

    attendance_rate = (present + 0.5 * half_day) / (present + half_day + absent) * 100
    """
    start_year, start_month = ref_date.year, ref_date.month - (months - 1)
    while start_month <= 0:
        start_month += 12
        start_year -= 1
    start = date(start_year, start_month, 1)
    end_month_last_day = calendar.monthrange(ref_date.year, ref_date.month)[1]
    end = date(ref_date.year, ref_date.month, end_month_last_day)

    query = db.query(
        func.year(Attendance.attendance_date).label("y"),
        func.month(Attendance.attendance_date).label("m"),
        Attendance.status,
        func.count(Attendance.id),
        func.sum(case((Attendance.late_minutes > 0, 1), else_=0)),
    ).filter(Attendance.attendance_date >= start, Attendance.attendance_date <= end)
    if scope_ids is not None:
        query = query.filter(Attendance.employee_id.in_(scope_ids or {-1}))
    rows = query.group_by("y", "m", Attendance.status).all()

    buckets: Dict[Tuple[int, int], Dict[str, Any]] = {}
    for y, m, att_status, count, late in rows:
        bucket = buckets.setdefault(
            (int(y), int(m)),
            {"present": 0, "absent": 0, "half_day": 0, "leave": 0, "late": 0},
        )
        if att_status in bucket:
            bucket[att_status] += int(count)
        bucket["late"] += int(late or 0)

    trend = []
    for (y, m) in sorted(buckets):
        b = buckets[(y, m)]
        worked_basis = b["present"] + b["half_day"] + b["absent"]
        rate = ((b["present"] + 0.5 * b["half_day"]) / worked_basis * 100) if worked_basis else 0.0
        trend.append({
            "month": f"{y}-{m:02d}",
            "label": date(y, m, 1).strftime("%b %Y"),
            "present": b["present"],
            "absent": b["absent"],
            "late": b["late"],
            "half_day": b["half_day"],
            "leave": b["leave"],
            "attendance_rate": round(rate, 1),
        })
    return trend


# ---------------------------------------------------------------------------
# Personal / Team Dashboard (any role)
# ---------------------------------------------------------------------------

def get_my_dashboard(db: Session, current_user: User, ref_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Personal overview for the logged-in user:
      - today's attendance record
      - attendance stats for the reference month (latest month with own data if none this month)
      - leave balance (calendar year of the reference month)
      - latest salary slip
      - for managers: team snapshot (direct reports)
    """
    employee = current_user.employee
    today = date.today()
    if employee is None:
        return {"employee": None, "month_label": today.strftime("%B %Y"), "today": None,
                "attendance": None, "leave_balance": [], "latest_salary": None, "team": None}

    # Reference month: current month if it has own data, else the latest month with own data
    if ref_date is None:
        latest_own = (
            db.query(func.max(Attendance.attendance_date))
            .filter(Attendance.employee_id == employee.id)
            .scalar()
        )
        has_this_month = latest_own is not None and latest_own.year == today.year and latest_own.month == today.month
        ref_date = today if (has_this_month or latest_own is None) else latest_own
    month_start = ref_date.replace(day=1)
    month_end = ref_date.replace(day=calendar.monthrange(ref_date.year, ref_date.month)[1])

    summary = attendance_service.get_attendance_summary(db, employee.id, month_start, month_end)
    basis = summary["present_days"] + summary["half_day_days"] + summary["absent_days"]
    attendance_pct = (
        round((summary["present_days"] + 0.5 * summary["half_day_days"]) / basis * 100, 1) if basis else 0.0
    )

    today_record = attendance_service.get_attendance_by_date(db, employee_id=employee.id, attendance_date=today)

    latest_salary = (
        db.query(Salary)
        .filter(Salary.employee_id == employee.id)
        .order_by(Salary.year.desc(), Salary.month.desc())
        .first()
    )

    team = None
    if current_user.role == UserRole.MANAGER.value:
        members = (
            db.query(Employee)
            .filter(Employee.manager_id == employee.id, Employee.status == EmployeeStatus.ACTIVE.value)
            .order_by(Employee.name.asc())
            .all()
        )
        member_ids = [m.id for m in members]
        team_day = get_latest_team_day(db, member_ids)
        day_records = {
            r.employee_id: r
            for r in db.query(Attendance).filter(
                Attendance.attendance_date == team_day, Attendance.employee_id.in_(member_ids or [-1])
            ).all()
        } if team_day else {}
        on_leave = (
            db.query(Leave)
            .filter(
                Leave.employee_id.in_(member_ids or [-1]),
                Leave.status == LeaveStatus.APPROVED.value,
                Leave.from_date <= (team_day or today),
                Leave.to_date >= (team_day or today),
            )
            .count()
        )
        pending = (
            db.query(Leave)
            .filter(Leave.employee_id.in_(member_ids or [-1]), Leave.status == LeaveStatus.PENDING.value)
            .count()
        )
        team = {
            "size": len(members),
            "reference_date": str(team_day) if team_day else None,
            "present_today": sum(
                1 for r in day_records.values()
                if r.status in (AttendanceStatus.PRESENT.value, AttendanceStatus.HALF_DAY.value)
            ),
            "on_leave_today": on_leave,
            "pending_leaves": pending,
            "members": [
                {
                    "id": m.id,
                    "name": m.name,
                    "designation": m.designation,
                    "today_status": day_records[m.id].status if m.id in day_records else "not_marked",
                }
                for m in members
            ],
        }

    return {
        "employee": {
            "id": employee.id,
            "employee_code": employee.employee_code,
            "name": employee.name,
            "department": employee.department,
            "designation": employee.designation,
        },
        "month_label": ref_date.strftime("%B %Y"),
        "today": {
            "status": today_record.status,
            "in_time": str(today_record.in_time) if today_record.in_time else None,
            "out_time": str(today_record.out_time) if today_record.out_time else None,
        } if today_record else None,
        "attendance": {
            "present_days": summary["present_days"],
            "absent_days": summary["absent_days"],
            "late_days": summary["late_days"],
            "half_day_days": summary["half_day_days"],
            "leave_days": summary["leave_days"],
            "total_working_minutes": summary["total_working_minutes"],
            "total_overtime_minutes": summary["total_overtime_minutes"],
            "attendance_percentage": attendance_pct,
        },
        "leave_balance": leave_service.get_leave_balance(db, employee.id, ref_date.year),
        "latest_salary": {
            "month": latest_salary.month,
            "year": latest_salary.year,
            "gross_salary": float(latest_salary.gross_salary),
            "net_salary": float(latest_salary.net_salary),
            "pf": float(latest_salary.pf),
            "deductions": float(latest_salary.deductions),
            "overtime_amount": float(latest_salary.overtime_amount),
        } if latest_salary else None,
        "team": team,
    }


def get_latest_team_day(db: Session, member_ids: List[int]) -> Optional[date]:
    """Today if the team has records today, else the latest date with team records."""
    if not member_ids:
        return None
    today = date.today()
    has_today = (
        db.query(Attendance.id)
        .filter(Attendance.attendance_date == today, Attendance.employee_id.in_(member_ids))
        .first()
    )
    if has_today:
        return today
    return (
        db.query(func.max(Attendance.attendance_date))
        .filter(Attendance.employee_id.in_(member_ids))
        .scalar()
    )
