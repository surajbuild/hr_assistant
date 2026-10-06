"""
app/services/report_service.py
------------------------------
Excel report generation service using openpyxl (PRD Section 22).

Generates:
1. Attendance Report (.xlsx):
   - Employee name, department, date, status, check-in, check-out, working minutes, overtime.
2. Overtime Report (.xlsx):
   - Employee name, department, date/month, overtime minutes, overtime hours, summary totals.
3. Leave Report (.xlsx):
   - Employee, leave type, from/to, leave days (working days), status, reason.

Attendance and Overtime workbooks open on a "Summary" sheet with exactly the
PRD §22 columns (Attendance: Employee/Present/Absent/Half Day/Late Count/
Working Minutes/OT Minutes; Overtime: Employee/Department/OT Hours/OT Amount),
followed by the detailed daily records sheet. OT Amount is computed per record
with the payroll engine's overtime rate, so partial-month ranges are exact.
"""

import io
from datetime import date
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database.models import Attendance, Employee, Leave


# ── Styling Helpers ────────────────────────────────────────────────────────────

HEADER_FILL = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")  # Navy Blue
HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
TITLE_FONT = Font(name="Calibri", size=15, bold=True, color="1E3A8A")
SUBTITLE_FONT = Font(name="Calibri", size=10, italic=True, color="6B7280")
TOTAL_FILL = PatternFill(start_color="F3F4F6", end_color="F3F4F6", fill_type="solid")
TOTAL_FONT = Font(name="Calibri", size=11, bold=True, color="111827")

THIN_BORDER = Border(
    left=Side(style="thin", color="E5E7EB"),
    right=Side(style="thin", color="E5E7EB"),
    top=Side(style="thin", color="E5E7EB"),
    bottom=Side(style="thin", color="E5E7EB"),
)


def _autofit_columns(ws, min_width=12):
    """Auto-adjust worksheet column widths based on contents."""
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            # Skip title row from calculation to prevent excessively wide first column
            if cell.row in [1, 2]:
                continue
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, min_width)


# ---------------------------------------------------------------------------
# 1. Attendance Report
# ---------------------------------------------------------------------------

def generate_attendance_report(
    db: Session,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    department: Optional[str] = None,
) -> io.BytesIO:
    """
    Generate professional Excel attendance report from database.

    Returns:
        io.BytesIO: In-memory stream containing the .xlsx workbook bytes.
    """
    query = (
        db.query(Attendance, Employee)
        .join(Employee, Attendance.employee_id == Employee.id)
    )

    if date_from:
        query = query.filter(Attendance.attendance_date >= date_from)
    if date_to:
        query = query.filter(Attendance.attendance_date <= date_to)
    if department:
        query = query.filter(Employee.department == department)

    records = query.order_by(Attendance.attendance_date.desc(), Employee.name.asc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Attendance Records"
    ws.views.sheetView[0].showGridLines = True

    # 1. Title & Meta header
    ws.append(["AI HR Assistant — Company Attendance Report"])
    ws["A1"].font = TITLE_FONT

    date_range_str = "All Recorded Dates"
    if date_from and date_to:
        date_range_str = f"{date_from} to {date_to}"
    elif date_from:
        date_range_str = f"From {date_from}"
    elif date_to:
        date_range_str = f"Up to {date_to}"

    ws.append([f"Period: {date_range_str} | Total Records: {len(records)}"])
    ws["A2"].font = SUBTITLE_FONT
    ws.append([])  # Spacer

    # 2. Table Headers
    headers = [
        "Employee Code",
        "Employee Name",
        "Department",
        "Designation",
        "Date",
        "Status",
        "Check-In",
        "Check-Out",
        "Worked (Mins)",
        "Late (Mins)",
        "Overtime (Mins)",
        "Overtime (Hours)",
    ]
    ws.append(headers)
    header_row_idx = 4

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row_idx, column=col_idx)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # 3. Data Rows
    current_row = header_row_idx + 1
    for att, emp in records:
        in_time_str = att.in_time.strftime("%H:%M") if att.in_time else "—"
        out_time_str = att.out_time.strftime("%H:%M") if att.out_time else "—"
        ot_hours = round(float(att.overtime_minutes or 0) / 60.0, 2)

        row_data = [
            emp.employee_code,
            emp.name,
            emp.department,
            emp.designation,
            str(att.attendance_date),
            att.status.capitalize(),
            in_time_str,
            out_time_str,
            att.working_minutes or 0,
            att.late_minutes or 0,
            att.overtime_minutes or 0,
            ot_hours,
        ]
        ws.append(row_data)

        # Apply cell borders & alignments
        for col_idx in range(1, len(row_data) + 1):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.border = THIN_BORDER
            if col_idx in [5, 6, 7, 8]:  # Date, Status, Check-In, Check-Out
                cell.alignment = Alignment(horizontal="center")
            elif col_idx >= 9:  # Numeric metrics
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.alignment = Alignment(horizontal="left")

        current_row += 1

    _autofit_columns(ws)
    _add_attendance_summary_sheet(wb, records, date_range_str)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


