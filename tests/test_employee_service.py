import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from datetime import date
from app.database.connection import SessionLocal
from app.database.models import Employee, User
from app.database.queries import create_employee, create_user
from app.services import employee_service
from app.services.employee_service import EmployeeNotFoundError

db = SessionLocal()

TEST_EMP_CODE_SVC_1 = "SVC-EMP-001"
TEST_EMAIL_SVC_1 = "svc.emp1@hr.dev"

TEST_EMP_CODE_SVC_2 = "SVC-EMP-002"
TEST_EMAIL_SVC_2 = "svc.emp2@hr.dev"

def cleanup():
    for email in [TEST_EMAIL_SVC_1, TEST_EMAIL_SVC_2]:
        u = db.query(User).filter(User.email == email).first()
        if u:
            db.delete(u)
    for code in [TEST_EMP_CODE_SVC_1, TEST_EMP_CODE_SVC_2]:
        e = db.query(Employee).filter(Employee.employee_code == code).first()
        if e:
            db.delete(e)
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
    print("  Employee Service Layer - Unit & Business Logic Test")
    print(SEP)
    cleanup()

    # Create test employees
    emp1 = create_employee(
        db, employee_code=TEST_EMP_CODE_SVC_1, name="Employee Svc User 1",
        department="Engineering", designation="Engineer", joining_date=date(2024, 1, 1)
    )
    user1 = create_user(db, employee_id=emp1.id, email=TEST_EMAIL_SVC_1, password_hash="hash", role="employee")

    emp2 = create_employee(
        db, employee_code=TEST_EMP_CODE_SVC_2, name="Employee Svc User 2",
        department="HR", designation="HR Officer", joining_date=date(2024, 2, 1)
    )
    user2 = create_user(db, employee_id=emp2.id, email=TEST_EMAIL_SVC_2, password_hash="hash", role="hr")

    # [1] get_all_employees returns all employees
    print("\n[1] get_all_employees returns persisted employees")
    all_emps = employee_service.get_all_employees(db)
    emp_ids = [e.id for e in all_emps]
    chk(emp1.id in emp_ids and emp2.id in emp_ids, "both test employees present in get_all_employees", f"Got IDs: {emp_ids}")

    # [2] get_employee_by_id returns specific employee
    print("\n[2] get_employee_by_id returns correct employee")
    fetched1 = employee_service.get_employee_by_id(db, emp1.id)
    chk(fetched1.id == emp1.id and fetched1.name == "Employee Svc User 1", "fetched1 matches emp1", "Mismatch")

    # [3] get_employee_by_id raises EmployeeNotFoundError for non-existent employee
    print("\n[3] get_employee_by_id raises EmployeeNotFoundError for missing ID")
    missing_raised = False
    try:
        employee_service.get_employee_by_id(db, 999999)
    except EmployeeNotFoundError as exc:
        missing_raised = True
        chk("Employee not found." in str(exc), "error message matches", f"Got: {exc}")
    chk(missing_raised, "EmployeeNotFoundError raised", "Did not raise EmployeeNotFoundError")

    # [4] get_my_profile returns employee associated with user
    print("\n[4] get_my_profile returns user's employee profile")
    profile = employee_service.get_my_profile(user1)
    chk(profile.id == emp1.id, "profile.id matches user1.employee_id", "Mismatch")

    # [5] get_my_profile raises EmployeeNotFoundError when user has no linked employee
    print("\n[5] get_my_profile raises EmployeeNotFoundError when no employee linked")
    user_no_emp = User(id=8888, employee_id=8888, email="orphan@hr.dev", role="employee", status="active")
    # user_no_emp has no linked employee relationship object
    orphan_raised = False
    try:
        employee_service.get_my_profile(user_no_emp)
    except EmployeeNotFoundError:
        orphan_raised = True
    chk(orphan_raised, "EmployeeNotFoundError raised for orphan user", "Did not raise EmployeeNotFoundError")

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
