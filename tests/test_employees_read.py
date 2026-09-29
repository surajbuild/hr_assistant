import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from datetime import date
from fastapi.testclient import TestClient

from app.main import app
from app.database.connection import SessionLocal
from app.database.models import Employee, User
from app.database.queries import create_employee, create_user
from app.utils.security import create_access_token

client = TestClient(app)
db = SessionLocal()

def cleanup():
    emails = ["read.hr@hr.dev", "read.admin@hr.dev", "read.emp@hr.dev", "read.tgt@hr.dev"]
    codes = ["READ-HR", "READ-ADM", "READ-EMP", "READ-TGT"]
    
    users = db.query(User).filter(User.email.in_(emails)).all()
    for u in users:
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
        department="Operations", designation=f"Officer {role}", joining_date=date(2024, 1, 15)
    )
    user = create_user(db, employee_id=emp.id, email=email, password_hash="secret_bcrypt_hash", role=role)
    token = create_access_token(user_id=user.id, role=user.role)
    return emp, user, token

try:
    print(SEP)
    print("  GET /employees & GET /employees/{id} - Integration Test")
    print(SEP)
    cleanup()

    _, _, hr_t = make_test_user("read.hr@hr.dev", "hr", "READ-HR", "HR Officer")
    _, _, adm_t = make_test_user("read.admin@hr.dev", "admin", "READ-ADM", "Admin Officer")
    emp, _, emp_t = make_test_user("read.emp@hr.dev", "employee", "READ-EMP", "Normal Employee")
    tgt_emp, _, _ = make_test_user("read.tgt@hr.dev", "employee", "READ-TGT", "Target Employee")

    # -----------------------------------------------------------------------
    # Part 1: GET /employees (List all employees)
    # -----------------------------------------------------------------------
    print("\n--- Testing GET /employees ---")

    print("\n[1] HR can access employee list -> 200")
    r1 = client.get("/employees", headers={"Authorization": f"Bearer {hr_t}"})
    chk(r1.status_code == 200, "status 200", f"status {r1.status_code}")
    data1 = r1.json()
    chk(isinstance(data1, list) and len(data1) >= 4, "returns list with employees", f"Got: {type(data1)}")

    print("\n[2] Admin can access employee list -> 200")
    r2 = client.get("/employees", headers={"Authorization": f"Bearer {adm_t}"})
    chk(r2.status_code == 200, "status 200", f"status {r2.status_code}")

    print("\n[3] regular employee cannot access employee list -> 403")
    r3 = client.get("/employees", headers={"Authorization": f"Bearer {emp_t}"})
    chk(r3.status_code == 403, "status 403", f"status {r3.status_code}")

    print("\n[4] unauthenticated request -> 401")
    r4 = client.get("/employees")
    chk(r4.status_code == 401, "status 401", f"status {r4.status_code}")

    print("\n[5] sensitive authentication fields are NOT exposed in employee list")
    for item in data1:
        has_hash = "password_hash" in item or "password" in item
        has_google = "google_id" in item
        has_token = "token" in item or "secret" in item
        if has_hash or has_google or has_token:
            chk(False, "", "Sensitive field exposed in response!")
            break
    else:
        chk(True, "no sensitive authentication fields exposed in employee list", "")

    # -----------------------------------------------------------------------
    # Part 2: GET /employees/{employee_id} (Specific employee)
    # -----------------------------------------------------------------------
    print("\n--- Testing GET /employees/{employee_id} ---")

    print("\n[6] HR can retrieve specific employee -> 200 with correct data")
    r5 = client.get(f"/employees/{tgt_emp.id}", headers={"Authorization": f"Bearer {hr_t}"})
    chk(r5.status_code == 200, "status 200", f"status {r5.status_code}")
    tgt_data = r5.json()
    chk(
        tgt_data.get("id") == tgt_emp.id 
        and tgt_data.get("employee_code") == "READ-TGT" 
        and tgt_data.get("name") == "Target Employee",
        "employee data matches database",
        f"Data mismatch: {tgt_data}"
    )

    print("\n[7] Admin can retrieve specific employee -> 200")
    r6 = client.get(f"/employees/{tgt_emp.id}", headers={"Authorization": f"Bearer {adm_t}"})
    chk(r6.status_code == 200, "status 200", f"status {r6.status_code}")

    print("\n[8] regular employee cannot access specific employee endpoint -> 403")
    r7 = client.get(f"/employees/{tgt_emp.id}", headers={"Authorization": f"Bearer {emp_t}"})
    chk(r7.status_code == 403, "status 403", f"status {r7.status_code}")

    print("\n[9] unauthenticated request -> 401")
    r8 = client.get(f"/employees/{tgt_emp.id}")
    chk(r8.status_code == 401, "status 401", f"status {r8.status_code}")

    print("\n[10] non-existent employee -> 404")
    r9 = client.get("/employees/999999", headers={"Authorization": f"Bearer {hr_t}"})
    chk(r9.status_code == 404, "status 404", f"status {r9.status_code}")

    print("\n[11] sensitive authentication fields are NOT exposed in single employee response")
    chk(
        "password_hash" not in tgt_data 
        and "password" not in tgt_data 
        and "google_id" not in tgt_data,
        "no sensitive authentication fields exposed in employee response",
        f"Sensitive fields detected in: {tgt_data}"
    )

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
