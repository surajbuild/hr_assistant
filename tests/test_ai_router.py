"""
tests/test_ai_router.py
-----------------------
Unit and service tests for AI Intent Classifier, Entity Extractor, and Controlled HR Data Access.
"""

import os
import sys

sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from app.ai.guardrails import check_rbac_access
from app.ai.router import (
    Intent,
    classify_intent,
    extract_month_and_year,
    find_target_employee,
    retrieve_hr_context,
)
from app.database.connection import SessionLocal
from app.database.models import Employee, User, UserRole

db = SessionLocal()

SEP = "-" * 55
passed = 0
failed = 0


def chk(ok: bool, ok_msg: str, fail_msg: str):
    global passed, failed
    if ok:
        print(f"    PASS - {ok_msg}")
        passed += 1
    else:
        print(f"    FAIL - {fail_msg}")
        failed += 1


try:
    print(SEP)
    print("  AI Intent Detection & Router - Unit Tests")
    print(SEP)

    # -----------------------------------------------------------------------
    # [1] Intent Detection: ATTENDANCE
    # -----------------------------------------------------------------------
    print("\n[1] Intent Detection: ATTENDANCE")
    chk(classify_intent("How many days was Aman present in August?") == Intent.ATTENDANCE,
        "Classified 'How many days was Aman present in August?' as ATTENDANCE", "Mismatch")
    chk(classify_intent("What is Rahul's overtime?") == Intent.ATTENDANCE,
        "Classified 'What is Rahul's overtime?' as ATTENDANCE", "Mismatch")
    chk(classify_intent("Did I have any late entries this month?") == Intent.ATTENDANCE,
        "Classified 'Did I have any late entries this month?' as ATTENDANCE", "Mismatch")
    chk(classify_intent("Check my clock in attendance for yesterday") == Intent.ATTENDANCE,
        "Classified clock in inquiry as ATTENDANCE", "Mismatch")

    # -----------------------------------------------------------------------
    # [2] Intent Detection: LEAVE
    # -----------------------------------------------------------------------
    print("\n[2] Intent Detection: LEAVE")
    chk(classify_intent("Show my leave history and applied leaves") == Intent.LEAVE,
        "Classified 'Show my leave history' as LEAVE", "Mismatch")
    chk(classify_intent("What is my sick leave status?") == Intent.LEAVE,
        "Classified 'What is my sick leave status?' as LEAVE", "Mismatch")
    chk(classify_intent("Did my casual leave get approved?") == Intent.LEAVE,
        "Classified casual leave query as LEAVE", "Mismatch")

    # -----------------------------------------------------------------------
    # [3] Intent Detection: SALARY
    # -----------------------------------------------------------------------
    print("\n[3] Intent Detection: SALARY")
    chk(classify_intent("What is my latest salary slip?") == Intent.SALARY,
        "Classified 'What is my latest salary slip?' as SALARY", "Mismatch")
    chk(classify_intent("Show payslip for August 2024") == Intent.SALARY,
        "Classified 'Show payslip for August 2024' as SALARY", "Mismatch")
    chk(classify_intent("What are the total PF deductions on my pay?") == Intent.SALARY,
        "Classified PF deductions query as SALARY", "Mismatch")
    chk(classify_intent("How much net salary was credited last month?") == Intent.SALARY,
        "Classified net salary query as SALARY", "Mismatch")

    # -----------------------------------------------------------------------
    # [4] Intent Detection: EMPLOYEE
    # -----------------------------------------------------------------------
    print("\n[4] Intent Detection: EMPLOYEE")
    chk(classify_intent("Who is the reporting manager of Aman?") == Intent.EMPLOYEE,
        "Classified 'Who is the reporting manager of Aman?' as EMPLOYEE", "Mismatch")
    chk(classify_intent("What is Rahul's department and designation?") == Intent.EMPLOYEE,
        "Classified department/designation query as EMPLOYEE", "Mismatch")
    chk(classify_intent("When was my joining date?") == Intent.EMPLOYEE,
        "Classified joining date query as EMPLOYEE", "Mismatch")

    # -----------------------------------------------------------------------
    # [5] Intent Detection: POLICY
    # -----------------------------------------------------------------------
    print("\n[5] Intent Detection: POLICY")
    chk(classify_intent("What is the company leave policy?") == Intent.POLICY,
        "Classified 'What is the company leave policy?' as POLICY", "Mismatch")
    chk(classify_intent("What are the standard working hours and lunch break?") == Intent.POLICY,
        "Classified working hours query as POLICY", "Mismatch")
    chk(classify_intent("Explain the overtime policy and compensation rules") == Intent.POLICY,
        "Classified overtime policy query as POLICY", "Mismatch")
    chk(classify_intent("What are the company attendance rules for late clock-in?") == Intent.POLICY,
        "Classified attendance rules query as POLICY", "Mismatch")
    chk(classify_intent("What is the official holiday list?") == Intent.POLICY,
        "Classified holiday list query as POLICY", "Mismatch")

    # -----------------------------------------------------------------------
    # [6] Intent Detection: GENERAL & UNKNOWN
    # -----------------------------------------------------------------------
    print("\n[6] Intent Detection: GENERAL & UNKNOWN")
    chk(classify_intent("Hello, who are you?") == Intent.GENERAL,
        "Classified 'Hello, who are you?' as GENERAL", "Mismatch")
    chk(classify_intent("Hi there, how can you help me?") == Intent.GENERAL,
        "Classified greeting/help as GENERAL", "Mismatch")
    chk(classify_intent("Tell me a random poem about bicycles") == Intent.UNKNOWN,
        "Classified off-topic query as UNKNOWN", "Mismatch")

    # -----------------------------------------------------------------------
    # [7] Entity Extraction: Month and Year
    # -----------------------------------------------------------------------
    print("\n[7] Entity Extraction: Month and Year")
    m1, y1 = extract_month_and_year("How many days was Aman present in August 2024?")
    chk(m1 == 8 and y1 == 2024, "Extracted August 2024 -> (8, 2024)", f"Got ({m1}, {y1})")

    m2, y2 = extract_month_and_year("What was the overtime in September?")
    chk(m2 == 9 and y2 is None, "Extracted September -> (9, None): the year is resolved from data (D-029)", f"Got ({m2}, {y2})")

    m3, _ = extract_month_and_year("May I see my attendance?")
    chk(m3 is None, "'May I…' is not read as the month of May", f"Got month {m3}")

    # resolve_period with a fixed "today" so the expectations don't depend on the calendar
    from datetime import date
    from app.ai.router import resolve_period
    from app.services.attendance_service import get_months_with_data

    periods = get_months_with_data(db)
    fixed_today = date(2030, 6, 15)  # no data that late → exercises the fallbacks
    latest_y, latest_m = max(p for p in periods if p <= (2030, 6))
    rm, ry, note = resolve_period(db, "What is my attendance this month?", today=fixed_today)
    chk((rm, ry) == (latest_m, latest_y) and note and "no records yet" in note,
        "'this month' without data falls back to the latest month with data (with a note)", f"Got ({rm}, {ry}, {note})")
    rm, ry, note = resolve_period(db, "Attendance this month", today=date(latest_y, latest_m, 1))
    chk((rm, ry, note) == (latest_m, latest_y, None), "'this month' with data = the current month, no note", f"Got ({rm}, {ry}, {note})")
    rm, ry, _ = resolve_period(db, "How was my attendance last month?", today=date(2027, 1, 10))
    chk((rm, ry) == (12, 2026), "'last month' in January = December of the previous year", f"Got ({rm}, {ry})")
    sept_years = [y for y, m in periods if m == 9 and (y, m) <= (2030, 6)]
    rm, ry, note = resolve_period(db, "What was the overtime in September?", today=fixed_today)
    chk(rm == 9 and ry == max(sept_years) and "most recent September" in (note or ""),
        f"Month without year -> most recent September with records ({max(sept_years)})", f"Got ({rm}, {ry}, {note})")
    rm, ry, _ = resolve_period(db, "Overtime in November?", today=date(2010, 3, 1))
    chk((rm, ry) == (11, 2009), "Month without year and no data -> most recent past November by calendar", f"Got ({rm}, {ry})")
    rm, ry, _ = resolve_period(db, "Show payslip for August 2024")
    chk((rm, ry) == (8, 2024), "Explicit month + year kept as given", f"Got ({rm}, {ry})")

    # -----------------------------------------------------------------------
    # [8] Controlled Data Retrieval & Grounding
    # -----------------------------------------------------------------------
    print("\n[8] Controlled Data Retrieval from MySQL & policies.json")

    # Users for testing
    hr_user = db.query(User).filter(User.email == "neha.hr@company.com").first()
    aman_user = db.query(User).filter(User.email == "aman@company.com").first()
    rahul_user = db.query(User).filter(User.email == "rahul@company.com").first()

    # 8.1 Policy retrieval
    ctx_pol, src_pol, err_pol = retrieve_hr_context(
        db, aman_user, Intent.POLICY, "What is the company leave policy?"
    )
    chk(src_pol == "policies.json" and "annual_entitlements" in ctx_pol,
        "Policy data loaded from policies.json with entitlements", f"Source: {src_pol}")

    # 8.2 Aman August Attendance retrieval by HR
    ctx_att, src_att, err_att = retrieve_hr_context(
        db, hr_user, Intent.ATTENDANCE, "How many days was Aman present in August 2024?"
    )
    chk("Present Days: 22" in ctx_att, "Aman August context contains 'Present Days: 22'", f"Got:\n{ctx_att}")
    chk("Absent Days: 2" in ctx_att, "Aman August context contains 'Absent Days: 2'", f"Got:\n{ctx_att}")
    chk("Late Clock-Ins: 4" in ctx_att, "Aman August context contains 'Late Clock-Ins: 4'", f"Got:\n{ctx_att}")
    chk(src_att == "attendance_database", "Source is attendance_database", f"Got: {src_att}")

    # 8.3 Rahul September Overtime retrieval by HR
    ctx_ot, src_ot, err_ot = retrieve_hr_context(
        db, hr_user, Intent.ATTENDANCE, "What is Rahul's overtime in September 2024?"
    )
    chk("1115 minutes" in ctx_ot or "1,115 minutes" in ctx_ot,
        "Rahul September context contains 1,115 minutes overtime", f"Got:\n{ctx_ot}")
    chk("18 hours 35 minutes" in ctx_ot or "18 hours" in ctx_ot,
        "Rahul September context contains 18 hours 35 minutes", f"Got:\n{ctx_ot}")

    # 8.4 Aman queries own salary (Allowed)
    ctx_my_sal, src_my_sal, err_my_sal = retrieve_hr_context(
        db, aman_user, Intent.SALARY, "What is my latest salary?"
    )
    chk(err_my_sal is None and "Aman Gupta" in ctx_my_sal and "₹" in ctx_my_sal,
        "Aman successfully retrieved own salary details", f"Err: {err_my_sal}")

    # 8.5 Aman queries Rahul's salary (FORBIDDEN)
    ctx_denied, src_denied, err_denied = retrieve_hr_context(
        db, aman_user, Intent.SALARY, "What is Rahul's salary?"
    )
    chk(err_denied is not None and "Access denied" in ctx_denied,
        "Employee blocked from viewing another employee's salary", f"Got: {ctx_denied}")

    # 8.6 HR queries Rahul's salary (ALLOWED)
    ctx_hr_sal, src_hr_sal, err_hr_sal = retrieve_hr_context(
        db, hr_user, Intent.SALARY, "What is Rahul's salary in August 2024?"
    )
    chk(err_hr_sal is None and "Rahul Sharma" in ctx_hr_sal,
        "HR successfully retrieved Rahul's salary details", f"Err: {err_hr_sal}")

    # 8.7 Non-existent employee query does not invent data
    ctx_ghost, src_ghost, _ = retrieve_hr_context(
        db, hr_user, Intent.EMPLOYEE, "What is the designation of John Unknown?"
    )
    chk("No employee record found" in ctx_ghost,
        "Non-existent employee inquiry states record not found", f"Got: {ctx_ghost}")

    print("\n" + SEP)
    print(f"  Results: {passed} passed, {failed} failed")
    print(SEP)

except Exception as exc:
    print(f"\n[ERROR] Exception occurred: {exc}")
    import traceback
    traceback.print_exc()
    failed += 1
finally:
    db.close()

if failed > 0:
    sys.exit(1)
else:
    sys.exit(0)
