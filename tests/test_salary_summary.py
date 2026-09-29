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

TEST_EMAILS = [
    "sum.sal.hr@hr.dev",
    "sum.sal.adm@hr.dev",
    "sum.sal.mgr@hr.dev",
    "sum.sal.emp1@hr.dev",
    "sum.sal.emp2@hr.dev",
    "sum.sal.inact@hr.dev",
]
TEST_CODES = [
    "SS-HR",
    "SS-ADM",
    "SS-MGR",
    "SS-EMP1",
    "SS-EMP2",
    "SS-INACT",
]

def cleanup():
    users = db.query(User).filter(User.email.in_(TEST_EMAILS)).all()
    for u in users:
        if u.employee_id:
            db.query(Salary).filter(Salary.employee_id == u.employee_id).delete()
        db.delete(u)
    db.commit()

    db.query(Employee).filter(Employee.employee_code.in_(TEST_CODES)).delete()
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

def make_user(email: str, role: str, emp_code: str, is_active: bool = True):
    emp = create_employee(
        db,
        employee_code=emp_code,
        name=f"Summary Test {role.upper()}",
        department="Finance",
        designation=role.capitalize(),
        joining_date=date(2024, 1, 1),
    )
    user = create_user(
        db,
        employee_id=emp.id,
        email=email,
        password_hash="hashed_pw",
        role=role,
    )
    if not is_active:
        user.status = "inactive"
        db.commit()
    token = create_access_token(user_id=user.id, role=user.role)
    return emp, user, token

