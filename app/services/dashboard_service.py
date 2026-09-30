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

from datetime import date
from typing import Any, Dict, List, Optional
from sqlalchemy import func, desc
from sqlalchemy.orm import Session

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
    }
