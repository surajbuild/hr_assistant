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

TEST_EMP_CODE = "L-EMP-001"
TEST_EMAIL = "leave.test@hr.dev"

def cleanup():
    u = db.query(User).filter(User.email == TEST_EMAIL).first()
    if u:
        db.query(Leave).filter(Leave.employee_id == u.employee_id).delete()
        db.delete(u)
    e = db.query(Employee).filter(Employee.employee_code == TEST_EMP_CODE).first()
    if e: db.delete(e)
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

try:
    print(SEP)
    print("  POST /leaves - Integration Test")
    print(SEP)
    cleanup()

    # 1. Setup Data
    emp = create_employee(
        db, employee_code=TEST_EMP_CODE, name="Leave Tester", 
        department="Test", designation="Tester", joining_date=date(2024, 1, 1)
    )
    user = create_user(db, employee_id=emp.id, email=TEST_EMAIL, password_hash="hash", role="employee")
    valid_token = create_access_token(user_id=user.id, role=user.role)

    print("\n[1] authenticated employee can create a leave request -> 201")
    payload = {
        "leave_type": "sick",
        "start_date": "2024-10-01",
        "end_date": "2024-10-02",
        "reason": "Feeling unwell"
    }
    r1 = client.post("/leaves", json=payload, headers={"Authorization": f"Bearer {valid_token}"})
    chk(r1.status_code == 201, "status 201", f"status {r1.status_code} - {r1.text}")

    print("\n[2] created leave belongs to authenticated employee and status is pending")
    data = r1.json()
    is_owner = data.get("employee_id") == emp.id
    is_pending = data.get("status") == "pending"
    chk(is_owner and is_pending, "Owner matches, status pending", f"Data: {data}")

    print("\n[3] missing token -> 401")
    r2 = client.post("/leaves", json=payload)
    chk(r2.status_code == 401, "401 returned", f"status {r2.status_code}")

    print("\n[4] invalid token -> 401")
    r3 = client.post("/leaves", json=payload, headers={"Authorization": "Bearer invalid.token"})
    chk(r3.status_code == 401, "401 returned", f"status {r3.status_code}")

    print("\n[5] start_date after end_date -> validation error (422)")
    bad_payload = payload.copy()
    bad_payload["start_date"] = "2024-10-05"
    r4 = client.post("/leaves", json=bad_payload, headers={"Authorization": f"Bearer {valid_token}"})
    chk(r4.status_code == 422, "422 returned", f"status {r4.status_code} - {r4.text}")

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
