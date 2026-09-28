import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from datetime import date
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models import Employee, User
from app.database.queries import create_employee, create_user
from app.utils.security import create_access_token
from app.utils.dependencies import require_role

# Dummy routes for testing
app = FastAPI()

@app.get("/hr-only")
def hr_route(user: User = Depends(require_role("hr"))):
    return {"status": "ok"}

@app.get("/hr-or-admin")
def hr_admin_route(user: User = Depends(require_role("hr", "admin"))):
    return {"status": "ok"}

client = TestClient(app)
db = SessionLocal()

def make_test_user(email: str, role: str, emp_code: str):
    emp = create_employee(
        db, employee_code=emp_code, name=f"Test {role}", 
        department="Test", designation="Tester", joining_date=date(2024, 1, 1)
    )
    user = create_user(db, employee_id=emp.id, email=email, password_hash="hash", role=role)
    token = create_access_token(user_id=user.id, role=user.role)
    return emp, user, token

def cleanup():
    emails = ["hr@test.dev", "admin@test.dev", "emp@test.dev", "mgr@test.dev"]
    codes = ["R-HR", "R-ADM", "R-EMP", "R-MGR"]
    for email in emails:
        u = db.query(User).filter(User.email == email).first()
        if u: db.delete(u)
    for code in codes:
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
    print("  require_role() Integration Test")
    print(SEP)
    cleanup()

    print("\n[setup] Creating test users...")
    _, _, hr_token = make_test_user("hr@test.dev", "hr", "R-HR")
    _, _, admin_token = make_test_user("admin@test.dev", "admin", "R-ADM")
    _, _, emp_token = make_test_user("emp@test.dev", "employee", "R-EMP")
    _, _, mgr_token = make_test_user("mgr@test.dev", "manager", "R-MGR")

    print("\n[1] HR user accessing an HR-protected route -> 200")
    r1 = client.get("/hr-only", headers={"Authorization": f"Bearer {hr_token}"})
    chk(r1.status_code == 200, "status 200", f"status {r1.status_code}")

    print("\n[2] Admin accessing an HR/admin-protected route -> 200")
    r2 = client.get("/hr-or-admin", headers={"Authorization": f"Bearer {admin_token}"})
    chk(r2.status_code == 200, "status 200", f"status {r2.status_code}")

    print("\n[3] Employee accessing an HR-protected route -> 403")
    r3 = client.get("/hr-only", headers={"Authorization": f"Bearer {emp_token}"})
    chk(r3.status_code == 403, "status 403", f"status {r3.status_code}")

    print("\n[4] Manager accessing an HR-protected route -> 403")
    r4 = client.get("/hr-only", headers={"Authorization": f"Bearer {mgr_token}"})
    chk(r4.status_code == 403, "status 403", f"status {r4.status_code}")

    print("\n[5] unauthenticated request -> 401")
    r5 = client.get("/hr-only")
    chk(r5.status_code == 401, "status 401", f"status {r5.status_code}")

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
