"""
app/services/report_service.py
------------------------------
Excel report generation service using openpyxl (PRD Section 22).

Generates:
1. Attendance Report (.xlsx):
   - Employee name, department, date, status, check-in, check-out, working minutes, overtime.
2. Overtime Report (.xlsx):
   - Employee name, department, date/month, overtime minutes, overtime hours, summary totals.
"""

import io
from datetime import date
from typing import Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database.models import Attendance, Employee


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

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
