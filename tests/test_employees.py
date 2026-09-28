import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database.connection import SessionLocal
from app.database.models import Employee, User, UserStatus
from app.database.queries import create_employee, create_user
from app.utils.security import hash_password, create_access_token

client = TestClient(app)
db = SessionLocal()

TEST_EMP_CODE = "EMP-TEST-001"
TEST_EMAIL = "emp.test@hr.dev"

def cleanup():
    u = db.query(User).filter(User.email == TEST_EMAIL).first()
    if u: db.delete(u)
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
    print("  GET /employees/me - Integration Test")
    print(SEP)
    cleanup()

    # 1. Setup Data
    emp = create_employee(
        db, employee_code=TEST_EMP_CODE, name="John Doe", 
        department="Engineering", designation="Developer", joining_date=date(2024, 1, 1)
    )
    user = create_user(db, employee_id=emp.id, email=TEST_EMAIL, password_hash="hash", role="employee")
    valid_token = create_access_token(user_id=user.id, role=user.role)

    print("\n[1] authenticated user can access /employees/me")
    r1 = client.get("/employees/me", headers={"Authorization": f"Bearer {valid_token}"})
    chk(r1.status_code == 200, "status 200", "status " + str(r1.status_code) + " " + r1.text)

    print("\n[2] returned employee belongs to the authenticated user")
    data = r1.json()
    chk(data.get("employee_code") == TEST_EMP_CODE and data.get("name") == "John Doe", "Data matches", "Mismatch: " + str(data))

    print("\n[3] missing token -> 401")
    r2 = client.get("/employees/me")
    chk(r2.status_code == 401, "401 returned", "status " + str(r2.status_code))

    print("\n[4] invalid token -> 401")
    r3 = client.get("/employees/me", headers={"Authorization": "Bearer invalid.token.xyz"})
    chk(r3.status_code == 401, "401 returned", "status " + str(r3.status_code))

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
