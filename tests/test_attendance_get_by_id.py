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
    emails = ["getbyid.hr@hr.dev", "getbyid.admin@hr.dev", "getbyid.emp@hr.dev", "getbyid.tgt@hr.dev"]
    codes = ["A-ID-HR", "A-ID-ADM", "A-ID-EMP", "A-ID-TGT"]
    
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
    print("  GET /attendance/{id} - Integration Test")
    print(SEP)
    cleanup()

    _, _, hr_t = make_test_user("getbyid.hr@hr.dev", "hr", "A-ID-HR")
    _, _, adm_t = make_test_user("getbyid.admin@hr.dev", "admin", "A-ID-ADM")
    _, _, emp_t = make_test_user("getbyid.emp@hr.dev", "employee", "A-ID-EMP")
    tgt_emp, _, _ = make_test_user("getbyid.tgt@hr.dev", "employee", "A-ID-TGT")

    # Add records for target employee
    att1 = Attendance(
        employee_id=tgt_emp.id, attendance_date=date(2024, 10, 1), 
        in_time=time(9, 0), out_time=time(17, 0), working_minutes=480, 
        status="present", late_minutes=0, overtime_minutes=0
    )
    db.add(att1)
    db.commit()

    print("\n[1] HR can get employee attendance -> 200")
    r1 = client.get(f"/attendance/{tgt_emp.id}", headers={"Authorization": f"Bearer {hr_t}"})
    chk(r1.status_code == 200, "status 200", f"status {r1.status_code}")
    chk(len(r1.json()) == 1, "1 record returned", f"got {len(r1.json())}")

    print("\n[2] Admin can get employee attendance -> 200")
    r2 = client.get(f"/attendance/{tgt_emp.id}", headers={"Authorization": f"Bearer {adm_t}"})
    chk(r2.status_code == 200, "status 200", f"status {r2.status_code}")

    print("\n[3] employee cannot get other employee attendance -> 403")
    r3 = client.get(f"/attendance/{tgt_emp.id}", headers={"Authorization": f"Bearer {emp_t}"})
    chk(r3.status_code == 403, "status 403", f"status {r3.status_code}")

    print("\n[4] unauthenticated request -> 401")
    r4 = client.get(f"/attendance/{tgt_emp.id}")
    chk(r4.status_code == 401, "status 401", f"status {r4.status_code}")

    print("\n[5] non-existent employee -> 404")
    r5 = client.get(f"/attendance/999999", headers={"Authorization": f"Bearer {hr_t}"})
    chk(r5.status_code == 404, "status 404", f"status {r5.status_code}")

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
