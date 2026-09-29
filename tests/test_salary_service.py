import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from datetime import date, datetime
from app.database.connection import SessionLocal
from app.database.models import Employee, User, Salary
from app.database.queries import create_employee, create_user
from app.services import salary_service
from app.services.salary_service import EmployeeNotFoundError, InvalidSalaryFilterError

db = SessionLocal()

TEST_EMP_CODE_SVC_1 = "SVC-SAL-001"
TEST_EMAIL_SVC_1 = "svc.sal1@hr.dev"

TEST_EMP_CODE_SVC_2 = "SVC-SAL-002"
TEST_EMAIL_SVC_2 = "svc.sal2@hr.dev"

def cleanup():
    for email in [TEST_EMAIL_SVC_1, TEST_EMAIL_SVC_2]:
        u = db.query(User).filter(User.email == email).first()
        if u:
            db.query(Salary).filter(Salary.employee_id == u.employee_id).delete()
            db.delete(u)
    for code in [TEST_EMP_CODE_SVC_1, TEST_EMP_CODE_SVC_2]:
        e = db.query(Employee).filter(Employee.employee_code == code).first()
        if e:
            db.query(Salary).filter(Salary.employee_id == e.id).delete()
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
    print("  Salary Service Layer - Unit & Business Logic Test")
    print(SEP)
    cleanup()

    # Create test employee 1 (with salaries)
    emp1 = create_employee(
        db, employee_code=TEST_EMP_CODE_SVC_1, name="Salary Svc User 1",
        department="Engineering", designation="Engineer", joining_date=date(2024, 1, 1)
    )
    user1 = create_user(db, employee_id=emp1.id, email=TEST_EMAIL_SVC_1, password_hash="hash", role="employee")

    # Create test employee 2 (without salaries)
    emp2 = create_employee(
        db, employee_code=TEST_EMP_CODE_SVC_2, name="Salary Svc User 2",
        department="Engineering", designation="Engineer", joining_date=date(2024, 1, 1)
    )
    user2 = create_user(db, employee_id=emp2.id, email=TEST_EMAIL_SVC_2, password_hash="hash", role="employee")

    # Insert 2 salary records for emp1
    s1 = Salary(
        employee_id=emp1.id, month=10, year=2024, gross_salary=50000.0,
        pf=1800.0, deductions=200.0, overtime_amount=1000.0, net_salary=49000.0,
        paid_at=datetime(2024, 10, 31, 10, 0, 0)
    )
    s2 = Salary(
        employee_id=emp1.id, month=11, year=2024, gross_salary=50000.0,
        pf=1800.0, deductions=200.0, overtime_amount=0.0, net_salary=48000.0,
        paid_at=None
    )
    db.add_all([s1, s2])
    db.commit()

    # [1] get_salary_by_employee_id
    print("\n[1] get_salary_by_employee_id returns records for emp1")
    recs1 = salary_service.get_salary_by_employee_id(db, emp1.id)
    chk(len(recs1) == 2, "recs1 has 2 records", f"Got {len(recs1)}")
    chk(all(r.employee_id == emp1.id for r in recs1), "all records belong to emp1", "Ownership mismatch")

    # [2] get_salary_by_employee_id for empty employee returns []
    print("\n[2] get_salary_by_employee_id for empty employee returns []")
    recs2 = salary_service.get_salary_by_employee_id(db, emp2.id)
    chk(recs2 == [], "empty employee returns []", f"Got {recs2}")

    # [3] get_my_salary respects data isolation
    print("\n[3] get_my_salary returns records only for authenticated employee")
    my_recs = salary_service.get_my_salary(db, emp1.id)
    chk(len(my_recs) == 2, "my_recs has 2 records", f"Got {len(my_recs)}")
    chk(all(r.employee_id == emp1.id for r in my_recs), "strictly emp1 records", "Data leakage")

    my_empty = salary_service.get_my_salary(db, emp2.id)
    chk(my_empty == [], "emp2 has []", f"Got {my_empty}")

    # [4] get_salary_for_employee validates employee existence
    print("\n[4] get_salary_for_employee returns records for existing employee")
    for_emp = salary_service.get_salary_for_employee(db, emp1.id)
    chk(len(for_emp) == 2, "got 2 records for emp1", f"Got {len(for_emp)}")

    for_emp2 = salary_service.get_salary_for_employee(db, emp2.id)
    chk(for_emp2 == [], "got [] for emp2 without records", f"Got {for_emp2}")

    # [5] get_salary_for_employee raises EmployeeNotFoundError for non-existent employee
    print("\n[5] get_salary_for_employee raises EmployeeNotFoundError for missing employee")
    not_found_raised = False
    try:
        salary_service.get_salary_for_employee(db, 999999)
    except EmployeeNotFoundError as exc:
        not_found_raised = True
        chk("Employee not found." in str(exc), "exception message matches", f"Got {exc}")
    chk(not_found_raised, "EmployeeNotFoundError raised", "Did not raise EmployeeNotFoundError")

    # [6] get_salary_by_month
    print("\n[6] get_salary_by_month finds specific record and returns None for missing")
    s_oct = salary_service.get_salary_by_month(db, emp1.id, month=10, year=2024)
    chk(s_oct is not None and s_oct.month == 10 and float(s_oct.net_salary) == 49000.0, "found Oct salary", "Oct salary mismatch")

    s_dec = salary_service.get_salary_by_month(db, emp1.id, month=12, year=2024)
    chk(s_dec is None, "Dec salary is None", "Expected None for unrecorded month")

    # [7] get_salary_summary - overall aggregation
    print("\n[7] get_salary_summary calculates organization totals")
    summary = salary_service.get_salary_summary(db)
    chk(summary["total_records"] >= 2, "total_records >= 2", f"Got {summary['total_records']}")
    chk(summary["total_employees"] >= 1, "total_employees >= 1", f"Got {summary['total_employees']}")
    chk(summary["record_count"] == summary["total_records"], "record_count matches total_records", "Mismatch")
    chk(summary["employee_count"] == summary["total_employees"], "employee_count matches total_employees", "Mismatch")
    chk(summary["total_gross_salary"] >= 100000.0, "total_gross_salary >= 100000", f"Got {summary['total_gross_salary']}")
    chk(summary["total_net_salary"] >= 97000.0, "total_net_salary >= 97000", f"Got {summary['total_net_salary']}")

    # [8] get_salary_summary with month & year filter
    print("\n[8] get_salary_summary with month & year filter")
    sum_oct = salary_service.get_salary_summary(db, month=10, year=2024)
    chk(sum_oct["month"] == 10 and sum_oct["year"] == 2024, "month and year reflected in summary", "Filter mismatch")
    chk(sum_oct["total_records"] >= 1, "October has records", f"Got {sum_oct['total_records']}")
    chk(sum_oct["total_overtime_amount"] >= 1000.0, "total_overtime_amount >= 1000", f"Got {sum_oct['total_overtime_amount']}")

    # [9] get_salary_summary empty filter returns zeros
    print("\n[9] get_salary_summary empty filter returns zero totals")
    sum_empty = salary_service.get_salary_summary(db, month=1, year=1999)
    chk(sum_empty["total_records"] == 0, "total_records == 0", f"Got {sum_empty['total_records']}")
    chk(sum_empty["total_employees"] == 0, "total_employees == 0", f"Got {sum_empty['total_employees']}")
    chk(sum_empty["total_gross_salary"] == 0.0, "total_gross_salary == 0.0", f"Got {sum_empty['total_gross_salary']}")
    chk(sum_empty["total_net_salary"] == 0.0, "total_net_salary == 0.0", f"Got {sum_empty['total_net_salary']}")

    # [10] get_salary_summary invalid month / year raises InvalidSalaryFilterError
    print("\n[10] get_salary_summary invalid filters raise InvalidSalaryFilterError")
    inv_m_raised = False
    try:
        salary_service.get_salary_summary(db, month=13)
    except InvalidSalaryFilterError:
        inv_m_raised = True
    chk(inv_m_raised, "Invalid month raises InvalidSalaryFilterError", "Did not raise for month=13")

    inv_y_raised = False
    try:
        salary_service.get_salary_summary(db, year=-5)
    except InvalidSalaryFilterError:
        inv_y_raised = True
    chk(inv_y_raised, "Invalid year raises InvalidSalaryFilterError", "Did not raise for year=-5")

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
