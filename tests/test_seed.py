import json
import os
import sys
import tempfile
from datetime import time

sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models import (
    Attendance,
    AttendanceStatus,
    Employee,
    Leave,
    LeaveStatus,
    LeaveType,
    Salary,
    User,
    UserRole,
)
from app.main import app
from scripts.seed_db import (
    DEFAULT_SEED_FILE,
    DEMO_EMPLOYEE_CODES,
    DEMO_EMAILS,
    DEMO_PASSWORD_PLAIN,
    clear_demo_data,
    seed_database,
)

client = TestClient(app)
db = SessionLocal()

# ---------------------------------------------------------------------------
# Isolation: never touch the real demo rows (AGENTS.md §5, KI-002).
# The test seeds a remapped copy of app/data/seed_data.json in which every
# employee code and email is namespaced (EMP004 -> TS-EMP004,
# aman@company.com -> ts.aman@hrtest.dev), and removes exactly those rows.
# ---------------------------------------------------------------------------
TS_PREFIX = "TS-"


def c(code: str) -> str:
    """Namespaced employee code used by this test."""
    return f"{TS_PREFIX}{code}"


def em(email: str) -> str:
    """Namespaced email used by this test."""
    return f"ts.{email.split('@')[0]}@hrtest.dev"


def build_isolated_seed_file() -> str:
    with open(DEFAULT_SEED_FILE, encoding="utf-8") as f:
        data = json.load(f)
    for emp in data["employees"]:
        emp["employee_code"] = c(emp["employee_code"])
        if emp.get("manager_code"):
            emp["manager_code"] = c(emp["manager_code"])
    for user in data["users"]:
        user["employee_code"] = c(user["employee_code"])
        user["email"] = em(user["email"])
    for key in ("attendance", "leaves", "salaries"):
        for row in data[key]:
            row["employee_code"] = c(row["employee_code"])
            if row.get("approved_by_email"):
                row["approved_by_email"] = em(row["approved_by_email"])
    fd, path = tempfile.mkstemp(prefix="seed_ts_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f)
    return path


TS_SEED_FILE = build_isolated_seed_file()
TS_CODES = [c(code) for code in DEMO_EMPLOYEE_CODES]
TS_EMAILS = [em(e) for e in DEMO_EMAILS]

SEP = "-" * 55
passed = 0
failed = 0


def chk(ok: bool, ok_msg: str, fail_msg: str):
    global passed, failed
    if ok:
        print(f"    PASS - {ok_msg}")
        passed += 1
    else:
        print(f"    FAIL - {fail_msg}")
        failed += 1


try:
    print(SEP)
    print("  Seed Database & Demo Data - Comprehensive Test")
    print(SEP)

    # -----------------------------------------------------------------------
    # [1] Initial Seed Execution
    # -----------------------------------------------------------------------
    # Baseline for company-wide aggregates (real demo data is present and untouched)
    clear_demo_data(db, employee_codes=TS_CODES, emails=TS_EMAILS)
    _hr = db.query(User).filter(User.role == UserRole.HR.value, User.status == "active").first()
    from app.utils.security import create_access_token as _tok
    baseline_summary = client.get(
        "/salary/summary?month=8&year=2024",
        headers={"Authorization": f"Bearer {_tok(user_id=_hr.id, role=_hr.role)}"},
    ).json() if _hr else {"record_count": 0, "total_gross_salary": 0.0}

    print("\n[1] seed_database() initial run")
    counts1 = seed_database(db, reset=True, seed_file=TS_SEED_FILE)
    chk(counts1["employees"] == 6, "Inserted 6 demo employees", f"Expected 6 employees, got {counts1['employees']}")
    chk(counts1["users"] == 6, "Inserted 6 demo users", f"Expected 6 users, got {counts1['users']}")
    chk(counts1["attendance"] == 66, "Inserted 66 attendance records", f"Expected 66 attendance, got {counts1['attendance']}")
    chk(counts1["leaves"] == 8, "Inserted 8 leave records", f"Expected 8 leaves, got {counts1['leaves']}")
    chk(counts1["salaries"] == 18, "Inserted 18 salary records", f"Expected 18 salaries, got {counts1['salaries']}")

    # -----------------------------------------------------------------------
    # [2] Idempotency & Re-run Safety
    # -----------------------------------------------------------------------
    print("\n[2] seed_database() re-run idempotency")
    counts2 = seed_database(db, reset=True, seed_file=TS_SEED_FILE)
    chk(counts2["employees"] == 6, "Re-run cleanly inserted 6 employees", f"Expected 6, got {counts2['employees']}")
    chk(counts2["attendance"] == 66, "Re-run cleanly inserted 66 attendance records", f"Expected 66, got {counts2['attendance']}")

    # Check total demo counts in DB
    demo_emps = db.query(Employee).filter(Employee.employee_code.in_(TS_CODES)).all()
    chk(len(demo_emps) == 6, "Exact 6 demo employees exist in DB (no duplicates)", f"Found {len(demo_emps)}")

    demo_users = db.query(User).filter(User.email.in_(TS_EMAILS)).all()
    chk(len(demo_users) == 6, "Exact 6 demo users exist in DB (no duplicates)", f"Found {len(demo_users)}")

    # -----------------------------------------------------------------------
    # [3] Verify Roles and Hierarchy
    # -----------------------------------------------------------------------
    print("\n[3] Verify Roles, Hierarchy & Foreign Keys")
    role_map = {u.email: u.role for u in demo_users}
    chk(role_map.get(em("admin@company.com")) == UserRole.ADMIN.value, "Vikram is ADMIN", f"Got {role_map.get('admin@company.com')}")
    chk(role_map.get(em("neha.hr@company.com")) == UserRole.HR.value, "Neha is HR", f"Got {role_map.get('neha.hr@company.com')}")
    chk(role_map.get(em("priya.mgr@company.com")) == UserRole.MANAGER.value, "Priya is MANAGER", f"Got {role_map.get('priya.mgr@company.com')}")
    chk(role_map.get(em("aman@company.com")) == UserRole.EMPLOYEE.value, "Aman is EMPLOYEE", f"Got {role_map.get('aman@company.com')}")
    chk(role_map.get(em("rahul@company.com")) == UserRole.EMPLOYEE.value, "Rahul is EMPLOYEE", f"Got {role_map.get('rahul@company.com')}")
    chk(role_map.get(em("sneha@company.com")) == UserRole.EMPLOYEE.value, "Sneha is EMPLOYEE", f"Got {role_map.get('sneha@company.com')}")

    emp_by_code = {e.employee_code: e for e in demo_emps}
    chk(emp_by_code[c("EMP002")].manager_id == emp_by_code[c("EMP001")].id, "Neha reports to CEO Vikram", "Manager link mismatch")
    chk(emp_by_code[c("EMP004")].manager_id == emp_by_code[c("EMP003")].id, "Aman reports to Priya", "Manager link mismatch")
    chk(emp_by_code[c("EMP005")].manager_id == emp_by_code[c("EMP003")].id, "Rahul reports to Priya", "Manager link mismatch")

    # -----------------------------------------------------------------------
    # [4] Verify Aman Gupta PRD Requirements (August 2024 Attendance)
    # -----------------------------------------------------------------------
    print("\n[4] Aman Gupta August 2024 Attendance Verification")
    aman_emp = emp_by_code[c("EMP004")]
    aman_aug_att = (
        db.query(Attendance)
        .filter(
            Attendance.employee_id == aman_emp.id,
            Attendance.attendance_date >= "2024-08-01",
            Attendance.attendance_date <= "2024-08-31",
        )
        .all()
    )
    chk(len(aman_aug_att) == 25, "Aman has 25 August records (24 working days + 1 holiday)", f"Got {len(aman_aug_att)}")
    aman_working_days = sum(1 for a in aman_aug_att if a.status in [AttendanceStatus.PRESENT.value, AttendanceStatus.ABSENT.value])
    chk(aman_working_days == 24, "Aman has exactly 24 working days in August (22 present + 2 absent)", f"Got {aman_working_days}")

    aman_present = sum(1 for a in aman_aug_att if a.status == AttendanceStatus.PRESENT.value)
    aman_absent = sum(1 for a in aman_aug_att if a.status == AttendanceStatus.ABSENT.value)
    aman_late = sum(1 for a in aman_aug_att if a.late_minutes > 0)

    chk(aman_present == 22, "Aman has exactly 22 PRESENT days in August", f"Got {aman_present}")
    chk(aman_absent == 2, "Aman has exactly 2 ABSENT days in August", f"Got {aman_absent}")
    chk(aman_late == 4, "Aman has exactly 4 late clock-ins in August (>0 late_minutes)", f"Got {aman_late}")

    # -----------------------------------------------------------------------
    # [5] Verify Rahul Sharma PRD Requirements (September 2024 Overtime)
    # -----------------------------------------------------------------------
    print("\n[5] Rahul Sharma September 2024 Overtime Verification")
    rahul_emp = emp_by_code[c("EMP005")]
    rahul_sep_att = (
        db.query(Attendance)
        .filter(
            Attendance.employee_id == rahul_emp.id,
            Attendance.attendance_date >= "2024-09-01",
            Attendance.attendance_date <= "2024-09-30",
        )
        .all()
    )
    chk(len(rahul_sep_att) == 21, "Rahul has 21 September working day records", f"Got {len(rahul_sep_att)}")

    rahul_absent = sum(1 for a in rahul_sep_att if a.status == AttendanceStatus.ABSENT.value)
    rahul_overtime_mins = sum(a.overtime_minutes or 0 for a in rahul_sep_att)

    chk(rahul_absent == 3, "Rahul has exactly 3 ABSENT days in September", f"Got {rahul_absent}")
    chk(
        rahul_overtime_mins == 1115,
        "Rahul has exactly 1,115 mins (18h 35m) overtime in September",
        f"Got {rahul_overtime_mins}",
    )

    # -----------------------------------------------------------------------
    # [6] Verify Leave Data Diversity
    # -----------------------------------------------------------------------
    print("\n[6] Leave Data Diversity Verification")
    demo_emp_ids = [e.id for e in demo_emps]
    leaves = db.query(Leave).filter(Leave.employee_id.in_(demo_emp_ids)).all()
    leave_statuses = {l.status for l in leaves}
    leave_types = {l.leave_type for l in leaves}

    chk(
        {LeaveStatus.APPROVED.value, LeaveStatus.PENDING.value, LeaveStatus.REJECTED.value}.issubset(leave_statuses),
        "Leaves cover APPROVED, PENDING, and REJECTED statuses",
        f"Found statuses: {leave_statuses}",
    )
    chk(
        {LeaveType.CASUAL.value, LeaveType.SICK.value, LeaveType.EARNED.value}.issubset(leave_types),
        "Leaves cover CASUAL, SICK, and EARNED leave types",
        f"Found types: {leave_types}",
    )

    # -----------------------------------------------------------------------
    # [7] Verify Salary Aggregates
    # -----------------------------------------------------------------------
    print("\n[7] Salary Data Verification")
    salaries = db.query(Salary).filter(Salary.employee_id.in_(demo_emp_ids)).all()
    chk(len(salaries) == 18, "Total 18 salary records for demo employees", f"Got {len(salaries)}")

    aug_salaries = [s for s in salaries if s.month == 8 and s.year == 2024]
    chk(len(aug_salaries) == 6, "August 2024 has salaries for all 6 demo employees", f"Got {len(aug_salaries)}")
    aug_gross = sum(s.gross_salary for s in aug_salaries)
    chk(aug_gross == 590000.0, "August total gross is 590,000.00", f"Got {aug_gross}")

    # -----------------------------------------------------------------------
    # [8] API Integration with Seeded Users
    # -----------------------------------------------------------------------
    print("\n[8] API Integration using Seeded Credentials")

    # 8.1 Login as Aman (Employee)
    r_aman_login = client.post("/auth/login", json={"email": em("aman@company.com"), "password": DEMO_PASSWORD_PLAIN})
    chk(r_aman_login.status_code == 200, "Aman logged in via /auth/login -> 200", f"Status {r_aman_login.status_code}")
    aman_token = r_aman_login.json().get("access_token")
    aman_headers = {"Authorization": f"Bearer {aman_token}"}

    # 8.2 Aman accesses own attendance
    r_aman_att = client.get("/attendance/me", headers=aman_headers)
    chk(r_aman_att.status_code == 200, "Aman accessed /attendance/me -> 200", f"Status {r_aman_att.status_code}")
    chk(len(r_aman_att.json()) == 25, "Aman retrieved 25 attendance records", f"Got {len(r_aman_att.json())}")

    # 8.3 Aman accesses own leaves
    r_aman_leaves = client.get("/leaves/me", headers=aman_headers)
    chk(r_aman_leaves.status_code == 200, "Aman accessed /leaves/me -> 200", f"Status {r_aman_leaves.status_code}")
    chk(len(r_aman_leaves.json()) >= 1, "Aman retrieved own leave records", f"Got {len(r_aman_leaves.json())}")

    # 8.4 Aman accesses own salary
    r_aman_sal = client.get("/salary/me", headers=aman_headers)
    chk(r_aman_sal.status_code == 200, "Aman accessed /salary/me -> 200", f"Status {r_aman_sal.status_code}")
    chk(len(r_aman_sal.json()) == 3, "Aman retrieved 3 monthly salary records", f"Got {len(r_aman_sal.json())}")

    # 8.5 Login as Neha (HR)
    r_neha_login = client.post("/auth/login", json={"email": em("neha.hr@company.com"), "password": DEMO_PASSWORD_PLAIN})
    chk(r_neha_login.status_code == 200, "Neha (HR) logged in via /auth/login -> 200", f"Status {r_neha_login.status_code}")
    hr_token = r_neha_login.json().get("access_token")
    hr_headers = {"Authorization": f"Bearer {hr_token}"}

    # 8.6 HR lists all employees
    r_emps = client.get("/employees", headers=hr_headers)
    chk(r_emps.status_code == 200, "HR accessed /employees -> 200", f"Status {r_emps.status_code}")
    emp_codes_returned = [e["employee_code"] for e in r_emps.json()]
    chk(
        set(TS_CODES).issubset(set(emp_codes_returned)),
        "HR /employees returns all demo employees",
        f"Missing: {set(TS_CODES) - set(emp_codes_returned)}",
    )

    # 8.7 HR looks up Aman's leaves via /leaves/{aman_id}
    r_aman_leaves_by_hr = client.get(f"/leaves/{aman_emp.id}", headers=hr_headers)
    chk(r_aman_leaves_by_hr.status_code == 200, "HR accessed /leaves/{id} for Aman -> 200", f"Status {r_aman_leaves_by_hr.status_code}")

    # 8.8 HR accesses salary summary for August 2024
    r_sal_sum = client.get("/salary/summary?month=8&year=2024", headers=hr_headers)
    chk(r_sal_sum.status_code == 200, "HR accessed /salary/summary -> 200", f"Status {r_sal_sum.status_code}")
    sum_data = r_sal_sum.json()
    delta_records = sum_data.get("record_count", 0) - baseline_summary.get("record_count", 0)
    delta_gross = round(sum_data.get("total_gross_salary", 0) - baseline_summary.get("total_gross_salary", 0), 2)
    chk(delta_records == 6, "Seeded data adds 6 salary records to the Aug 2024 summary", f"Got +{delta_records}")
    chk(delta_gross == 590000.0, "Seeded data adds 590,000.00 gross to the Aug 2024 summary", f"Got +{delta_gross}")

    # -----------------------------------------------------------------------
    # [9] Demo Data Clean Verification & Final Re-seed
    # -----------------------------------------------------------------------
    print("\n[9] clear_demo_data() verification & final re-seed")
    del_counts = clear_demo_data(db, employee_codes=TS_CODES, emails=TS_EMAILS)
    chk(del_counts["employees"] == 6, "clear_demo_data() deleted 6 demo employees", f"Got {del_counts['employees']}")
    chk(del_counts["users"] == 6, "clear_demo_data() deleted 6 demo users", f"Got {del_counts['users']}")

    rem_emps = db.query(Employee).filter(Employee.employee_code.in_(TS_CODES)).count()
    chk(rem_emps == 0, "No demo employees remain after clean", f"Remaining: {rem_emps}")

    # Real demo data must be untouched by everything above
    real_left = db.query(Employee).filter(Employee.employee_code.in_(DEMO_EMPLOYEE_CODES)).count()
    chk(real_left == 6, "Real demo employees untouched by the isolated seed test", f"Real demo employees: {real_left}")

    print("\n" + SEP)
    print(f"  Results: {passed} passed, {failed} failed")
    print(SEP)

except Exception as exc:
    print(f"\n[ERROR] Exception occurred during testing: {exc}")
    import traceback
    traceback.print_exc()
    failed += 1
finally:
    try:
        db.rollback()
        clear_demo_data(db, employee_codes=TS_CODES, emails=TS_EMAILS)
        db.commit()
    except Exception as cleanup_exc:  # never mask the test result
        print(f"[WARN] cleanup failed: {cleanup_exc}")
    db.close()
    try:
        os.remove(TS_SEED_FILE)
    except OSError:
        pass

if failed > 0:
    sys.exit(1)
else:
    sys.exit(0)