# ---------------------------------------------------------------------------
# 2. Overtime Report
# ---------------------------------------------------------------------------

def generate_overtime_report(
    db: Session,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    department: Optional[str] = None,
) -> io.BytesIO:
    """
    Generate professional Excel overtime report from database.

    Filters records where overtime_minutes > 0.

    Returns:
        io.BytesIO: In-memory stream containing the .xlsx workbook bytes.
    """
    query = (
        db.query(Attendance, Employee)
        .join(Employee, Attendance.employee_id == Employee.id)
        .filter(Attendance.overtime_minutes > 0)
    )

    if date_from:
        query = query.filter(Attendance.attendance_date >= date_from)
    if date_to:
        query = query.filter(Attendance.attendance_date <= date_to)
    if department:
        query = query.filter(Employee.department == department)

    records = query.order_by(Attendance.attendance_date.desc(), Attendance.overtime_minutes.desc()).all()

    wb = Workbook()
    ws = wb.active
    ws.title = "Overtime Records"
    ws.views.sheetView[0].showGridLines = True

    # 1. Title & Meta header
    ws.append(["AI HR Assistant — Employee Overtime Report"])
    ws["A1"].font = TITLE_FONT

    date_range_str = "All Recorded Dates"
    if date_from and date_to:
        date_range_str = f"{date_from} to {date_to}"
    elif date_from:
        date_range_str = f"From {date_from}"
    elif date_to:
        date_range_str = f"Up to {date_to}"

    total_ot_mins = sum((r[0].overtime_minutes or 0) for r in records)
    total_ot_hours = round(float(total_ot_mins) / 60.0, 2)

    ws.append([f"Period: {date_range_str} | Overtime Sessions: {len(records)} | Total Overtime: {total_ot_hours} hrs"])
    ws["A2"].font = SUBTITLE_FONT
    ws.append([])  # Spacer

    # 2. Table Headers
    headers = [
        "Employee Code",
        "Employee Name",
        "Department",
        "Designation",
        "Date",
        "Check-In",
        "Check-Out",
        "Working Minutes",
        "Overtime (Minutes)",
        "Overtime (Hours)",
    ]
    ws.append(headers)
    header_row_idx = 4

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row_idx, column=col_idx)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # 3. Data Rows
    current_row = header_row_idx + 1
    for att, emp in records:
        in_time_str = att.in_time.strftime("%H:%M") if att.in_time else "—"
        out_time_str = att.out_time.strftime("%H:%M") if att.out_time else "—"
        ot_hours = round(float(att.overtime_minutes or 0) / 60.0, 2)

        row_data = [
            emp.employee_code,
            emp.name,
            emp.department,
            emp.designation,
            str(att.attendance_date),
            in_time_str,
            out_time_str,
            att.working_minutes or 0,
            att.overtime_minutes or 0,
            ot_hours,
        ]
        ws.append(row_data)

        for col_idx in range(1, len(row_data) + 1):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.border = THIN_BORDER
            if col_idx in [5, 6, 7]:
                cell.alignment = Alignment(horizontal="center")
            elif col_idx >= 8:
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.alignment = Alignment(horizontal="left")

        current_row += 1

    # 4. Total Summary Row
    if records:
        summary_row = [
            "Total",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            total_ot_mins,
            total_ot_hours,
        ]
        ws.append(summary_row)
        for col_idx in range(1, len(summary_row) + 1):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.fill = TOTAL_FILL
            cell.font = TOTAL_FONT
            cell.border = THIN_BORDER
            if col_idx >= 8:
                cell.alignment = Alignment(horizontal="right")

    _autofit_columns(ws)
    _add_overtime_summary_sheet(db, wb, records, date_range_str, date_from, date_to)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer



