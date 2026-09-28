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
    emails = ["patch.hr@hr.dev", "patch.mgr@hr.dev", "patch.emp@hr.dev"]
    codes = ["P-HR", "P-MGR", "P-EMP"]
    
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
    print("  PATCH /leaves/{id}/status - Integration Test")
    print(SEP)
    cleanup()

    _, hr_u, hr_t = make_test_user("patch.hr@hr.dev", "hr", "P-HR")
    _, mgr_u, mgr_t = make_test_user("patch.mgr@hr.dev", "manager", "P-MGR")
    emp, emp_u, emp_t = make_test_user("patch.emp@hr.dev", "employee", "P-EMP")

    l1 = Leave(employee_id=emp.id, leave_type="sick", from_date=date(2024, 1, 1), to_date=date(2024, 1, 2), status="pending")
    l2 = Leave(employee_id=emp.id, leave_type="casual", from_date=date(2024, 2, 1), to_date=date(2024, 2, 2), status="pending")
    l3 = Leave(employee_id=emp.id, leave_type="casual", from_date=date(2024, 3, 1), to_date=date(2024, 3, 2), status="approved")
    db.add_all([l1, l2, l3])
    db.commit()

    print("\n[1] HR approves pending leave -> 200")
    r1 = client.patch(f"/leaves/{l1.id}/status", json={"status": "approved"}, headers={"Authorization": f"Bearer {hr_t}"})
    chk(r1.status_code == 200, "status 200", f"status {r1.status_code}")
    db.commit() # Reset MySQL REPEATABLE READ snapshot
    l1 = db.query(Leave).filter(Leave.id == l1.id).first()
    chk(l1.status == "approved" and l1.approved_by == hr_u.id, "Status approved and approved_by matches HR", "DB state incorrect")

    print("\n[2] Manager rejects pending leave -> 200")
    r2 = client.patch(f"/leaves/{l2.id}/status", json={"status": "rejected"}, headers={"Authorization": f"Bearer {mgr_t}"})
    chk(r2.status_code == 200, "status 200", f"status {r2.status_code}")
    db.commit()
    l2 = db.query(Leave).filter(Leave.id == l2.id).first()
    chk(l2.status == "rejected" and l2.approved_by == mgr_u.id, "Status rejected and approved_by matches Manager", "DB state incorrect")

    print("\n[3] employee cannot approve/reject -> 403")
    r3 = client.patch(f"/leaves/{l2.id}/status", json={"status": "approved"}, headers={"Authorization": f"Bearer {emp_t}"})
    chk(r3.status_code == 403, "status 403", f"status {r3.status_code}")

    print("\n[4] unauthenticated request -> 401")
    r4 = client.patch(f"/leaves/{l1.id}/status", json={"status": "approved"})
    chk(r4.status_code == 401, "status 401", f"status {r4.status_code}")

    print("\n[5] non-existent leave -> 404")
    r5 = client.patch(f"/leaves/999999/status", json={"status": "approved"}, headers={"Authorization": f"Bearer {hr_t}"})
    chk(r5.status_code == 404, "status 404", f"status {r5.status_code}")

    print("\n[6] already processed leave cannot be processed again -> 400")
    r6 = client.patch(f"/leaves/{l3.id}/status", json={"status": "rejected"}, headers={"Authorization": f"Bearer {hr_t}"})
    chk(r6.status_code == 400, "status 400", f"status {r6.status_code} text: {r6.text}")

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
