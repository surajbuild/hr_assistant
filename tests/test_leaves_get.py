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

TEST_EMP_CODE_1 = "L-GET-001"
TEST_EMAIL_1 = "get.leave1@hr.dev"

TEST_EMP_CODE_2 = "L-GET-002"
TEST_EMAIL_2 = "get.leave2@hr.dev"

def cleanup():
    for email in [TEST_EMAIL_1, TEST_EMAIL_2]:
        u = db.query(User).filter(User.email == email).first()
        if u:
            db.query(Leave).filter(Leave.employee_id == u.employee_id).delete()
            db.delete(u)
    for code in [TEST_EMP_CODE_1, TEST_EMP_CODE_2]:
        e = db.query(Employee).filter(Employee.employee_code == code).first()
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
    print("  GET /leaves/me - Integration Test")
    print(SEP)
    cleanup()

    # Setup User 1 (Has leaves)
    emp1 = create_employee(
        db, employee_code=TEST_EMP_CODE_1, name="Leave Getter 1", 
        department="Test", designation="Tester", joining_date=date(2024, 1, 1)
    )
    user1 = create_user(db, employee_id=emp1.id, email=TEST_EMAIL_1, password_hash="hash", role="employee")
    token1 = create_access_token(user_id=user1.id, role=user1.role)

    # Insert 2 leaves for User 1
    leave1 = Leave(employee_id=emp1.id, leave_type="sick", from_date=date(2024, 10, 1), to_date=date(2024, 10, 2), status="pending")
    leave2 = Leave(employee_id=emp1.id, leave_type="casual", from_date=date(2024, 11, 1), to_date=date(2024, 11, 2), status="approved")
    db.add(leave1)
    db.add(leave2)
    db.commit()

    # Setup User 2 (No leaves)
    emp2 = create_employee(
        db, employee_code=TEST_EMP_CODE_2, name="Leave Getter 2", 
        department="Test", designation="Tester", joining_date=date(2024, 1, 1)
    )
    user2 = create_user(db, employee_id=emp2.id, email=TEST_EMAIL_2, password_hash="hash", role="employee")
    token2 = create_access_token(user_id=user2.id, role=user2.role)

    print("\n[1] authenticated employee gets their leaves -> 200")
    r1 = client.get("/leaves/me", headers={"Authorization": f"Bearer {token1}"})
    chk(r1.status_code == 200, "status 200", f"status {r1.status_code}")

    print("\n[2] multiple leaves are returned correctly & belong only to authenticated employee")
    data1 = r1.json()
    chk(len(data1) == 2, "2 leaves returned", f"returned {len(data1)}")
    is_owner = all(item.get("employee_id") == emp1.id for item in data1)
    chk(is_owner, "All leaves belong to user1", "Ownership mismatch")

    print("\n[3] employee with no leaves gets [] -> 200")
    r2 = client.get("/leaves/me", headers={"Authorization": f"Bearer {token2}"})
    chk(r2.status_code == 200 and r2.json() == [], "status 200 and empty list", f"status {r2.status_code}, data {r2.text}")

    print("\n[4] missing token -> 401")
    r3 = client.get("/leaves/me")
    chk(r3.status_code == 401, "401 returned", f"status {r3.status_code}")

    print("\n[5] invalid token -> 401")
    r4 = client.get("/leaves/me", headers={"Authorization": "Bearer invalid.token"})
    chk(r4.status_code == 401, "401 returned", f"status {r4.status_code}")

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
