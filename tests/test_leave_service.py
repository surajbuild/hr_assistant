import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from datetime import date
from app.database.connection import SessionLocal
from app.database.models import Employee, User, Leave, LeaveStatus
from app.database.queries import create_employee, create_user
from app.services import leave_service
from app.services.leave_service import (
    EmployeeNotFoundError,
    InvalidLeaveDateError,
    LeaveNotFoundError,
    LeaveStatusError,
)

db = SessionLocal()

TEST_EMP_CODE_SVC_1 = "SVC-LEV-001"
TEST_EMAIL_SVC_1 = "svc.lev1@hr.dev"

TEST_EMP_CODE_SVC_2 = "SVC-LEV-002"
TEST_EMAIL_SVC_2 = "svc.lev2@hr.dev"

def cleanup():
    for email in [TEST_EMAIL_SVC_1, TEST_EMAIL_SVC_2]:
        u = db.query(User).filter(User.email == email).first()
        if u:
            db.query(Leave).filter(Leave.employee_id == u.employee_id).delete()
            db.delete(u)
    for code in [TEST_EMP_CODE_SVC_1, TEST_EMP_CODE_SVC_2]:
        e = db.query(Employee).filter(Employee.employee_code == code).first()
        if e:
            db.query(Leave).filter(Leave.employee_id == e.id).delete()
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
    print("  Leave Service Layer - Unit & Business Logic Test")
    print(SEP)
    cleanup()

    # Create test employee 1 & approver user
    emp1 = create_employee(
        db, employee_code=TEST_EMP_CODE_SVC_1, name="Leave Svc User 1",
        department="Engineering", designation="Tester", joining_date=date(2024, 1, 1)
    )
    user1 = create_user(db, employee_id=emp1.id, email=TEST_EMAIL_SVC_1, password_hash="hash", role="employee")

    emp2 = create_employee(
        db, employee_code=TEST_EMP_CODE_SVC_2, name="Leave Svc User 2",
        department="HR", designation="HR Manager", joining_date=date(2024, 1, 1)
    )
    user2 = create_user(db, employee_id=emp2.id, email=TEST_EMAIL_SVC_2, password_hash="hash", role="hr")

    # [1] create_leave_request: valid creation
    print("\n[1] create_leave_request creates record with 'pending' status")
    l1 = leave_service.create_leave_request(
        db,
        employee_id=emp1.id,
        leave_type="casual",
        from_date=date(2024, 12, 1),
        to_date=date(2024, 12, 2),
        reason="Family event",
    )
    chk(l1.id is not None, "l1 has ID", "Creation failed")
    chk(l1.status == "pending", "status is pending", f"Got status {l1.status}")
    chk(l1.employee_id == emp1.id, "employee_id matches", f"Got {l1.employee_id}")

    # [2] create_leave_request: invalid date range raises InvalidLeaveDateError
    print("\n[2] create_leave_request start_date > end_date raises InvalidLeaveDateError")
    bad_date_raised = False
    try:
        leave_service.create_leave_request(
            db,
            employee_id=emp1.id,
            leave_type="casual",
            from_date=date(2024, 12, 10),
            to_date=date(2024, 12, 1),
        )
    except InvalidLeaveDateError:
        bad_date_raised = True
    chk(bad_date_raised, "InvalidLeaveDateError raised", "Did not raise InvalidLeaveDateError")

    # [3] create_leave_request: non-existent employee raises EmployeeNotFoundError
    print("\n[3] create_leave_request non-existent employee raises EmployeeNotFoundError")
    emp_not_found = False
    try:
        leave_service.create_leave_request(
            db,
            employee_id=999999,
            leave_type="casual",
            from_date=date(2024, 12, 5),
            to_date=date(2024, 12, 6),
        )
    except EmployeeNotFoundError:
        emp_not_found = True
    chk(emp_not_found, "EmployeeNotFoundError raised", "Did not raise EmployeeNotFoundError")

    # [4] get_leave_by_id
    print("\n[4] get_leave_by_id returns leave and None for missing")
    found_l = leave_service.get_leave_by_id(db, l1.id)
    missing_l = leave_service.get_leave_by_id(db, 888888)
    chk(found_l is not None and found_l.id == l1.id, "found_l matches l1", "Failed to find leave")
    chk(missing_l is None, "missing_l is None", "Expected None for non-existent leave")

    # [5] get_leaves_by_employee_id & get_my_leaves
    print("\n[5] get_leaves_by_employee_id and get_my_leaves")
    l_list1 = leave_service.get_leaves_by_employee_id(db, emp1.id)
    my_l1 = leave_service.get_my_leaves(db, emp1.id)
    chk(len(l_list1) == 1 and l_list1[0].id == l1.id, "l_list1 has 1 record", f"Got {len(l_list1)}")
    chk(len(my_l1) == 1, "my_l1 has 1 record", f"Got {len(my_l1)}")

    # Empty employee gets []
    l_list2 = leave_service.get_leaves_by_employee_id(db, emp2.id)
    chk(l_list2 == [], "empty employee returns []", f"Got {l_list2}")

    # [6] get_leaves_for_employee validates existence
    print("\n[6] get_leaves_for_employee validates employee existence")
    for_emp = leave_service.get_leaves_for_employee(db, emp1.id)
    chk(len(for_emp) == 1, "get_leaves_for_employee returns records", f"Got {len(for_emp)}")

    missing_raised = False
    try:
        leave_service.get_leaves_for_employee(db, 777777)
    except EmployeeNotFoundError:
        missing_raised = True
    chk(missing_raised, "EmployeeNotFoundError raised for missing employee", "Did not raise EmployeeNotFoundError")

    # [7] update_leave_status: approve pending leave
    print("\n[7] update_leave_status approves pending leave")
    approved_l = leave_service.update_leave_status(
        db,
        leave_id=l1.id,
        status="approved",
        approved_by_user_id=user2.id,
    )
    chk(approved_l.status == "approved", "status updated to approved", f"Got {approved_l.status}")
    chk(approved_l.approved_by == user2.id, "approved_by set to user2", f"Got {approved_l.approved_by}")

    # [8] update_leave_status: already approved cannot be updated again
    print("\n[8] update_leave_status on non-pending raises LeaveStatusError")
    non_pending_raised = False
    try:
        leave_service.update_leave_status(
            db,
            leave_id=l1.id,
            status="rejected",
            approved_by_user_id=user2.id,
        )
    except LeaveStatusError as exc:
        non_pending_raised = True
        chk("Cannot update leave status" in str(exc), "error message matches", f"Got {exc}")
    chk(non_pending_raised, "LeaveStatusError raised", "Did not raise LeaveStatusError")

    # [9] update_leave_status: reject pending leave
    print("\n[9] update_leave_status rejects a second pending leave")
    l2 = leave_service.create_leave_request(
        db,
        employee_id=emp1.id,
        leave_type="sick",
        from_date=date(2024, 12, 10),
        to_date=date(2024, 12, 11),
    )
    rejected_l = leave_service.update_leave_status(
        db,
        leave_id=l2.id,
        status="rejected",
        approved_by_user_id=user2.id,
    )
    chk(rejected_l.status == "rejected", "status updated to rejected", f"Got {rejected_l.status}")
    chk(rejected_l.approved_by == user2.id, "approved_by set to user2", f"Got {rejected_l.approved_by}")

    # [10] update_leave_status: non-existent leave raises LeaveNotFoundError
    print("\n[10] update_leave_status non-existent leave raises LeaveNotFoundError")
    not_found_raised = False
    try:
        leave_service.update_leave_status(
            db,
            leave_id=999999,
            status="approved",
            approved_by_user_id=user2.id,
        )
    except LeaveNotFoundError:
        not_found_raised = True
    chk(not_found_raised, "LeaveNotFoundError raised", "Did not raise LeaveNotFoundError")

    # [11] update_leave_status: invalid target status raises LeaveStatusError
    print("\n[11] update_leave_status invalid target status raises LeaveStatusError")
    l3 = leave_service.create_leave_request(
        db,
        employee_id=emp1.id,
        leave_type="casual",
        from_date=date(2024, 12, 20),
        to_date=date(2024, 12, 21),
    )
    invalid_status_raised = False
    try:
        leave_service.update_leave_status(
            db,
            leave_id=l3.id,
            status="cancelled",
            approved_by_user_id=user2.id,
        )
    except LeaveStatusError:
        invalid_status_raised = True
    chk(invalid_status_raised, "LeaveStatusError raised for invalid status", "Did not raise LeaveStatusError")

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
