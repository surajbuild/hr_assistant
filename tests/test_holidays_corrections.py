"""
tests/test_holidays_corrections.py
----------------------------------
Session-5 HR features:

  [1] Holiday calendar (D-034): GET/POST/DELETE /holidays — auth, roles, weekend / national /
      duplicate validation; declared holidays reduce payroll working days and are not charged as leave
  [2] Attendance correction requests (D-033): create / list / approve / reject / cancel — validation,
      manager team scope, no self-review, record recomputed on approval
  [3] HR direct edit PUT /attendance/records/{id} — roles, own record refused, computed minutes
  [4] Mark as paid (D-036): POST /salary/mark-paid — roles, idempotent, paid month locks corrections/edits
  [5] Pagination (D-035): limit / offset + X-Total-Count on /employees, /attendance/records, /chat/logs

Only test-owned rows: employees T-COR-* (department "QA Corrections", users @hrtest.dev), holidays in
2031 (a year without data), their attendance / leaves / salary / corrections. Everything is removed in
`finally`; seeded rows are never modified.
"""

import os
import sys
from datetime import date, time, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models import (
    Attendance,
    AttendanceCorrection,
    Employee,
    Holiday,
    Leave,
    Salary,
    User,
)
from app.main import app
from app.services import leave_service, salary_service
from app.services.attendance_service import COMPANY_HOLIDAYS, working_days_between
from app.services.employee_service import create_employee
from app.utils.security import create_access_token

client = TestClient(app)
db = SessionLocal()
passed_count = 0
failed_count = 0

CODES = ["T-COR-MGR", "T-COR-EMP", "T-COR-MGR2", "T-COR-HR"]
DEPT = "QA Corrections"
PASSWORD = "CorTest#2026"
HOLIDAY_YEAR = 2031


def chk(condition: bool, msg: str, fail_detail: str = ""):
    global passed_count, failed_count
    if condition:
        print(f"  [PASS] {msg}")
        passed_count += 1
    else:
        print(f"  [FAIL] {msg} -> {fail_detail}")
        failed_count += 1


def hdr(user: User):
    return {"Authorization": f"Bearer {create_access_token(user_id=user.id, role=user.role)}"}


def first_weekday(start: date, skip_national: bool = True) -> date:
    d = start
    while d.weekday() >= 5 or (skip_national and (d.month, d.day) in COMPANY_HOLIDAYS):
        d += timedelta(days=1)
    return d


def cleanup():
    db.rollback()
    db.query(Holiday).filter(
        Holiday.holiday_date >= date(HOLIDAY_YEAR, 1, 1), Holiday.holiday_date <= date(HOLIDAY_YEAR, 12, 31)
    ).delete(synchronize_session=False)
    ids = [e.id for e in db.query(Employee).filter(Employee.employee_code.in_(CODES)).all()]
    if ids:
        db.query(AttendanceCorrection).filter(AttendanceCorrection.employee_id.in_(ids)).delete(synchronize_session=False)
        db.query(Salary).filter(Salary.employee_id.in_(ids)).delete(synchronize_session=False)
        db.query(Attendance).filter(Attendance.employee_id.in_(ids)).delete(synchronize_session=False)
        db.query(Leave).filter(Leave.employee_id.in_(ids)).delete(synchronize_session=False)
        db.query(User).filter(User.employee_id.in_(ids)).delete(synchronize_session=False)
        db.query(Employee).filter(Employee.id.in_(ids)).update({Employee.manager_id: None}, synchronize_session=False)
        db.query(Employee).filter(Employee.id.in_(ids)).delete(synchronize_session=False)
    db.commit()


