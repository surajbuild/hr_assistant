"""
scripts/seed_db.py
------------------
Deterministic database seed script for the AI HR Assistant MVP.

Populates MySQL with realistic company HR data for demo, testing, and AI tool calling:
- Loads seed configuration directly from `app/data/seed_data.json`
- 6 Employees across Executive, HR, Engineering, and Marketing
- 6 Users with different RBAC roles (admin, hr, manager, employee)
- Detailed Attendance records for August, September, and October 2024
  * Aman: Exactly 22 present days out of 24 working days in August (2 absences, 4 late entries)
  * Rahul: Exactly 18 hours 35 minutes (1,115 mins) overtime in September, 3 absences
- Leave records with varying statuses (approved, pending, rejected) and types (casual, sick, earned, unpaid)
- Monthly Salary records for July, August, and September 2024

Usage:
    python scripts/seed_db.py             # Clear existing demo data and re-seed from JSON
    python scripts/seed_db.py --clean     # Remove demo data without re-seeding
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, time

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath("."))

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database.connection import SessionLocal
from app.database.models import (
    Attendance,
    AttendanceStatus,
    ChatLog,
    Employee,
    EmployeeStatus,
    Leave,
    LeaveStatus,
    LeaveType,
    Salary,
    User,
    UserRole,
    UserStatus,
)
from app.utils.security import hash_password

# ---------------------------------------------------------------------------
# Default Seed File & Demo Identifiers
# ---------------------------------------------------------------------------

DEFAULT_SEED_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "app", "data", "seed_data.json"
)

DEMO_PASSWORD_PLAIN = "Demo@12345"

DEMO_EMPLOYEE_CODES = [
    "EMP001",
    "EMP002",
    "EMP003",
    "EMP004",
    "EMP005",
    "EMP006",
]

DEMO_EMAILS = [
    "admin@company.com",
    "neha.hr@company.com",
    "priya.mgr@company.com",
    "aman@company.com",
    "rahul@company.com",
    "sneha@company.com",
]


# ---------------------------------------------------------------------------
# Clean / Reset Logic
# ---------------------------------------------------------------------------

def clear_demo_data(
    db: Session,
    employee_codes: list[str] = DEMO_EMPLOYEE_CODES,
    emails: list[str] = DEMO_EMAILS,
) -> dict:
    """
    Safely delete existing demo data by matching demo employee codes and emails.
    Preserves all foreign-key constraint dependencies.
    """
    demo_employees = db.query(Employee).filter(Employee.employee_code.in_(employee_codes)).all()
    demo_emp_ids = [e.id for e in demo_employees]

    demo_users = db.query(User).filter(
        or_(
            User.email.in_(emails),
            User.employee_id.in_(demo_emp_ids) if demo_emp_ids else False,
        )
    ).all()
    demo_user_ids = [u.id for u in demo_users]

    deleted_counts = {
        "salaries": 0,
        "leaves": 0,
        "attendance": 0,
        "users": 0,
        "employees": 0,
    }

    if demo_emp_ids or demo_user_ids:
        # Delete dependent salary records
        if demo_emp_ids:
            s_del = db.query(Salary).filter(Salary.employee_id.in_(demo_emp_ids)).delete(synchronize_session=False)
            deleted_counts["salaries"] = s_del

        # Delete dependent leaves (both as applicant and approver)
        l_filters = []
        if demo_emp_ids:
            l_filters.append(Leave.employee_id.in_(demo_emp_ids))
        if demo_user_ids:
            l_filters.append(Leave.approved_by.in_(demo_user_ids))
        if l_filters:
            l_del = db.query(Leave).filter(or_(*l_filters)).delete(synchronize_session=False)
            deleted_counts["leaves"] = l_del

        # Delete dependent attendance records
        if demo_emp_ids:
            a_del = db.query(Attendance).filter(Attendance.employee_id.in_(demo_emp_ids)).delete(synchronize_session=False)
            deleted_counts["attendance"] = a_del

        # Delete dependent chat_logs
        if demo_user_ids:
            db.query(ChatLog).filter(ChatLog.user_id.in_(demo_user_ids)).delete(synchronize_session=False)

        # Delete users
        if demo_user_ids or demo_emp_ids:
            u_del = db.query(User).filter(
                or_(
                    User.id.in_(demo_user_ids) if demo_user_ids else False,
                    User.employee_id.in_(demo_emp_ids) if demo_emp_ids else False,
                )
            ).delete(synchronize_session=False)
            deleted_counts["users"] = u_del

        # Clear self-referential manager_ids before deleting employees
        if demo_emp_ids:
            db.query(Employee).filter(Employee.id.in_(demo_emp_ids)).update(
                {Employee.manager_id: None}, synchronize_session=False
            )
            e_del = db.query(Employee).filter(Employee.id.in_(demo_emp_ids)).delete(synchronize_session=False)
            deleted_counts["employees"] = e_del

        db.commit()

    return deleted_counts


# ---------------------------------------------------------------------------
# Seed Data Loading & Population
# ---------------------------------------------------------------------------

def seed_database(
    db: Session,
    reset: bool = True,
    seed_file: str = DEFAULT_SEED_FILE,
) -> dict:
    """
    Populate the database with deterministic demo HR data loaded from a JSON file.
    """
    if not os.path.exists(seed_file):
        raise FileNotFoundError(f"Seed file not found: {seed_file}")

    with open(seed_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Extract demo identifiers from JSON to ensure full cleanup
    seed_emp_codes = [e["employee_code"] for e in data.get("employees", [])] or DEMO_EMPLOYEE_CODES
    seed_emails = [u["email"] for u in data.get("users", [])] or DEMO_EMAILS

    if reset:
        clear_demo_data(db, employee_codes=seed_emp_codes, emails=seed_emails)

    hashed_pw = hash_password(DEMO_PASSWORD_PLAIN)

    # 1. Employees & Management Hierarchy (2-phase insert to resolve manager self-reference)
    emp_map: dict[str, Employee] = {}
    for item in data.get("employees", []):
        emp = Employee(
            employee_code=item["employee_code"],
            name=item["name"],
            department=item["department"],
            designation=item["designation"],
            joining_date=date.fromisoformat(item["joining_date"]),
            status=item.get("status", EmployeeStatus.ACTIVE.value),
            manager_id=None,
        )
        db.add(emp)
        emp_map[item["employee_code"]] = emp

    db.commit()

    # Assign manager_id references
    for item in data.get("employees", []):
        m_code = item.get("manager_code")
        if m_code and m_code in emp_map:
            emp_map[item["employee_code"]].manager_id = emp_map[m_code].id

    db.commit()
    for emp in emp_map.values():
        db.refresh(emp)

    # 2. Users (Authentication & RBAC)
    user_map: dict[str, User] = {}
    for item in data.get("users", []):
        emp = emp_map.get(item["employee_code"])
        user = User(
            employee_id=emp.id if emp else None,
            email=item["email"],
            password_hash=hashed_pw,
            role=item["role"],
            status=item.get("status", UserStatus.ACTIVE.value),
        )
        db.add(user)
        user_map[item["email"]] = user

    db.commit()
    for user in user_map.values():
        db.refresh(user)

    # 3. Attendance Records
    attendance_records = []
    for item in data.get("attendance", []):
        emp = emp_map.get(item["employee_code"])
        if not emp:
            continue
        attendance_records.append(
            Attendance(
                employee_id=emp.id,
                attendance_date=date.fromisoformat(item["attendance_date"]),
                status=item["status"],
                in_time=time.fromisoformat(item["in_time"]) if item.get("in_time") else None,
                out_time=time.fromisoformat(item["out_time"]) if item.get("out_time") else None,
                working_minutes=item.get("working_minutes", 0),
                late_minutes=item.get("late_minutes", 0),
                overtime_minutes=item.get("overtime_minutes", 0),
            )
        )
    db.add_all(attendance_records)
    db.commit()

    # 4. Leave Records
    leave_records = []
    for item in data.get("leaves", []):
        emp = emp_map.get(item["employee_code"])
        if not emp:
            continue
        approver = user_map.get(item["approved_by_email"]) if item.get("approved_by_email") else None
        leave_records.append(
            Leave(
                employee_id=emp.id,
                leave_type=item["leave_type"],
                from_date=date.fromisoformat(item["from_date"]),
                to_date=date.fromisoformat(item["to_date"]),
                status=item["status"],
                reason=item.get("reason"),
                approved_by=approver.id if approver else None,
            )
        )
    db.add_all(leave_records)
    db.commit()

    # 5. Salary Records
    salary_records = []
    for item in data.get("salaries", []):
        emp = emp_map.get(item["employee_code"])
        if not emp:
            continue
        paid_dt = datetime.fromisoformat(item["paid_at"]) if item.get("paid_at") else None
        salary_records.append(
            Salary(
                employee_id=emp.id,
                month=item["month"],
                year=item["year"],
                gross_salary=item["gross_salary"],
                pf=item.get("pf", 0.0),
                deductions=item.get("deductions", 0.0),
                overtime_amount=item.get("overtime_amount", 0.0),
                net_salary=item["net_salary"],
                paid_at=paid_dt,
            )
        )
    db.add_all(salary_records)
    db.commit()

    return {
        "employees": len(data.get("employees", [])),
        "users": len(data.get("users", [])),
        "attendance": len(attendance_records),
        "leaves": len(leave_records),
        "salaries": len(salary_records),
    }


# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed demo HR dataset for AI HR Assistant.")
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove all demo data without re-seeding.",
    )
    parser.add_argument(
        "--file",
        type=str,
        default=DEFAULT_SEED_FILE,
        help="Custom path to seed JSON file.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.clean:
            print("[INFO] Cleaning demo records...")
            counts = clear_demo_data(db)
            print(f"[SUCCESS] Removed: {counts}")
        else:
            print(f"[INFO] Seeding database with demo HR dataset from {args.file}...")
            counts = seed_database(db, reset=True, seed_file=args.file)
            print("[SUCCESS] Database seeded successfully!")
            print(f"  • Employees  : {counts['employees']}")
            print(f"  • Users      : {counts['users']}")
            print(f"  • Attendance : {counts['attendance']}")
            print(f"  • Leaves     : {counts['leaves']}")
            print(f"  • Salaries   : {counts['salaries']}")
            print("\nDefault demo accounts (password for all: 'Demo@12345'):")
            print("  • Admin   : admin@company.com     (Vikram Sharma)")
            print("  • HR      : neha.hr@company.com   (Neha Verma)")
            print("  • Manager : priya.mgr@company.com (Priya Nair)")
            print("  • Employee: aman@company.com      (Aman Gupta)")
            print("  • Employee: rahul@company.com     (Rahul Sharma)")
            print("  • Employee: sneha@company.com     (Sneha Patel)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
