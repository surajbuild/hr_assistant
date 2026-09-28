import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from datetime import date, timedelta
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models import Employee, User, UserStatus
from app.database.queries import create_employee, create_user
from app.utils.security import hash_password, create_access_token
from app.utils.dependencies import get_current_user

app = FastAPI()

@app.get("/test-protected")
def protected_route(user: User = Depends(get_current_user)):
    return {"user_id": user.id, "email": user.email}

client = TestClient(app)
db = SessionLocal()

TEST_EMP_CODE = "DEP-EMP-001"
TEST_EMAIL = "dep.valid@hr.dev"
INACTIVE_CODE = "DEP-EMP-002"
INACTIVE_EMAIL = "dep.inactive@hr.dev"
DELETED_CODE = "DEP-EMP-003"
DELETED_EMAIL = "dep.deleted@hr.dev"

def cleanup():
    for email in [TEST_EMAIL, INACTIVE_EMAIL, DELETED_EMAIL]:
        u = db.query(User).filter(User.email == email).first()
        if u: db.delete(u)
    for code in [TEST_EMP_CODE, INACTIVE_CODE, DELETED_CODE]:
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
    print("  get_current_user() Dependency Test")
    print(SEP)
    cleanup()

    # 1. Setup Data
    e1 = create_employee(db, employee_code=TEST_EMP_CODE, name="Valid", department="QA", designation="T", joining_date=date(2024,1,1))
    u1 = create_user(db, employee_id=e1.id, email=TEST_EMAIL, password_hash="hash", role="employee")
    valid_token = create_access_token(user_id=u1.id, role=u1.role)

    e2 = create_employee(db, employee_code=INACTIVE_CODE, name="Inactive", department="QA", designation="T", joining_date=date(2024,1,1))
    u2 = create_user(db, employee_id=e2.id, email=INACTIVE_EMAIL, password_hash="hash", status=UserStatus.INACTIVE.value, role="employee")
    inactive_token = create_access_token(user_id=u2.id, role=u2.role)

    e3 = create_employee(db, employee_code=DELETED_CODE, name="Deleted", department="QA", designation="T", joining_date=date(2024,1,1))
    u3 = create_user(db, employee_id=e3.id, email=DELETED_EMAIL, password_hash="hash", role="employee")
    deleted_token = create_access_token(user_id=u3.id, role=u3.role)
    # delete u3
    db.delete(u3)
    db.delete(e3)
    db.commit()

    expired_token = create_access_token(user_id=u1.id, role=u1.role, expires_delta=timedelta(seconds=-10))

    # Tests
    print("\n[1] valid Bearer token -> current user returned")
    r1 = client.get("/test-protected", headers={"Authorization": f"Bearer {valid_token}"})
    chk(r1.status_code == 200 and r1.json().get("email") == TEST_EMAIL, "User authenticated", "status " + str(r1.status_code) + " " + r1.text)

    print("\n[2] missing Authorization header -> 401")
    r2 = client.get("/test-protected")
    chk(r2.status_code == 401, "401 missing auth", "status " + str(r2.status_code))

    print("\n[3] malformed Authorization header -> 401")
    r3 = client.get("/test-protected", headers={"Authorization": f"Basic {valid_token}"})
    chk(r3.status_code == 401, "401 malformed header", "status " + str(r3.status_code))

    print("\n[4] invalid JWT -> 401")
    r4 = client.get("/test-protected", headers={"Authorization": "Bearer invalid.jwt.token"})
    chk(r4.status_code == 401, "401 invalid JWT", "status " + str(r4.status_code))

    print("\n[5] expired JWT -> 401")
    r5 = client.get("/test-protected", headers={"Authorization": f"Bearer {expired_token}"})
    chk(r5.status_code == 401, "401 expired JWT", "status " + str(r5.status_code))

    print("\n[6] token for non-existent user -> 401")
    r6 = client.get("/test-protected", headers={"Authorization": f"Bearer {deleted_token}"})
    chk(r6.status_code == 401, "401 non-existent user", "status " + str(r6.status_code))

    print("\n[7] inactive user -> 403")
    r7 = client.get("/test-protected", headers={"Authorization": f"Bearer {inactive_token}"})
    chk(r7.status_code == 403, "403 inactive user", "status " + str(r7.status_code))

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