# ---------------------------------------------------------------------------
# Shared table writer
# ---------------------------------------------------------------------------

def _write_table(ws, title: str, subtitle: str, headers, rows, total_row=None, numeric_from: int = 3):
    ws.append([title])
    ws["A1"].font = TITLE_FONT
    ws.append([subtitle])
    ws["A2"].font = SUBTITLE_FONT
    ws.append([])
    ws.append(list(headers))
    header_row_idx = 4
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=header_row_idx, column=col_idx)
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    current = header_row_idx + 1
    for row in rows:
        ws.append(list(row))
        for col_idx in range(1, len(row) + 1):
            cell = ws.cell(row=current, column=col_idx)
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal="right" if col_idx >= numeric_from else "left")
        current += 1
    if total_row and rows:
        ws.append(list(total_row))
        for col_idx in range(1, len(total_row) + 1):
            cell = ws.cell(row=current, column=col_idx)
            cell.fill = TOTAL_FILL
            cell.font = TOTAL_FONT
            cell.border = THIN_BORDER
            cell.alignment = Alignment(horizontal="right" if col_idx >= numeric_from else "left")
    _autofit_columns(ws)


# ---------------------------------------------------------------------------
# PRD §22 summary sheets
# ---------------------------------------------------------------------------

def _add_attendance_summary_sheet(wb, records, date_range_str: str) -> None:
    per_emp = {}
    for att, emp in records:
        row = per_emp.setdefault(emp.id, {
            "code": emp.employee_code, "name": emp.name, "department": emp.department,
            "present": 0, "absent": 0, "half_day": 0, "late": 0, "working": 0, "ot": 0,
        })
        if att.status in ("present", "absent", "half_day"):
            row[att.status] += 1
        if (att.late_minutes or 0) > 0:
            row["late"] += 1
        row["working"] += att.working_minutes or 0
        row["ot"] += att.overtime_minutes or 0

    rows = [
        [r["code"], r["name"], r["department"], r["present"], r["absent"], r["half_day"],
         r["late"], r["working"], r["ot"]]
        for r in sorted(per_emp.values(), key=lambda x: x["name"])
    ]
    totals = ["Total", "", ""] + [sum(r[i] for r in rows) for i in range(3, 9)]
    ws = wb.create_sheet("Summary", 0)
    _write_table(
        ws,
        "AI HR Assistant — Attendance Summary",
        f"Period: {date_range_str} | Employees: {len(rows)}",
        ["Employee Code", "Employee", "Department", "Present", "Absent", "Half Day",
         "Late Count", "Working Minutes", "OT Minutes"],
        rows,
        totals,
        numeric_from=4,
    )
    wb.active = 0


def overtime_amount_for_records(db, records):
    """
    OT amount per employee, pro-rated exactly to the records in range (KI-015):
    each record's overtime minutes x the overtime hourly rate of its own month
    (salary_service.overtime_hourly_rate — the same rate the payroll engine uses).
    Employees without a salary structure get None.
    """
    from app.services.holiday_service import get_declared_holiday_dates
    from app.services.salary_service import get_monthly_gross, overtime_hourly_rate

    holidays = get_declared_holiday_dates(db)
    gross_cache, amounts = {}, {}
    for att, emp in records:
        if emp.id not in gross_cache:
            gross_cache[emp.id] = get_monthly_gross(db, emp)
        gross = gross_cache[emp.id]
        if gross is None:
            amounts.setdefault(emp.id, None)
            continue
        rate = overtime_hourly_rate(gross, att.attendance_date.month, att.attendance_date.year, holidays)
        amounts[emp.id] = (amounts.get(emp.id) or 0.0) + (att.overtime_minutes or 0) / 60.0 * rate
    return {emp_id: (round(v, 2) if v is not None else None) for emp_id, v in amounts.items()}