try:
    print(SEP)
    print("  GET /salary/summary - Integration Test Suite")
    print(SEP)
    cleanup()

    # Create users
    hr_emp, _, hr_tok = make_user("sum.sal.hr@hr.dev", "hr", "SS-HR")
    adm_emp, _, adm_tok = make_user("sum.sal.adm@hr.dev", "admin", "SS-ADM")
    mgr_emp, _, mgr_tok = make_user("sum.sal.mgr@hr.dev", "manager", "SS-MGR")
    emp1, _, emp1_tok = make_user("sum.sal.emp1@hr.dev", "employee", "SS-EMP1")
    emp2, _, emp2_tok = make_user("sum.sal.emp2@hr.dev", "employee", "SS-EMP2")
    _, _, inact_tok = make_user("sum.sal.inact@hr.dev", "hr", "SS-INACT", is_active=False)

    # Insert known salary test records
    # Emp1: Oct 2024 & Nov 2024
    s1 = Salary(
        employee_id=emp1.id, month=10, year=2024,
        gross_salary=50000.0, pf=1800.0, deductions=200.0,
        overtime_amount=1000.0, net_salary=49000.0,
        paid_at=datetime(2024, 10, 31, 10, 0, 0),
    )
    s2 = Salary(
        employee_id=emp1.id, month=11, year=2024,
        gross_salary=50000.0, pf=1800.0, deductions=200.0,
        overtime_amount=0.0, net_salary=48000.0,
        paid_at=None,
    )
    # Emp2: Oct 2024 & Oct 2025
    s3 = Salary(
        employee_id=emp2.id, month=10, year=2024,
        gross_salary=60000.0, pf=2000.0, deductions=500.0,
        overtime_amount=1500.0, net_salary=59000.0,
        paid_at=datetime(2024, 10, 31, 10, 0, 0),
    )
    s4 = Salary(
        employee_id=emp2.id, month=10, year=2025,
        gross_salary=65000.0, pf=2200.0, deductions=600.0,
        overtime_amount=2000.0, net_salary=64200.0,
        paid_at=datetime(2025, 10, 31, 10, 0, 0),
    )
    db.add_all([s1, s2, s3, s4])
    db.commit()

    # 1. Access Control: HR allowed (200)
    print("\n[1] HR can access summary -> 200")
    r_hr = client.get("/salary/summary", headers={"Authorization": f"Bearer {hr_tok}"})
    chk(r_hr.status_code == 200, "status 200", f"status {r_hr.status_code}")
    hr_data = r_hr.json()
    chk("total_gross_salary" in hr_data, "response has total_gross_salary", f"Got {hr_data}")
    chk("total_net_salary" in hr_data, "response has total_net_salary", f"Got {hr_data}")

    # 2. Access Control: Admin allowed (200)
    print("\n[2] Admin can access summary -> 200")
    r_adm = client.get("/salary/summary", headers={"Authorization": f"Bearer {adm_tok}"})
    chk(r_adm.status_code == 200, "status 200", f"status {r_adm.status_code}")

    # 3. Access Control: Regular employee forbidden (403)
    print("\n[3] Regular employee cannot access summary -> 403")
    r_emp = client.get("/salary/summary", headers={"Authorization": f"Bearer {emp1_tok}"})
    chk(r_emp.status_code == 403, "status 403", f"status {r_emp.status_code}")

    # 4. Access Control: Manager forbidden (403)
    print("\n[4] Manager cannot access summary -> 403")
    r_mgr = client.get("/salary/summary", headers={"Authorization": f"Bearer {mgr_tok}"})
    chk(r_mgr.status_code == 403, "status 403", f"status {r_mgr.status_code}")

    # 5. Access Control: Unauthenticated / Invalid token (401)
    print("\n[5] Unauthenticated request -> 401")
    r_no_auth = client.get("/salary/summary")
    chk(r_no_auth.status_code == 401, "status 401 without token", f"status {r_no_auth.status_code}")
    r_bad_auth = client.get("/salary/summary", headers={"Authorization": "Bearer INVALID_TOKEN"})
    chk(r_bad_auth.status_code == 401, "status 401 with invalid token", f"status {r_bad_auth.status_code}")

    # 6. Inactive user forbidden (403)
    print("\n[6] Inactive HR user -> 403")
    r_inact = client.get("/salary/summary", headers={"Authorization": f"Bearer {inact_tok}"})
    chk(r_inact.status_code == 403, "status 403", f"status {r_inact.status_code}")

    # 7. Summary totals calculated correctly (Month 10, Year 2024: s1 and s3)
    print("\n[7] Summary totals calculated correctly for Month + Year filter")
    r_filtered = client.get(
        "/salary/summary?month=10&year=2024",
        headers={"Authorization": f"Bearer {hr_tok}"},
    )
    chk(r_filtered.status_code == 200, "status 200", f"status {r_filtered.status_code}")
    d = r_filtered.json()
    chk(d["month"] == 10, "month=10", f"Got month={d['month']}")
    chk(d["year"] == 2024, "year=2024", f"Got year={d['year']}")
    chk(d["total_records"] == 2, "total_records=2", f"Got total_records={d['total_records']}")
    chk(d["total_employees"] == 2, "total_employees=2", f"Got total_employees={d['total_employees']}")
    chk(d["record_count"] == 2, "record_count=2", f"Got record_count={d['record_count']}")
    chk(d["employee_count"] == 2, "employee_count=2", f"Got employee_count={d['employee_count']}")
    chk(d["total_gross_salary"] == 110000.0, "total_gross=110000.0", f"Got gross={d['total_gross_salary']}")
    chk(d["total_pf"] == 3800.0, "total_pf=3800.0", f"Got pf={d['total_pf']}")
    chk(d["total_deductions"] == 700.0, "total_deductions=700.0", f"Got deductions={d['total_deductions']}")
    chk(d["total_overtime_amount"] == 2500.0, "total_ot=2500.0", f"Got ot={d['total_overtime_amount']}")
    chk(d["total_net_salary"] == 108000.0, "total_net=108000.0", f"Got net={d['total_net_salary']}")

    # 8. Month filter works
    print("\n[8] Month filter works (month=11: s2 only)")
    r_m = client.get("/salary/summary?month=11", headers={"Authorization": f"Bearer {hr_tok}"})
    chk(r_m.status_code == 200, "status 200", f"status {r_m.status_code}")
    d_m = r_m.json()
    chk(d_m["total_records"] >= 1, "total_records >= 1", f"Got {d_m['total_records']}")
    chk(d_m["month"] == 11, "month=11", f"Got {d_m['month']}")

    # 9. Year filter works
    print("\n[9] Year filter works (year=2025: s4 only)")
    r_y = client.get("/salary/summary?year=2025", headers={"Authorization": f"Bearer {hr_tok}"})
    chk(r_y.status_code == 200, "status 200", f"status {r_y.status_code}")
    d_y = r_y.json()
    chk(d_y["year"] == 2025, "year=2025", f"Got {d_y['year']}")
    chk(d_y["total_records"] >= 1, "total_records >= 1", f"Got {d_y['total_records']}")
    chk(d_y["total_gross_salary"] >= 65000.0, "total_gross_salary >= 65000", f"Got {d_y['total_gross_salary']}")

    # 10. No matching records returns valid 200 with zero totals
    print("\n[10] No matching records returns 200 with zero totals")
    r_zero = client.get("/salary/summary?year=1990", headers={"Authorization": f"Bearer {hr_tok}"})
    chk(r_zero.status_code == 200, "status 200", f"status {r_zero.status_code}")
    d_zero = r_zero.json()
    chk(d_zero["total_records"] == 0, "total_records=0", f"Got {d_zero['total_records']}")
    chk(d_zero["total_employees"] == 0, "total_employees=0", f"Got {d_zero['total_employees']}")
    chk(d_zero["total_gross_salary"] == 0.0, "total_gross=0.0", f"Got {d_zero['total_gross_salary']}")
    chk(d_zero["total_pf"] == 0.0, "total_pf=0.0", f"Got {d_zero['total_pf']}")
    chk(d_zero["total_deductions"] == 0.0, "total_deductions=0.0", f"Got {d_zero['total_deductions']}")
    chk(d_zero["total_overtime_amount"] == 0.0, "total_ot=0.0", f"Got {d_zero['total_overtime_amount']}")
    chk(d_zero["total_net_salary"] == 0.0, "total_net=0.0", f"Got {d_zero['total_net_salary']}")

    # 11. Invalid month is rejected -> 400
    print("\n[11] Invalid month is rejected -> 400")
    r_inv_m1 = client.get("/salary/summary?month=13", headers={"Authorization": f"Bearer {hr_tok}"})
    chk(r_inv_m1.status_code == 400, "month=13 -> status 400", f"status {r_inv_m1.status_code}")
    r_inv_m2 = client.get("/salary/summary?month=0", headers={"Authorization": f"Bearer {hr_tok}"})
    chk(r_inv_m2.status_code == 400, "month=0 -> status 400", f"status {r_inv_m2.status_code}")

    # 12. Invalid year is rejected -> 400
    print("\n[12] Invalid year is rejected -> 400")
    r_inv_y1 = client.get("/salary/summary?year=0", headers={"Authorization": f"Bearer {hr_tok}"})
    chk(r_inv_y1.status_code == 400, "year=0 -> status 400", f"status {r_inv_y1.status_code}")
    r_inv_y2 = client.get("/salary/summary?year=-2024", headers={"Authorization": f"Bearer {hr_tok}"})
    chk(r_inv_y2.status_code == 400, "year=-2024 -> status 400", f"status {r_inv_y2.status_code}")

    # 13. Existing salary endpoints still work & route ordering preserved
    print("\n[13] Route ordering & preservation of GET /salary/me and GET /salary/{employee_id}")
    r_me = client.get("/salary/me", headers={"Authorization": f"Bearer {emp1_tok}"})
    chk(r_me.status_code == 200, "GET /salary/me works -> 200", f"status {r_me.status_code}")
    chk(len(r_me.json()) == 2, "returns emp1's 2 salary records", f"Got {len(r_me.json())}")

    r_id = client.get(f"/salary/{emp2.id}", headers={"Authorization": f"Bearer {hr_tok}"})
    chk(r_id.status_code == 200, "GET /salary/{employee_id} works -> 200", f"status {r_id.status_code}")
    chk(len(r_id.json()) == 2, "returns emp2's 2 salary records", f"Got {len(r_id.json())}")

except Exception as e:
    print("\nEXCEPTION:", e)
    failed += 1
finally:
    cleanup()
    db.close()
    print("\n" + SEP)
    print(f"  Results: {passed} passed, {failed} failed")
    print(SEP)
    if failed > 0:
        sys.exit(1)
