import sys, os, textwrap
sys.path.insert(0, os.path.dirname(os.path.abspath('.')))
from datetime import date
from app.database.connection import SessionLocal
from app.database.queries import (
    create_employee, get_employee_by_id,
    create_user, get_user_by_email, get_user_by_id,
)
from app.database.models import Employee, User

TEST_EMPLOYEE_CODE = 'TEST-EMP-001'
TEST_EMAIL = 'test.user@hr-assistant.dev'
TEST_PASSWORD_HASH = 'hashed_password_placeholder'
SEP = '-' * 55


def cleanup(db, employee_code, email):
    user = db.query(User).filter(User.email == email).first()
    if user:
        db.delete(user)
    emp = db.query(Employee).filter(Employee.employee_code == employee_code).first()
    if emp:
        db.delete(emp)
    db.commit()
    print('  [cleanup] Test rows removed.')


def run_tests():
    db = SessionLocal()
    passed = 0
    failed = 0
    try:
        print(SEP)
        print('  AI HR Assistant - Database Layer Test')
        print(SEP)
        print('\n[0] Pre-run cleanup ...')
        cleanup(db, TEST_EMPLOYEE_CODE, TEST_EMAIL)

        print('\n[1] create_employee()')
        emp = create_employee(
            db,
            employee_code=TEST_EMPLOYEE_CODE,
            name='Test User',
            department='Engineering',
            designation='Software Engineer',
            joining_date=date(2024, 1, 15),
        )
        if emp and emp.id:
            print('    PASS - Employee created. id=' + str(emp.id))
            passed += 1
        else:
            print('    FAIL - create_employee returned None')
            failed += 1
            return

        print('\n[2] get_employee_by_id()')
        fetched_emp = get_employee_by_id(db, emp.id)
        if fetched_emp and fetched_emp.name == 'Test User':
            print('    PASS - Fetched employee: id=' + str(fetched_emp.id))
            passed += 1
        else:
            print('    FAIL - get_employee_by_id wrong result')
            failed += 1

        print('\n[3] create_user()')
        user = create_user(
            db,
            employee_id=emp.id,
            email=TEST_EMAIL,
            password_hash=TEST_PASSWORD_HASH,
        )
        if user and user.id:
            print('    PASS - User created. id=' + str(user.id) + ' role=' + user.role)
            passed += 1
        else:
            print('    FAIL - create_user returned None')
            failed += 1
            return

        print('\n[4] get_user_by_email()')
        by_email = get_user_by_email(db, TEST_EMAIL)
        if by_email and by_email.id == user.id:
            print('    PASS - by email: id=' + str(by_email.id))
            passed += 1
        else:
            print('    FAIL - get_user_by_email wrong result')
            failed += 1

        print('\n[5] get_user_by_id()')
        by_id = get_user_by_id(db, user.id)
        if by_id and by_id.email == TEST_EMAIL:
            print('    PASS - by id: id=' + str(by_id.id) + ' email=' + by_id.email)
            passed += 1
        else:
            print('    FAIL - get_user_by_id wrong result')
            failed += 1

    except Exception as exc:
        print('\n  EXCEPTION: ' + str(exc))
        db.rollback()
        failed += 1
        raise
    finally:
        print('\n[cleanup] Removing test data ...')
        cleanup(db, TEST_EMPLOYEE_CODE, TEST_EMAIL)
        db.close()
        print(SEP)
        print('  Results: ' + str(passed) + ' passed, ' + str(failed) + ' failed')
        print(SEP)
        if failed:
            sys.exit(1)


if __name__ == '__main__':
    run_tests()
