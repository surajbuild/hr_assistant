import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from datetime import date
from fastapi.testclient import TestClient

from app.main import app
from app.database.connection import SessionLocal
from app.database.models import Employee, User, Leave
from app.database.queries import create_employee, create_user
from app.utils.security import create_access_token

client = TestClient(app)
db = SessionLocal()

def cleanup():
    emails = [
        "leave.id.hr@hr.dev",
        "leave.id.adm@hr.dev",
        "leave.id.mgr@hr.dev",
        "leave.id.emp@hr.dev",
        "leave.id.tgt@hr.dev",
        "leave.id.empty@hr.dev",
    ]
    codes = [
        "LEV-ID-HR",
        "LEV-ID-ADM",
        "LEV-ID-MGR",
        "LEV-ID-EMP",
        "LEV-ID-TGT",
        "LEV-ID-EMPTY",
    ]
    
    users = db.query(User).filter(User.email.in_(emails)).all()
    for u in users:
        db.query(Leave).filter(Leave.employee_id == u.employee_id).delete()
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

def make_test_user(email: str, role: str, emp_code: str, name: str):
    emp = create_employee(
        db, employee_code=emp_code, name=name, 
        department="Operations", designation=f"Staff {role}", joining_date=date(2024, 1, 15)
    )
    user = create_user(db, employee_id=emp.id, email=email, password_hash="hash", role=role)
    token = create_access_token(user_id=user.id, role=user.role)
    return emp, user, token

try:
    print(SEP)
    print("  GET /leaves/{employee_id} - Integration Test")
    print(SEP)
    cleanup()

    # Create test users with various roles
    _, _, hr_t = make_test_user("leave.id.hr@hr.dev", "hr", "LEV-ID-HR", "HR User")
    _, _, adm_t = make_test_user("leave.id.adm@hr.dev", "admin", "LEV-ID-ADM", "Admin User")
    _, _, mgr_t = make_test_user("leave.id.mgr@hr.dev", "manager", "LEV-ID-MGR", "Manager User")
    emp, _, emp_t = make_test_user("leave.id.emp@hr.dev", "employee", "LEV-ID-EMP", "Normal Employee")
    tgt_emp, _, _ = make_test_user("leave.id.tgt@hr.dev", "employee", "LEV-ID-TGT", "Target Employee")
    empty_emp, _, _ = make_test_user("leave.id.empty@hr.dev", "employee", "LEV-ID-EMPTY", "Empty Employee")

    # Add 2 leaves for target employee
    l1 = Leave(
        employee_id=tgt_emp.id,
        leave_type="sick",
        from_date=date(2024, 10, 1),
        to_date=date(2024, 10, 2),
        status="approved",
        reason="Fever",
    )
    l2 = Leave(
        employee_id=tgt_emp.id,
        leave_type="casual",
        from_date=date(2024, 11, 5),
        to_date=date(2024, 11, 6),
        status="pending",
        reason="Personal work",
    )
    # Add 1 leave for normal employee (to verify no cross-leakage)
    l3 = Leave(
        employee_id=emp.id,
        leave_type="casual",
        from_date=date(2024, 10, 15),
        to_date=date(2024, 10, 16),
        status="pending",
    )
    db.add_all([l1, l2, l3])
    db.commit()

    # [1] HR can retrieve target employee's leaves -> 200
    print("\n[1] HR can retrieve target employee's leaves -> 200")
    r1 = client.get(f"/leaves/{tgt_emp.id}", headers={"Authorization": f"Bearer {hr_t}"})
    chk(r1.status_code == 200, "status 200", f"status {r1.status_code}")
    data1 = r1.json()
    chk(len(data1) == 2, "2 leave records returned", f"got {len(data1)}")
    is_owner = all(item.get("employee_id") == tgt_emp.id for item in data1)
    chk(is_owner, "All returned leaves belong to tgt_emp", "Data leakage: wrong employee leaves")

    # [2] Admin can retrieve target employee's leaves -> 200
    print("\n[2] Admin can retrieve target employee's leaves -> 200")
    r2 = client.get(f"/leaves/{tgt_emp.id}", headers={"Authorization": f"Bearer {adm_t}"})
    chk(r2.status_code == 200, "status 200", f"status {r2.status_code}")
    chk(len(r2.json()) == 2, "2 leave records returned to Admin", f"got {len(r2.json())}")

    # [3] Existing employee with no leaves returns 200 with []
    print("\n[3] Existing employee with no leaves returns [] -> 200")
    r3 = client.get(f"/leaves/{empty_emp.id}", headers={"Authorization": f"Bearer {hr_t}"})
    chk(r3.status_code == 200 and r3.json() == [], "status 200 and []", f"status {r3.status_code} data: {r3.text}")

    # [4] Non-existent employee returns 404
    print("\n[4] Non-existent employee returns 404")
    r4 = client.get("/leaves/999999", headers={"Authorization": f"Bearer {hr_t}"})
    chk(r4.status_code == 404, "status 404", f"status {r4.status_code}")
    chk(r4.json().get("detail") == "Employee not found.", "detail is 'Employee not found.'", f"Got: {r4.json()}")

    # [5] Regular employee gets 403 Forbidden
    print("\n[5] Regular employee gets 403 Forbidden")
    r5 = client.get(f"/leaves/{tgt_emp.id}", headers={"Authorization": f"Bearer {emp_t}"})
    chk(r5.status_code == 403, "status 403", f"status {r5.status_code}")

    # [6] Manager gets 403 Forbidden
    print("\n[6] Manager gets 403 Forbidden")
    r6 = client.get(f"/leaves/{tgt_emp.id}", headers={"Authorization": f"Bearer {mgr_t}"})
    chk(r6.status_code == 403, "status 403", f"status {r6.status_code}")

    # [7] Unauthenticated request gets 401 Unauthorized
    print("\n[7] Unauthenticated request gets 401 Unauthorized")
    r7 = client.get(f"/leaves/{tgt_emp.id}")
    chk(r7.status_code == 401, "status 401", f"status {r7.status_code}")

    # [8] Route ordering: GET /leaves/me is preserved and not interpreted as {employee_id}
    print("\n[8] Route ordering: GET /leaves/me still works and is not shadowed")
    r8 = client.get("/leaves/me", headers={"Authorization": f"Bearer {emp_t}"})
    chk(r8.status_code == 200, "status 200 for /leaves/me", f"status {r8.status_code}")
    chk(len(r8.json()) == 1 and r8.json()[0]["employee_id"] == emp.id, "returns emp's own leaves", f"Got: {r8.json()}")

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
