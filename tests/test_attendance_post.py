import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from datetime import date
from fastapi.testclient import TestClient

from app.main import app
from app.database.connection import SessionLocal
from app.database.models import Employee, User, Attendance
from app.database.queries import create_employee, create_user
from app.utils.security import create_access_token

client = TestClient(app)
db = SessionLocal()

def cleanup():
    emails = ["att.hr@hr.dev", "att.admin@hr.dev", "att.emp@hr.dev", "att.target@hr.dev"]
    codes = ["A-HR", "A-ADM", "A-EMP", "A-TGT"]
    
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
    print("  POST /attendance - Integration Test")
    print(SEP)
    cleanup()

    _, _, hr_t = make_test_user("att.hr@hr.dev", "hr", "A-HR")
    _, _, adm_t = make_test_user("att.admin@hr.dev", "admin", "A-ADM")
    _, _, emp_t = make_test_user("att.emp@hr.dev", "employee", "A-EMP")
    tgt_emp, _, _ = make_test_user("att.target@hr.dev", "employee", "A-TGT")

    payload1 = {
        "employee_id": tgt_emp.id,
        "attendance_date": "2024-10-10",
        "in_time": "09:00:00",
        "out_time": "17:00:00",
        "status": "present",
        "working_minutes": 480,
        "late_minutes": 0,
        "overtime_minutes": 0
    }

    print("\n[1] HR can create attendance -> 201")
    r1 = client.post("/attendance", json=payload1, headers={"Authorization": f"Bearer {hr_t}"})
    chk(r1.status_code == 201, "status 201", f"status {r1.status_code}")
    db.commit()
    att_in_db1 = db.query(Attendance).filter(
        Attendance.employee_id == tgt_emp.id, Attendance.attendance_date == date(2024,10,10)
    ).first()
    chk(att_in_db1 is not None, "Record inserted into DB by HR", "Record not found")

    print("\n[2] Admin can create attendance -> 201")
    payload2 = payload1.copy()
    payload2["attendance_date"] = "2024-10-11"
    r2 = client.post("/attendance", json=payload2, headers={"Authorization": f"Bearer {adm_t}"})
    chk(r2.status_code == 201, "status 201", f"status {r2.status_code}")
    db.commit()
    att_in_db2 = db.query(Attendance).filter(
        Attendance.employee_id == tgt_emp.id, Attendance.attendance_date == date(2024,10,11)
    ).first()
    chk(att_in_db2 is not None, "Record inserted into DB by Admin", "Record not found")

    print("\n[3] employee cannot create attendance -> 403")
    payload3 = payload1.copy()
    payload3["attendance_date"] = "2024-10-12"
    r3 = client.post("/attendance", json=payload3, headers={"Authorization": f"Bearer {emp_t}"})
    chk(r3.status_code == 403, "status 403", f"status {r3.status_code}")

    print("\n[4] unauthenticated request -> 401")
    r4 = client.post("/attendance", json=payload3)
    chk(r4.status_code == 401, "status 401", f"status {r4.status_code}")

    print("\n[5] non-existent employee -> 404")
    payload4 = payload3.copy()
    payload4["employee_id"] = 999999
    r5 = client.post("/attendance", json=payload4, headers={"Authorization": f"Bearer {hr_t}"})
    chk(r5.status_code == 404, "status 404", f"status {r5.status_code}")

    print("\n[6] duplicate attendance date -> appropriate error (409)")
    r6 = client.post("/attendance", json=payload1, headers={"Authorization": f"Bearer {hr_t}"})
    chk(r6.status_code == 409, "status 409", f"status {r6.status_code} text: {r6.text}")

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
