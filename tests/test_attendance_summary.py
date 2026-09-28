import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from datetime import date, time
from fastapi.testclient import TestClient

from app.main import app
from app.database.connection import SessionLocal
from app.database.models import Employee, User, Attendance
from app.database.queries import create_employee, create_user
from app.utils.security import create_access_token

client = TestClient(app)
db = SessionLocal()

def cleanup():
    emails = ["sum.emp@hr.dev", "sum.empty@hr.dev"]
    codes = ["S-EMP", "S-EMPTY"]
    
    users = db.query(User).filter(User.email.in_(emails)).all()
    for u in users:
        db.query(Attendance).filter(Attendance.employee_id == u.employee_id).delete()
        db.delete(u)
    db.commit()
        
    db.query(Employee).filter(Employee.employee_code.in_(codes)).delete()
    db.commit()

SEP = "-" * 55
passed = 0
failed = 0

def chk(ok, ok_msg, fail_msg):
    global passed, failed
    if ok:
        print("    PASS - " + ok_msg)
        passed += 1
    else:
        print("    FAIL - " + fail_msg)
        failed += 1

def make_test_user(email: str, role: str, emp_code: str):
    emp = create_employee(
        db, employee_code=emp_code, name=f"Tester {role}", 
        department="Test", designation="Tester", joining_date=date(2024, 1, 1)
    )
    user = create_user(db, employee_id=emp.id, email=email, password_hash="hash", role=role)
    token = create_access_token(user_id=user.id, role=user.role)
    return emp, user, token

try:
    print(SEP)
    print("  GET /attendance/summary - Integration Test")
    print(SEP)
    cleanup()

    emp, _, emp_t = make_test_user("sum.emp@hr.dev", "employee", "S-EMP")
    empty_emp, _, empty_t = make_test_user("sum.empty@hr.dev", "employee", "S-EMPTY")

    records = [
        # date, status, working_minutes, late_minutes, overtime_minutes
        (date(2024, 10, 1), "present", 480, 0, 0),    # Normal present
        (date(2024, 10, 2), "present", 450, 30, 0),   # Present but late
        (date(2024, 10, 3), "absent", 0, 0, 0),       # Absent
        (date(2024, 10, 4), "half_day", 240, 0, 0),   # Half day
        (date(2024, 10, 5), "leave", 0, 0, 0),        # Leave
        (date(2024, 10, 6), "weekend", 0, 0, 120),    # Weekend Overtime
        (date(2024, 10, 7), "present", 600, 0, 120),  # Present Overtime
    ]

    for d, st, w_m, l_m, o_m in records:
        db.add(Attendance(
            employee_id=emp.id, attendance_date=d,
            status=st, working_minutes=w_m, late_minutes=l_m, overtime_minutes=o_m
        ))
    db.commit()

    print("\n[1] authenticated employee gets correct summary -> 200")
    r1 = client.get("/attendance/summary", headers={"Authorization": f"Bearer {emp_t}"})
    chk(r1.status_code == 200, "status 200", f"status {r1.status_code}")
    data = r1.json()

    print("\n[2] present/absent/leave/half_day counts are correct")
    chk(data["total_days"] == 7, "total_days=7", f"total_days={data['total_days']}")
    chk(data["present_days"] == 3, "present=3", f"present={data['present_days']}")
    chk(data["absent_days"] == 1, "absent=1", f"absent={data['absent_days']}")
    chk(data["half_day_days"] == 1, "half=1", f"half={data['half_day_days']}")
    chk(data["leave_days"] == 1, "leave=1", f"leave={data['leave_days']}")

    print("\n[3] late_days calculation is correct")
    chk(data["late_days"] == 1, "late_days=1", f"late_days={data['late_days']}")

    print("\n[4] overtime_days calculation is correct")
    chk(data["overtime_days"] == 2, "overtime_days=2", f"overtime_days={data['overtime_days']}")

    print("\n[5] working/overtime minute totals are correct")
    chk(data["total_working_minutes"] == 1770, "total_working_minutes=1770", f"total_working_minutes={data['total_working_minutes']}")
    chk(data["total_overtime_minutes"] == 240, "total_overtime_minutes=240", f"total_overtime_minutes={data['total_overtime_minutes']}")

    print("\n[6] date filtering works")
    r2 = client.get("/attendance/summary?start_date=2024-10-01&end_date=2024-10-02", headers={"Authorization": f"Bearer {emp_t}"})
    chk(r2.status_code == 200, "status 200", f"status {r2.status_code}")
    data_f = r2.json()
    chk(data_f["total_days"] == 2, "total_days=2", f"total_days={data_f['total_days']}")
    chk(data_f["late_days"] == 1, "late_days=1", f"late_days={data_f['late_days']}")
    chk(data_f["total_working_minutes"] == 930, "working_minutes=930", f"working_minutes={data_f['total_working_minutes']}")

    print("\n[7] employee with no records gets zero summary")
    r3 = client.get("/attendance/summary", headers={"Authorization": f"Bearer {empty_t}"})
    chk(r3.status_code == 200, "status 200", f"status {r3.status_code}")
    chk(r3.json()["total_days"] == 0, "total_days=0", f"total_days={r3.json()['total_days']}")
    chk(r3.json()["total_working_minutes"] == 0, "total_working_minutes=0", f"working={r3.json()['total_working_minutes']}")

    print("\n[8] invalid date range -> 422")
    r4 = client.get("/attendance/summary?start_date=2024-10-10&end_date=2024-10-01", headers={"Authorization": f"Bearer {emp_t}"})
    chk(r4.status_code == 422, "status 422", f"status {r4.status_code}")

    print("\n[9] missing/invalid token -> 401")
    r5 = client.get("/attendance/summary")
    chk(r5.status_code == 401, "missing token -> 401", f"status {r5.status_code}")
    r6 = client.get("/attendance/summary", headers={"Authorization": "Bearer BAD"})
    chk(r6.status_code == 401, "invalid token -> 401", f"status {r6.status_code}")

except Exception as e:
    print("\nEXCEPTION:", e)
    failed += 1
finally:
    cleanup()
    db.close()
    print("\n" + SEP)
    print(f"  Results: {passed} passed, {failed} failed")
    print(SEP)
    if failed > 0: sys.exit(1)
