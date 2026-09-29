import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from datetime import date, time
from app.database.connection import SessionLocal
from app.database.models import Employee, User, Attendance
from app.database.queries import create_employee, create_user
from app.services import attendance_service
from app.services.attendance_service import (
    DuplicateAttendanceError,
    EmployeeNotFoundError,
    InvalidDateRangeError,
)

db = SessionLocal()

TEST_EMP_CODE_SVC_1 = "SVC-ATT-001"
TEST_EMAIL_SVC_1 = "svc.att1@hr.dev"

TEST_EMP_CODE_SVC_2 = "SVC-ATT-002"
TEST_EMAIL_SVC_2 = "svc.att2@hr.dev"

def cleanup():
    for email in [TEST_EMAIL_SVC_1, TEST_EMAIL_SVC_2]:
        u = db.query(User).filter(User.email == email).first()
        if u:
            db.query(Attendance).filter(Attendance.employee_id == u.employee_id).delete()
            db.delete(u)
    for code in [TEST_EMP_CODE_SVC_1, TEST_EMP_CODE_SVC_2]:
        e = db.query(Employee).filter(Employee.employee_code == code).first()
        if e:
            db.query(Attendance).filter(Attendance.employee_id == e.id).delete()
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
    print("  Attendance Service Layer - Unit & Business Logic Test")
    print(SEP)
    cleanup()

    # Create test employee 1
    emp1 = create_employee(
        db, employee_code=TEST_EMP_CODE_SVC_1, name="Service Tester 1",
        department="Engineering", designation="Tester", joining_date=date(2024, 1, 1)
    )
    user1 = create_user(db, employee_id=emp1.id, email=TEST_EMAIL_SVC_1, password_hash="hash", role="employee")

    # Create test employee 2 (empty)
    emp2 = create_employee(
        db, employee_code=TEST_EMP_CODE_SVC_2, name="Service Tester 2",
        department="Engineering", designation="Tester", joining_date=date(2024, 1, 1)
    )
    user2 = create_user(db, employee_id=emp2.id, email=TEST_EMAIL_SVC_2, password_hash="hash", role="employee")

    # [1] create_attendance: successful creation
    print("\n[1] create_attendance creates and persists record")
    rec1 = attendance_service.create_attendance(
        db,
        employee_id=emp1.id,
        attendance_date=date(2024, 11, 1),
        status="present",
        in_time=time(9, 0),
        out_time=time(17, 30),
        working_minutes=510,
        late_minutes=0,
        overtime_minutes=30,
    )
    chk(rec1.id is not None and rec1.employee_id == emp1.id, "rec1 created with ID", "Creation failed")

    # [2] create_attendance: duplicate date raises DuplicateAttendanceError
    print("\n[2] create_attendance duplicate date raises DuplicateAttendanceError")
    dup_raised = False
    try:
        attendance_service.create_attendance(
            db,
            employee_id=emp1.id,
            attendance_date=date(2024, 11, 1),
            status="present",
        )
    except DuplicateAttendanceError:
        dup_raised = True
    chk(dup_raised, "DuplicateAttendanceError raised", "Did not raise DuplicateAttendanceError")

    # [3] create_attendance: non-existent employee raises EmployeeNotFoundError
    print("\n[3] create_attendance non-existent employee raises EmployeeNotFoundError")
    not_found_raised = False
    try:
        attendance_service.create_attendance(
            db,
            employee_id=999999,
            attendance_date=date(2024, 11, 2),
            status="present",
        )
    except EmployeeNotFoundError:
        not_found_raised = True
    chk(not_found_raised, "EmployeeNotFoundError raised", "Did not raise EmployeeNotFoundError")

    # [4] get_attendance_by_date
    print("\n[4] get_attendance_by_date finds existing and returns None for missing")
    found_att = attendance_service.get_attendance_by_date(db, emp1.id, date(2024, 11, 1))
    missing_att = attendance_service.get_attendance_by_date(db, emp1.id, date(2024, 11, 9))
    chk(found_att is not None and found_att.id == rec1.id, "found_att matches rec1", "Failed to find record")
    chk(missing_att is None, "missing_att is None", "Expected None for missing date")

    # [5] get_attendance_by_employee_id and get_my_attendance
    print("\n[5] get_attendance_by_employee_id and get_my_attendance return records")
    list1 = attendance_service.get_attendance_by_employee_id(db, emp1.id)
    my_list1 = attendance_service.get_my_attendance(db, emp1.id)
    chk(len(list1) == 1 and list1[0].id == rec1.id, "list1 contains 1 record", f"Got {len(list1)}")
    chk(len(my_list1) == 1, "get_my_attendance returns 1 record", f"Got {len(my_list1)}")

    # Empty employee returns []
    list2 = attendance_service.get_attendance_by_employee_id(db, emp2.id)
    chk(list2 == [], "empty employee returns []", f"Got {list2}")

    # [6] get_attendance_for_employee
    print("\n[6] get_attendance_for_employee validates existence and raises on missing")
    for_emp = attendance_service.get_attendance_for_employee(db, emp1.id)
    chk(len(for_emp) == 1, "get_attendance_for_employee returned 1 record", f"Got {len(for_emp)}")

    missing_raised = False
    try:
        attendance_service.get_attendance_for_employee(db, 888888)
    except EmployeeNotFoundError:
        missing_raised = True
    chk(missing_raised, "EmployeeNotFoundError raised for missing employee", "Did not raise EmployeeNotFoundError")

    # [7] Add more attendance records to emp1 and test get_attendance_summary
    print("\n[7] get_attendance_summary calculation & aggregations")
    attendance_service.create_attendance(
        db,
        employee_id=emp1.id,
        attendance_date=date(2024, 11, 2),
        status="present",
        working_minutes=450,
        late_minutes=30,
        overtime_minutes=0,
    )
    attendance_service.create_attendance(
        db,
        employee_id=emp1.id,
        attendance_date=date(2024, 11, 3),
        status="absent",
        working_minutes=0,
        late_minutes=0,
        overtime_minutes=0,
    )
    attendance_service.create_attendance(
        db,
        employee_id=emp1.id,
        attendance_date=date(2024, 11, 4),
        status="half_day",
        working_minutes=240,
        late_minutes=0,
        overtime_minutes=0,
    )
    attendance_service.create_attendance(
        db,
        employee_id=emp1.id,
        attendance_date=date(2024, 11, 5),
        status="leave",
        working_minutes=0,
        late_minutes=0,
        overtime_minutes=0,
    )

    summary = attendance_service.get_attendance_summary(db, emp1.id)
    chk(summary["total_days"] == 5, f"total_days == 5 (got {summary['total_days']})", f"Wrong total_days: {summary['total_days']}")
    chk(summary["present_days"] == 2, f"present_days == 2 (got {summary['present_days']})", f"Wrong present_days: {summary['present_days']}")
    chk(summary["absent_days"] == 1, f"absent_days == 1 (got {summary['absent_days']})", f"Wrong absent_days: {summary['absent_days']}")
    chk(summary["half_day_days"] == 1, f"half_day_days == 1 (got {summary['half_day_days']})", f"Wrong half_day_days: {summary['half_day_days']}")
    chk(summary["leave_days"] == 1, f"leave_days == 1 (got {summary['leave_days']})", f"Wrong leave_days: {summary['leave_days']}")
    chk(summary["late_days"] == 1, f"late_days == 1 (got {summary['late_days']})", f"Wrong late_days: {summary['late_days']}")
    chk(summary["overtime_days"] == 1, f"overtime_days == 1 (got {summary['overtime_days']})", f"Wrong overtime_days: {summary['overtime_days']}")
    chk(summary["total_working_minutes"] == 1200, f"total_working_minutes == 1200 (got {summary['total_working_minutes']})", f"Wrong total_working_minutes: {summary['total_working_minutes']}")
    chk(summary["total_overtime_minutes"] == 30, f"total_overtime_minutes == 30 (got {summary['total_overtime_minutes']})", f"Wrong total_overtime_minutes: {summary['total_overtime_minutes']}")

    # [8] Date filtering in summary
    print("\n[8] get_attendance_summary with date filters")
    filtered_summary = attendance_service.get_attendance_summary(
        db, emp1.id, start_date=date(2024, 11, 1), end_date=date(2024, 11, 2)
    )
    chk(filtered_summary["total_days"] == 2, "filtered total_days == 2", f"Got {filtered_summary['total_days']}")
    chk(filtered_summary["total_working_minutes"] == 960, "filtered working_minutes == 960", f"Got {filtered_summary['total_working_minutes']}")

    # [9] Invalid date range raises InvalidDateRangeError
    print("\n[9] get_attendance_summary invalid date range raises InvalidDateRangeError")
    range_raised = False
    try:
        attendance_service.get_attendance_summary(
            db, emp1.id, start_date=date(2024, 11, 10), end_date=date(2024, 11, 1)
        )
    except InvalidDateRangeError:
        range_raised = True
    chk(range_raised, "InvalidDateRangeError raised", "Did not raise InvalidDateRangeError")

    # [10] Empty employee summary gives zero counts
    print("\n[10] get_attendance_summary for empty employee gives zero")
    empty_summary = attendance_service.get_attendance_summary(db, emp2.id)
    chk(empty_summary["total_days"] == 0, "total_days == 0", f"Got {empty_summary['total_days']}")
    chk(empty_summary["total_working_minutes"] == 0, "working_minutes == 0", f"Got {empty_summary['total_working_minutes']}")

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
