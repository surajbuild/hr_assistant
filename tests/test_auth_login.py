import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")
from datetime import date
from fastapi.testclient import TestClient
from app.main import app
from app.database.connection import SessionLocal
from app.database.models import Employee, User, UserStatus
from app.database.queries import create_employee, create_user
from app.utils.security import hash_password, decode_access_token

SEP = "-" * 55
passed = 0
failed = 0
TEST_EMP_CODE  = "AUTH-TEST-EMP-001"
TEST_EMAIL     = "auth.test@hr-assistant.dev"
TEST_PASSWORD  = "CorrectPassword@99"
INACTIVE_EMAIL = "inactive.auth@hr-assistant.dev"
INACTIVE_CODE  = "AUTH-TEST-EMP-002"

db = SessionLocal()

def cleanup():
    for email in [TEST_EMAIL, INACTIVE_EMAIL]:
        u = db.query(User).filter(User.email == email).first()
        if u: db.delete(u)
    for code in [TEST_EMP_CODE, INACTIVE_CODE]:
        e = db.query(Employee).filter(Employee.employee_code == code).first()
        if e: db.delete(e)
    db.commit()
    print("  [cleanup] Test rows removed.")

def chk(label, ok, ok_msg, fail_msg):
    global passed, failed
    if ok:
        print("    PASS - " + ok_msg); passed += 1
    else:
        print("    FAIL - " + fail_msg); failed += 1

client = TestClient(app)
try:
    print(SEP)
    print("  POST /auth/login - Integration Test")
    print(SEP)
    print("\n[setup] Creating test employee + user...")
    cleanup()
    emp = create_employee(db, employee_code=TEST_EMP_CODE, name="Auth Test",
        department="QA", designation="Tester", joining_date=date(2024, 1, 1))
    user = create_user(db, employee_id=emp.id, email=TEST_EMAIL,
        password_hash=hash_password(TEST_PASSWORD), role="hr")
    emp2 = create_employee(db, employee_code=INACTIVE_CODE, name="Inactive",
        department="QA", designation="Tester", joining_date=date(2024, 1, 1))
    create_user(db, employee_id=emp2.id, email=INACTIVE_EMAIL,
        password_hash=hash_password(TEST_PASSWORD),
        status=UserStatus.INACTIVE.value, role="employee")
    print("  Setup OK - user.id=" + str(user.id) + " role=" + user.role)

    print("\n[1] Valid credentials - 200")
    r = client.post("/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD})
    chk("status", r.status_code == 200, "status 200", "status " + str(r.status_code) + " " + r.text)

    body = r.json()
    print("\n[2] Response has access_token")
    chk("token", bool(body.get("access_token")), "access_token present (len=" + str(len(body.get("access_token",""))) + ")", "missing")

    print("\n[3] token_type is bearer")
    chk("type", body.get("token_type") == "bearer", "bearer", "got " + str(body.get("token_type")))

    print("\n[4] Token decodes successfully")
    td = None
    try:
        td = decode_access_token(body["access_token"])
        print("    PASS - decoded OK"); passed += 1
    except Exception as e:
        print("    FAIL - " + str(e)); failed += 1

    print("\n[5] Decoded user_id matches DB")
    chk("uid", td and td.user_id == user.id, "user_id=" + str(user.id), "mismatch")

    print("\n[6] Decoded role is hr")
    chk("role", td and td.role == "hr", "role=hr", "wrong role " + str(getattr(td,"role",None)))

    print("\n[7] Wrong password - 401")
    r2 = client.post("/auth/login", json={"email": TEST_EMAIL, "password": "WrongPass!"})
    chk("wp", r2.status_code == 401, "401 returned", "status " + str(r2.status_code))

    print("\n[8] Unknown email - 401")
    r3 = client.post("/auth/login", json={"email": "nobody@hr.dev", "password": TEST_PASSWORD})
    chk("unk", r3.status_code == 401, "401 returned", "status " + str(r3.status_code))

    print("\n[9] Inactive user - 403")
    r4 = client.post("/auth/login", json={"email": INACTIVE_EMAIL, "password": TEST_PASSWORD})
    chk("inactive", r4.status_code == 403, "403 returned", "status " + str(r4.status_code) + " " + r4.text)

    print("\n[10] Missing password field - 422")
    r5 = client.post("/auth/login", json={"email": TEST_EMAIL})
    chk("422", r5.status_code == 422, "422 returned", "status " + str(r5.status_code))

except Exception as exc:
    print("\n  EXCEPTION: " + str(exc))
    db.rollback(); failed += 1
    raise
finally:
    print("\n[cleanup] Removing test data...")
    cleanup(); db.close()
    print(SEP)
    print("  Results: " + str(passed) + " passed, " + str(failed) + " failed")
    print(SEP)
    if failed: sys.exit(1)