def _add_overtime_summary_sheet(db, wb, records, date_range_str: str, date_from, date_to) -> None:
    per_emp = {}
    for att, emp in records:
        row = per_emp.setdefault(emp.id, {
            "code": emp.employee_code, "name": emp.name, "department": emp.department, "ot": 0,
        })
        row["ot"] += att.overtime_minutes or 0

    amounts = overtime_amount_for_records(db, records)

    rows = [
        [r["code"], r["name"], r["department"], round(r["ot"] / 60.0, 2),
         amounts.get(emp_id) if amounts.get(emp_id) is not None else "n/a"]
        for emp_id, r in sorted(per_emp.items(), key=lambda kv: -kv[1]["ot"])
    ]
    totals = [
        "Total", "", "", round(sum(r[3] for r in rows), 2),
        round(sum(r[4] for r in rows if isinstance(r[4], (int, float))), 2),
    ]
    ws = wb.create_sheet("Summary", 0)
    _write_table(
        ws,
        "AI HR Assistant — Overtime Summary",
        f"Period: {date_range_str} | OT Amount = OT hours x (monthly gross / (working days x 8)) x 1.5, "
        f"pro-rated to the dates in range",
        ["Employee Code", "Employee", "Department", "OT Hours", "OT Amount"],
        rows,
        totals,
        numeric_from=4,
    )
    wb.active = 0


# ---------------------------------------------------------------------------
# 3. Leave Report
# ---------------------------------------------------------------------------

def generate_leave_report(
    db: Session,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    department: Optional[str] = None,
) -> io.BytesIO:
    """
    Leave report (PRD §22): Employee, Leave Type, Leave Days, Status (+ dates, reason).
    A leave is included when it overlaps the requested period.
    """
    from app.services.holiday_service import get_declared_holiday_dates
    from app.services.leave_service import count_leave_days

    holidays = get_declared_holiday_dates(db)

    query = db.query(Leave, Employee).join(Employee, Leave.employee_id == Employee.id)
    if date_from:
        query = query.filter(Leave.to_date >= date_from)
    if date_to:
        query = query.filter(Leave.from_date <= date_to)
    if department:
        query = query.filter(Employee.department == department)
    records = query.order_by(Leave.from_date.desc(), Employee.name.asc()).all()

    date_range_str = "All Recorded Dates"
    if date_from and date_to:
        date_range_str = f"{date_from} to {date_to}"
    elif date_from:
        date_range_str = f"From {date_from}"
    elif date_to:
        date_range_str = f"Up to {date_to}"

    rows = [
        [
            emp.employee_code,
            emp.name,
            emp.department,
            lv.leave_type.replace("_", " ").title(),
            str(lv.from_date),
            str(lv.to_date),
            count_leave_days(lv.from_date, lv.to_date, holidays=holidays),
            lv.status.title(),
            lv.reason or "",
        ]
        for lv, emp in records
    ]

    wb = Workbook()
    ws = wb.active
    ws.title = "Leave Records"
    approved_days = sum(r[6] for r in rows if r[7] == "Approved")
    _write_table(
        ws,
        "AI HR Assistant — Leave Report",
        f"Period: {date_range_str} | Requests: {len(rows)} | Approved leave days: {approved_days}",
        ["Employee Code", "Employee", "Department", "Leave Type", "From", "To",
         "Leave Days", "Status", "Reason"],
        rows,
        numeric_from=7,
    )
    for row in ws.iter_rows(min_row=5, min_col=8, max_col=9):
        for cell in row:
            cell.alignment = Alignment(horizontal="left")

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