try:
    cleanup()
    hr = db.query(User).filter(User.email == "neha.hr@company.com").first()
    admin = db.query(User).filter(User.email == "admin@company.com").first()
    seeded_emp = db.query(User).filter(User.email == "aman@company.com").first()
    if not hr or not admin or not seeded_emp:
        raise RuntimeError("Seed users missing — run scripts/seed_db.py")

    mgr_e = create_employee(db, employee_code="T-COR-MGR", name="Cor Manager", department=DEPT,
                            designation="QA Lead", joining_date=date(2024, 1, 1),
                            email="t.cor.mgr@hrtest.dev", password=PASSWORD, role="manager")
    emp_e = create_employee(db, employee_code="T-COR-EMP", name="Cor Employee", department=DEPT,
                            designation="QA Engineer", joining_date=date(2024, 1, 1), manager_id=mgr_e.id,
                            email="t.cor.emp@hrtest.dev", password=PASSWORD, role="employee",
                            monthly_gross_salary=84000)
    mgr2_e = create_employee(db, employee_code="T-COR-MGR2", name="Cor Other Manager", department=DEPT,
                             designation="QA Lead", joining_date=date(2024, 1, 1),
                             email="t.cor.mgr2@hrtest.dev", password=PASSWORD, role="manager")
    hr_e = create_employee(db, employee_code="T-COR-HR", name="Cor HR", department=DEPT,
                           designation="HR Executive", joining_date=date(2024, 1, 1),
                           email="t.cor.hr@hrtest.dev", password=PASSWORD, role="hr")
    users = {u.employee_id: u for u in db.query(User).filter(User.employee_id.in_(
        [mgr_e.id, emp_e.id, mgr2_e.id, hr_e.id])).all()}
    MGR, EMP, MGR2, THR = (hdr(users[e.id]) for e in (mgr_e, emp_e, mgr2_e, hr_e))
    HR, ADMIN, SEEDED = hdr(hr), hdr(admin), hdr(seeded_emp)

    # -----------------------------------------------------------------------
    print("\n[1] Holiday calendar")
    chk(client.get("/holidays").status_code == 401, "GET /holidays unauthenticated → 401")
    r = client.get(f"/holidays?year={HOLIDAY_YEAR}", headers=EMP)
    national = [i for i in r.json().get("items", []) if i["kind"] == "national"] if r.status_code == 200 else []
    chk(r.status_code == 200 and len(national) == len(COMPANY_HOLIDAYS), "employee sees national holidays", r.text[:200])

    hol_day = first_weekday(date(HOLIDAY_YEAR, 3, 10))
    body = {"holiday_date": hol_day.isoformat(), "name": "T-COR Founders Day"}
    chk(client.post("/holidays", json=body).status_code == 401, "POST /holidays unauthenticated → 401")
    chk(client.post("/holidays", json=body, headers=EMP).status_code == 403, "employee cannot declare → 403")
    chk(client.post("/holidays", json=body, headers=MGR).status_code == 403, "manager cannot declare → 403")
    r = client.post("/holidays", json=body, headers=HR)
    chk(r.status_code == 201 and r.json()["kind"] == "company", "HR declares a company holiday → 201", r.text)
    hol_id = r.json().get("id")
    chk(client.post("/holidays", json=body, headers=ADMIN).status_code == 409, "same date again → 409")
    weekend = hol_day + timedelta(days=(5 - hol_day.weekday()))
    r = client.post("/holidays", json={"holiday_date": weekend.isoformat(), "name": "T-COR weekend"}, headers=HR)
    chk(r.status_code == 422, "weekend date → 422", r.text)
    nat = next(date(HOLIDAY_YEAR, m, d) for (m, d) in COMPANY_HOLIDAYS if date(HOLIDAY_YEAR, m, d).weekday() < 5)
    r = client.post("/holidays", json={"holiday_date": nat.isoformat(), "name": "T-COR dup national"}, headers=HR)
    chk(r.status_code == 409, "national holiday date → 409", r.text)
    r = client.post("/holidays", json={"holiday_date": hol_day.isoformat(), "name": "  "}, headers=HR)
    chk(r.status_code in (409, 422), "blank name refused", str(r.status_code))
    items = client.get(f"/holidays?year={HOLIDAY_YEAR}", headers=EMP).json()["items"]
    chk(any(i["id"] == hol_id and i["weekday"] == hol_day.strftime("%A") for i in items), "listed with weekday")

    # Effect on payroll working days and leave counting
    db.commit()
    month_first = date(HOLIDAY_YEAR, hol_day.month, 1)
    month_last = (month_first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    plain = len(working_days_between(month_first, month_last))
    calc = salary_service.calculate_payroll(db, db.query(Employee).get(emp_e.id), hol_day.month, HOLIDAY_YEAR)
    chk(calc["working_days"] == plain - 1, "declared holiday removes one payroll working day",
        f"{calc['working_days']} vs {plain}")
    db.add(Leave(employee_id=emp_e.id, leave_type="casual", from_date=hol_day - timedelta(days=0),
                 to_date=hol_day + timedelta(days=1) if hol_day.weekday() < 4 else hol_day,
                 status="approved", reason="T-COR leave over holiday"))
    db.commit()
    expected_days = 1 if hol_day.weekday() < 4 else 0
    bal = {b["leave_type"]: b for b in leave_service.get_leave_balance(db, emp_e.id, HOLIDAY_YEAR)}
    chk(bal["casual"]["used"] == expected_days, "holiday inside a leave is not charged",
        f"used {bal['casual']['used']} expected {expected_days}")

    chk(client.delete(f"/holidays/{hol_id}", headers=EMP).status_code == 403, "employee cannot delete → 403")
    chk(client.delete(f"/holidays/{hol_id}", headers=HR).status_code == 204, "HR deletes → 204")
    chk(client.delete(f"/holidays/{hol_id}", headers=HR).status_code == 404, "deleted again → 404")
    db.commit()
    calc = salary_service.calculate_payroll(db, db.query(Employee).get(emp_e.id), hol_day.month, HOLIDAY_YEAR)
    chk(calc["working_days"] == plain, "working days restored after delete")

    # -----------------------------------------------------------------------
    print("\n[2] Correction requests")
    day1 = first_weekday(date(2025, 6, 2))            # existing record → corrected
    day2 = first_weekday(day1 + timedelta(days=1))   # no record → created on approval
    day3 = first_weekday(day2 + timedelta(days=1))   # rejected
    day4 = first_weekday(day3 + timedelta(days=1))   # cancelled
    db.add(Attendance(employee_id=emp_e.id, attendance_date=day1, status="present", in_time=time(9, 5),
                      out_time=None, working_minutes=0, late_minutes=0, overtime_minutes=0))
    db.commit()

    def req(d, i="09:30:00", o="18:45:00", reason="Forgot to check out", headers=EMP):
        return client.post("/attendance/corrections", headers=headers,
                           json={"attendance_date": d.isoformat(), "in_time": i, "out_time": o, "reason": reason})

    chk(client.post("/attendance/corrections", json={}).status_code == 401, "unauthenticated → 401")
    chk(req(date.today() + timedelta(days=2)).status_code == 422, "future date → 422")
    chk(req(day1, i="18:00:00", o="09:00:00").status_code == 422, "out before in → 422")
    chk(req(date(2023, 12, 29)).status_code == 422, "before joining date → 422")
    r1 = req(day1)
    chk(r1.status_code == 201 and r1.json()["status"] == "pending" and r1.json()["current_status"] == "present",
        "request for a day with a record → 201 pending, shows current record", r1.text)
    c1 = r1.json().get("id")
    chk(req(day1).status_code == 409, "second pending request for the same day → 409")
    c2 = req(day2).json().get("id")
    c3 = req(day3).json().get("id")
    c4 = req(day4).json().get("id")
    rm = req(day1, headers=MGR)
    chk(rm.status_code == 201, "manager files own request → 201", rm.text)
    cm = rm.json().get("id")

    mine = client.get("/attendance/corrections/me", headers=EMP).json()
    chk({c1, c2, c3, c4} <= {c["id"] for c in mine} and cm not in {c["id"] for c in mine}, "GET /me lists only own requests")
    chk(client.get("/attendance/corrections", headers=EMP).status_code == 403, "employee cannot list the review queue → 403")
    mq = {c["id"] for c in client.get("/attendance/corrections?status=pending", headers=MGR).json()}
    chk({c1, c2, c3, c4} <= mq, "manager sees the team's pending requests")
    chk(cm not in mq, "manager's own request is not in their review queue")
    chk(not ({c1, c2} & {c["id"] for c in client.get("/attendance/corrections", headers=MGR2).json()}),
        "another manager does not see them")
    chk(cm in {c["id"] for c in client.get("/attendance/corrections", headers=HR).json()}, "HR sees the manager's request")

    chk(client.post(f"/attendance/corrections/{c1}/approve", headers=EMP).status_code == 403, "employee cannot approve → 403")
    chk(client.post(f"/attendance/corrections/{c1}/approve", headers=MGR2).status_code == 403, "other team's manager → 403")
    chk(client.post(f"/attendance/corrections/{cm}/approve", headers=MGR).status_code == 403, "manager approving own request → 403")
    chk(client.post("/attendance/corrections/999999/approve", headers=HR).status_code == 404, "unknown request → 404")

    r = client.post(f"/attendance/corrections/{c1}/approve", headers=MGR, json={"note": "ok"})
    chk(r.status_code == 200 and r.json()["status"] == "approved" and r.json()["reviewed_by_name"] == "Cor Manager",
        "manager approves team request → 200", r.text)
    db.commit()
    rec = db.query(Attendance).filter(Attendance.employee_id == emp_e.id, Attendance.attendance_date == day1).first()
    chk(rec and rec.in_time == time(9, 30) and rec.out_time == time(18, 45), "approval updates the record times")
    chk(rec and (rec.working_minutes, rec.late_minutes, rec.overtime_minutes, rec.status) == (495, 30, 15, "present"),
        "minutes recomputed by the server (495 worked, 30 late, 15 OT)",
        f"{rec.working_minutes, rec.late_minutes, rec.overtime_minutes, rec.status}" if rec else "no record")
    chk(db.query(Attendance).filter(Attendance.employee_id == emp_e.id, Attendance.attendance_date == day1).count() == 1,
        "no duplicate record")
    chk(client.post(f"/attendance/corrections/{c1}/approve", headers=HR).status_code == 409, "approve twice → 409")

    r = client.post(f"/attendance/corrections/{c2}/approve", headers=HR)
    db.commit()
    chk(r.status_code == 200 and db.query(Attendance).filter(
        Attendance.employee_id == emp_e.id, Attendance.attendance_date == day2).count() == 1,
        "HR approval creates the missing record")
    r = client.post(f"/attendance/corrections/{c3}/reject", headers=MGR, json={"note": "Badge log shows 10:40"})
    chk(r.status_code == 200 and r.json()["status"] == "rejected" and r.json()["review_note"] == "Badge log shows 10:40",
        "manager rejects with a note", r.text)
    db.commit()
    chk(db.query(Attendance).filter(Attendance.employee_id == emp_e.id, Attendance.attendance_date == day3).count() == 0,
        "rejection does not touch attendance")
    chk(client.post(f"/attendance/corrections/{c4}/cancel", headers=MGR).status_code == 404, "someone else cannot cancel → 404")
    r = client.post(f"/attendance/corrections/{c4}/cancel", headers=EMP)
    chk(r.status_code == 200 and r.json()["status"] == "cancelled", "owner cancels a pending request")
    chk(client.post(f"/attendance/corrections/{c4}/cancel", headers=EMP).status_code == 409, "cancel twice → 409")
    chk(client.post(f"/attendance/corrections/{cm}/approve", headers=THR).status_code == 200, "another HR approves the manager's request")

    # -----------------------------------------------------------------------
    print("\n[3] HR direct edit")
    db.commit()
    rec2 = db.query(Attendance).filter(Attendance.employee_id == emp_e.id, Attendance.attendance_date == day2).first()
    url = f"/attendance/records/{rec2.id}"
    chk(client.put(url, json={"status": "absent"}).status_code == 401, "unauthenticated → 401")
    chk(client.put(url, json={"status": "absent"}, headers=EMP).status_code == 403, "employee → 403")
    chk(client.put(url, json={"status": "absent"}, headers=MGR).status_code == 403, "manager → 403")
    chk(client.put(url, json={"status": "present"}, headers=HR).status_code == 422, "worked day without times → 422")
    r = client.put(url, json={"status": "present", "in_time": "09:00:00", "out_time": "12:00:00"}, headers=HR)
    chk(r.status_code == 200 and r.json()["status"] == "half_day" and r.json()["working_minutes"] == 180,
        "short worked day becomes half day (computed)", r.text)
    r = client.put(url, json={"status": "absent"}, headers=HR)
    chk(r.status_code == 200 and r.json()["in_time"] is None and r.json()["working_minutes"] == 0,
        "absent clears times and minutes", r.text)
    chk(client.put("/attendance/records/99999999", json={"status": "absent"}, headers=HR).status_code == 404, "unknown record → 404")
    db.add(Attendance(employee_id=hr_e.id, attendance_date=day1, status="absent", working_minutes=0,
                      late_minutes=0, overtime_minutes=0))
    db.commit()
    own = db.query(Attendance).filter(Attendance.employee_id == hr_e.id, Attendance.attendance_date == day1).first()
    chk(client.put(f"/attendance/records/{own.id}", json={"status": "holiday"}, headers=THR).status_code == 403,
        "HR cannot edit their own record → 403")
    r = client.post("/attendance", headers=THR, json={"employee_id": hr_e.id, "attendance_date": day2.isoformat(),
                                                      "status": "present"})
    chk(r.status_code == 403, "HR cannot create their own attendance record → 403 (D-039)", r.text)

    # -----------------------------------------------------------------------
    print("\n[4] Mark as paid + lock")
    db.add(Salary(employee_id=emp_e.id, month=day1.month, year=day1.year, gross_salary=84000, pf=0,
                  deductions=0, overtime_amount=0, net_salary=84000, paid_at=None))
    db.commit()
    sal = db.query(Salary).filter(Salary.employee_id == emp_e.id, Salary.month == day1.month, Salary.year == day1.year).first()
    chk(client.post("/salary/mark-paid", json={"salary_ids": [sal.id]}).status_code == 401, "unauthenticated → 401")
    chk(client.post("/salary/mark-paid", json={"salary_ids": [sal.id]}, headers=EMP).status_code == 403, "employee → 403")
    chk(client.post("/salary/mark-paid", json={"salary_ids": [sal.id]}, headers=MGR).status_code == 403, "manager → 403")
    chk(client.post("/salary/mark-paid", json={"salary_ids": []}, headers=HR).status_code == 422, "empty list → 422")
    r = client.post("/salary/mark-paid", json={"salary_ids": [sal.id, 99999999]}, headers=HR)
    chk(r.status_code == 200 and r.json()["marked"] == [sal.id] and r.json()["not_found"] == [99999999],
        "HR marks paid; unknown id reported", r.text)
    r = client.post("/salary/mark-paid", json={"salary_ids": [sal.id]}, headers=HR)
    chk(r.status_code == 200 and r.json()["already_paid"] == [sal.id] and r.json()["marked"] == [],
        "second call is idempotent (already_paid)", r.text)
    payroll = client.get(f"/salary?month={day1.month}&year={day1.year}", headers=HR).json()
    chk(any(i["id"] == sal.id and i["paid_at"] for i in payroll["items"]), "payroll sheet shows paid_at")
    r = req(day3)
    chk(r.status_code == 409 and "paid" in r.json().get("detail", ""), "correction in a paid month → 409", r.text)
    r = client.put(url, json={"status": "present", "in_time": "09:00:00", "out_time": "18:00:00"}, headers=HR)
    chk(r.status_code == 409, "direct edit in a paid month → 409", r.text)
    db.commit()  # fresh snapshot: paid_at was written through the API
    gen = salary_service.generate_payroll(db, day1.month, day1.year, employee_ids=[emp_e.id])
    chk(gen["skipped"] and "locked" in gen["skipped"][0]["reason"], "payroll engine skips the paid row")

    # -----------------------------------------------------------------------
    print("\n[5] Pagination")
    full = client.get("/employees", headers=HR)
    total = len(full.json())
    chk(full.headers.get("x-total-count") == str(total), "GET /employees sends X-Total-Count", str(full.headers.get("x-total-count")))
    page = client.get("/employees?limit=2&offset=1", headers=HR)
    chk(page.json() == full.json()[1:3] and page.headers.get("x-total-count") == str(total),
        "limit/offset slice matches the full list")
    chk(client.get(f"/employees?limit=5&offset={total}", headers=HR).json() == [], "offset past the end → []")
    chk(client.get("/employees?limit=0", headers=HR).status_code == 422, "limit=0 → 422")
    r = client.get(f"/attendance/records?employee_id={emp_e.id}&limit=1", headers=HR)
    db.commit()
    n_rec = db.query(Attendance).filter(Attendance.employee_id == emp_e.id).count()
    chk(r.status_code == 200 and len(r.json()) == 1 and r.headers.get("x-total-count") == str(n_rec),
        "GET /attendance/records paginates with total", f"{r.headers.get('x-total-count')} vs {n_rec}")
    r2 = client.get(f"/attendance/records?employee_id={emp_e.id}&limit=1&offset=1", headers=HR)
    chk(r2.json() and r2.json()[0]["id"] != r.json()[0]["id"], "next page returns a different record")
    r = client.get("/chat/logs?limit=1", headers=ADMIN)
    chk(r.status_code == 200 and len(r.json()) <= 1 and r.headers.get("x-total-count", "").isdigit(),
        "GET /chat/logs paginates with total")
    r = client.get("/chat/logs?limit=5&search=zz-no-such-question-zz", headers=ADMIN)
    chk(r.status_code == 200 and r.json() == [] and r.headers.get("x-total-count") == "0", "chat log search filters")
    chk(client.get("/chat/logs?limit=1", headers=HR).status_code == 403, "chat logs stay admin-only")
finally:
    cleanup()
    db.close()

print(f"\nResults: {passed_count} passed, {failed_count} failed")
sys.exit(1 if failed_count else 0)
