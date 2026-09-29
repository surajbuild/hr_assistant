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
    emails = ["sal.id.hr@hr.dev", "sal.id.adm@hr.dev", "sal.id.emp@hr.dev", "sal.id.tgt@hr.dev"]
    codes = ["SAL-ID-HR", "SAL-ID-ADM", "SAL-ID-EMP", "SAL-ID-TGT"]
    
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
    print("  GET /salary/{id} - Integration Test")
    print(SEP)
    cleanup()

    _, _, hr_t = make_test_user("sal.id.hr@hr.dev", "hr", "SAL-ID-HR")
    _, _, adm_t = make_test_user("sal.id.adm@hr.dev", "admin", "SAL-ID-ADM")
    emp, _, emp_t = make_test_user("sal.id.emp@hr.dev", "employee", "SAL-ID-EMP")
    tgt_emp, _, _ = make_test_user("sal.id.tgt@hr.dev", "employee", "SAL-ID-TGT")

    # Add 2 salary records for target employee
    s1 = Salary(
        employee_id=tgt_emp.id, month=10, year=2024, gross_salary=50000, 
        pf=1800, deductions=200, overtime_amount=1000, net_salary=49000, 
        paid_at=datetime(2024, 10, 31, 10, 0, 0)
    )
    s2 = Salary(
        employee_id=tgt_emp.id, month=11, year=2024, gross_salary=50000, 
        pf=1800, deductions=200, overtime_amount=0, net_salary=48000, 
        paid_at=None
    )
    
    # Add 1 record for normal employee (to ensure no cross-leakage)
    s3 = Salary(
        employee_id=emp.id, month=10, year=2024, gross_salary=40000,
        pf=1000, deductions=0, overtime_amount=0, net_salary=39000
    )

    db.add_all([s1, s2, s3])
    db.commit()

    print("\n[1] HR can retrieve an employee's salary -> 200")
    r1 = client.get(f"/salary/{tgt_emp.id}", headers={"Authorization": f"Bearer {hr_t}"})
    chk(r1.status_code == 200, "status 200", f"status {r1.status_code}")

    print("\n[2] returned records belong to the requested employee")
    data1 = r1.json()
    chk(len(data1) == 2, "2 records returned", f"got {len(data1)}")
    is_owner = all(item["employee_id"] == tgt_emp.id for item in data1)
    chk(is_owner, "All records belong to tgt_emp", "Data leakage: wrong employee data")

    print("\n[3] Admin can retrieve an employee's salary -> 200")
    r2 = client.get(f"/salary/{tgt_emp.id}", headers={"Authorization": f"Bearer {adm_t}"})
    chk(r2.status_code == 200, "status 200", f"status {r2.status_code}")
    chk(len(r2.json()) == 2, "2 records returned", f"got {len(r2.json())}")

    print("\n[4] employee cannot access this endpoint -> 403")
    r3 = client.get(f"/salary/{tgt_emp.id}", headers={"Authorization": f"Bearer {emp_t}"})
    chk(r3.status_code == 403, "status 403", f"status {r3.status_code}")

    print("\n[5] unauthenticated request -> 401")
    r4 = client.get(f"/salary/{tgt_emp.id}")
    chk(r4.status_code == 401, "status 401", f"status {r4.status_code}")

    print("\n[6] non-existent employee -> 404")
    r5 = client.get(f"/salary/999999", headers={"Authorization": f"Bearer {hr_t}"})
    chk(r5.status_code == 404, "status 404", f"status {r5.status_code}")

    print("\n[7] existing employee with no salary records -> 200 with []")
    # Using 'emp' since it has 1 record, delete it first
    db.query(Salary).filter(Salary.employee_id == emp.id).delete()
    db.commit()
    r6 = client.get(f"/salary/{emp.id}", headers={"Authorization": f"Bearer {hr_t}"})
    chk(r6.status_code == 200 and r6.json() == [], "status 200 and []", f"status {r6.status_code} data: {r6.text}")

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
