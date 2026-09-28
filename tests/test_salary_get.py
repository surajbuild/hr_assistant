import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from datetime import date, datetime
from fastapi.testclient import TestClient

from app.main import app
from app.database.connection import SessionLocal
from app.database.models import Employee, User, Salary
from app.database.queries import create_employee, create_user
from app.utils.security import create_access_token

client = TestClient(app)
db = SessionLocal()

def cleanup():
    emails = ["sal.emp@hr.dev", "sal.empty@hr.dev"]
    codes = ["SAL-EMP", "SAL-EMPTY"]
    
    users = db.query(User).filter(User.email.in_(emails)).all()
    for u in users:
        db.query(Salary).filter(Salary.employee_id == u.employee_id).delete()
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
    print("  GET /salary/me - Integration Test")
    print(SEP)
    cleanup()

    emp, _, emp_t = make_test_user("sal.emp@hr.dev", "employee", "SAL-EMP")
    empty_emp, _, empty_t = make_test_user("sal.empty@hr.dev", "employee", "SAL-EMPTY")

    # Add 2 salary records for emp
    s1 = Salary(
        employee_id=emp.id, month=10, year=2024, gross_salary=50000, 
        pf=1800, deductions=200, overtime_amount=1000, net_salary=49000, 
        paid_at=datetime(2024, 10, 31, 10, 0, 0)
    )
    s2 = Salary(
        employee_id=emp.id, month=11, year=2024, gross_salary=50000, 
        pf=1800, deductions=200, overtime_amount=0, net_salary=48000, 
        paid_at=None
    )
    # Add 1 salary record for someone else (empty_emp in this case just to have a rogue record)
    s3 = Salary(
        employee_id=empty_emp.id, month=10, year=2024, gross_salary=60000, 
        pf=2000, deductions=0, overtime_amount=0, net_salary=58000, 
        paid_at=None
    )

    db.add_all([s1, s2, s3])
    db.commit()

    print("\n[1] authenticated employee gets their salary records -> 200")
    r1 = client.get("/salary/me", headers={"Authorization": f"Bearer {emp_t}"})
    chk(r1.status_code == 200, "status 200", f"status {r1.status_code}")

    print("\n[2] returned records belong only to the authenticated employee")
    data1 = r1.json()
    chk(len(data1) == 2, "2 records returned", f"got {len(data1)}")
    is_owner = all(item["employee_id"] == emp.id for item in data1)
    chk(is_owner, "All records belong to emp", "Security breach: wrong employee data")

    # Just double-checking the rogue record was NOT returned
    has_rogue = any(item["employee_id"] == empty_emp.id for item in data1)
    chk(not has_rogue, "Other employee's salary is NEVER returned", "Security breach!")

    print("\n[3] employee with no salary records gets [] -> 200 (using empty_emp's rogue record, let's delete it first)")
    # Delete the rogue record so empty_emp truly has no salary
    db.query(Salary).filter(Salary.employee_id == empty_emp.id).delete()
    db.commit()

    r2 = client.get("/salary/me", headers={"Authorization": f"Bearer {empty_t}"})
    chk(r2.status_code == 200 and r2.json() == [], "status 200 and []", f"status {r2.status_code} data: {r2.text}")

    print("\n[4] missing token -> 401")
    r3 = client.get("/salary/me")
    chk(r3.status_code == 401, "401 returned", f"status {r3.status_code}")

    print("\n[5] invalid token -> 401")
    r4 = client.get("/salary/me", headers={"Authorization": "Bearer badtoken"})
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
