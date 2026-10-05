"""
tests/test_chat_api.py
----------------------
Integration tests for POST /chat endpoint.

Tests:
1. Authentication: Unauthorized requests return 401.
2. Input validation: Empty or blank questions return 400.
3. Authenticated employee allowed inquiries (own attendance, own salary).
4. HR company-wide inquiries (Aman's August attendance, Rahul's overtime, company payroll summary).
5. RBAC data isolation: Employee cannot access another employee's salary (access denied, LLM not invoked).
6. Data grounding verification: Prompt passed to mock LLM contains real database context.
7. Policy inquiries: Context passed to mock LLM comes from policies.json.
8. Non-existent records: Grounding indicates unavailable data without fabrication.
9. Provider failure safety: LLMProviderError returns friendly fallback without crashing.
10. Immutable chat logging: chat_logs table records interaction details and timing.
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient

from app.ai.llm import LLMProviderError
from app.database.connection import SessionLocal
from app.database.models import ChatLog, User
from app.main import app
from tests.helpers import TrackingClient
from app.utils.security import create_access_token

db = SessionLocal()
# TrackingClient removes the chat_logs rows this test causes (tests must leave the dev DB unchanged)
client = TrackingClient(app, db)

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
    print("  POST /chat - Integration Test Suite")
    print(SEP)

    # Fetch seeded users for tokens
    aman_user = db.query(User).filter(User.email == "aman@company.com").first()
    neha_hr = db.query(User).filter(User.email == "neha.hr@company.com").first()
    rahul_user = db.query(User).filter(User.email == "rahul@company.com").first()

    aman_token = create_access_token(user_id=aman_user.id, role=aman_user.role)
    hr_token = create_access_token(user_id=neha_hr.id, role=neha_hr.role)

    aman_headers = {"Authorization": f"Bearer {aman_token}"}
    hr_headers = {"Authorization": f"Bearer {hr_token}"}

    # -----------------------------------------------------------------------
    # [1] Authentication & Input Validation
    # -----------------------------------------------------------------------
    print("\n[1] Authentication & Input Validation")

    # 1.1 Unauthenticated request returns 401
    r_no_auth = client.post("/chat", json={"question": "What is the leave policy?"})
    chk(r_no_auth.status_code == 401, "Unauthenticated request returns 401 Unauthorized", f"Status: {r_no_auth.status_code}")

    # 1.2 Empty question returns 400
    r_empty = client.post("/chat", json={"question": "   "}, headers=aman_headers)
    chk(r_empty.status_code == 400, "Blank question returns 400 Bad Request", f"Status: {r_empty.status_code}")

    # -----------------------------------------------------------------------
    # [2] Policy Inquiry from policies.json
    # -----------------------------------------------------------------------
    print("\n[2] Policy Inquiry from policies.json")
    with patch("app.api.chat.generate_response") as mock_llm:
        mock_llm.return_value = "Employees are entitled to 12 casual leaves and 10 sick leaves annually."
        q = "What is the company leave policy?"
        r_policy = client.post("/chat", json={"question": q}, headers=aman_headers)

        chk(r_policy.status_code == 200, "Policy inquiry returns 200 OK", f"Status: {r_policy.status_code}")
        data = r_policy.json()
        chk(data.get("intent") == "POLICY", "Intent classified as POLICY", f"Got: {data.get('intent')}")
        chk("12 casual leaves" in data.get("answer", ""), "Answer contains generated policy summary", f"Got: {data}")

        # Verify mock received policies.json content
        called_prompt = mock_llm.call_args[1].get("prompt") or mock_llm.call_args[0][0]
        chk("annual_entitlements" in called_prompt, "Mock LLM received policies.json context", "Context missing")

    # -----------------------------------------------------------------------
    # [3] HR Inquiries: Aman's August Attendance (PRD Query)
    # -----------------------------------------------------------------------
    print("\n[3] HR Inquiry: Aman's August Attendance (PRD Query)")
    with patch("app.api.chat.generate_response") as mock_llm:
        mock_llm.return_value = "Aman was present for 22 days in August 2024, with 2 absences and 4 late clock-ins."
        q = "How many days was Aman present in August?"
        r_aman_att = client.post("/chat", json={"question": q}, headers=hr_headers)

        chk(r_aman_att.status_code == 200, "HR query returns 200 OK", f"Status: {r_aman_att.status_code}")
        data = r_aman_att.json()
        chk(data.get("intent") == "ATTENDANCE", "Intent classified as ATTENDANCE", f"Got: {data.get('intent')}")

        called_prompt = mock_llm.call_args[1].get("prompt") or mock_llm.call_args[0][0]
        chk("Present Days: 22" in called_prompt, "Prompt contains verified 22 Present Days from MySQL", f"Prompt:\n{called_prompt}")
        chk("Absent Days: 2" in called_prompt, "Prompt contains verified 2 Absent Days from MySQL", f"Prompt:\n{called_prompt}")
        chk("Late Clock-Ins: 4" in called_prompt, "Prompt contains verified 4 Late Clock-Ins from MySQL", f"Prompt:\n{called_prompt}")

    # -----------------------------------------------------------------------
    # [4] HR Inquiry: Rahul's September Overtime (PRD Query)
    # -----------------------------------------------------------------------
    print("\n[4] HR Inquiry: Rahul's September Overtime (PRD Query)")
    with patch("app.api.chat.generate_response") as mock_llm:
        mock_llm.return_value = "Rahul Sharma worked 1,115 minutes (18 hours 35 minutes) of overtime in September 2024."
        q = "What is Rahul's overtime in September?"
        r_rahul_ot = client.post("/chat", json={"question": q}, headers=hr_headers)

        chk(r_rahul_ot.status_code == 200, "Rahul overtime returns 200 OK", f"Status: {r_rahul_ot.status_code}")
        called_prompt = mock_llm.call_args[1].get("prompt") or mock_llm.call_args[0][0]
        chk("1,115 minutes" in called_prompt or "1115 minutes" in called_prompt,
            "Prompt contains verified 1,115 minutes overtime from MySQL", f"Prompt:\n{called_prompt}")
        chk("18 hours 35 minutes" in called_prompt,
            "Prompt contains verified 18 hours 35 minutes conversion", f"Prompt:\n{called_prompt}")

    # -----------------------------------------------------------------------
    # [5] Authenticated Employee: Access Own Salary (Allowed)
    # -----------------------------------------------------------------------
    print("\n[5] Authenticated Employee: Access Own Salary")
    with patch("app.api.chat.generate_response") as mock_llm:
        mock_llm.return_value = "Your latest net salary for September 2024 is ₹90,200.00."
        q = "What is my latest salary?"
        r_sal = client.post("/chat", json={"question": q}, headers=aman_headers)

        chk(r_sal.status_code == 200, "Employee salary query returns 200 OK", f"Status: {r_sal.status_code}")
        called_prompt = mock_llm.call_args[1].get("prompt") or mock_llm.call_args[0][0]
        chk("Aman Gupta" in called_prompt and "Gross Salary:" in called_prompt,
            "Prompt passed Aman's salary slip to LLM", f"Prompt:\n{called_prompt}")

    # -----------------------------------------------------------------------
    # [6] RBAC Data Isolation: Employee Cannot Access Another's Salary
    # -----------------------------------------------------------------------
    print("\n[6] RBAC Data Isolation: Employee Blocked from Another Employee's Salary")
    with patch("app.api.chat.generate_response") as mock_llm:
        q = "What is Rahul's salary?"
        r_denied = client.post("/chat", json={"question": q}, headers=aman_headers)

        chk(r_denied.status_code == 200, "Denied query returns 200 OK response with refusal", f"Status: {r_denied.status_code}")
        data = r_denied.json()
        chk("Access denied" in data.get("answer", ""),
            "Response explicitly denies unauthorized salary access", f"Answer: {data.get('answer')}")
        chk(not mock_llm.called, "LLM was NOT called on unauthorized inquiry (no data leakage)", "LLM was called!")

    # -----------------------------------------------------------------------
    # [7] Anti-Hallucination: Non-Existent Employee Data
    # -----------------------------------------------------------------------
    print("\n[7] Anti-Hallucination: Non-Existent Employee Inquiry")
    with patch("app.api.chat.generate_response") as mock_llm:
        mock_llm.return_value = "I could not find any employee named Bruce Wayne in our records."
        q = "What is the designation of Bruce Wayne?"
        r_ghost = client.post("/chat", json={"question": q}, headers=hr_headers)

        chk(r_ghost.status_code == 200, "Non-existent inquiry returns 200 OK", f"Status: {r_ghost.status_code}")
        called_prompt = mock_llm.call_args[1].get("prompt") or mock_llm.call_args[0][0]
        chk("No employee record found" in called_prompt,
            "Prompt explicitly indicates employee not found to prevent hallucination", f"Prompt:\n{called_prompt}")

    # -----------------------------------------------------------------------
    # [8] Safe LLM Provider Failure Handling
    # -----------------------------------------------------------------------
    print("\n[8] Safe LLM Provider Failure Handling")
    with patch("app.api.chat.generate_response") as mock_llm:
        mock_llm.side_effect = LLMProviderError("External LLM API network timeout")
        q = "What are the standard working hours?"
        r_err = client.post("/chat", json={"question": q}, headers=aman_headers)

        chk(r_err.status_code == 200, "Provider failure returns graceful 200 OK fallback", f"Status: {r_err.status_code}")
        data = r_err.json()
        chk("temporarily unavailable" in data.get("answer", ""),
            "Fallback answer informs user of temporary issue without crashing", f"Answer: {data.get('answer')}")

    # -----------------------------------------------------------------------
    # [9] Immutable Chat Logging
    # -----------------------------------------------------------------------
    print("\n[9] Immutable Chat Logging in chat_logs Table")
    db.commit()
    latest_log = (
        db.query(ChatLog)
        .filter(ChatLog.user_id == aman_user.id)
        .order_by(ChatLog.id.desc())
        .first()
    )
    chk(latest_log is not None, "ChatLog row created in MySQL database", "No ChatLog row found")
    chk(latest_log.question == "What are the standard working hours?", "ChatLog recorded exact user question", f"Got: {latest_log.question}")
    chk(latest_log.detected_intent == "POLICY", "ChatLog recorded detected_intent POLICY", f"Got: {latest_log.detected_intent}")
    # Policy answers come from an uploaded document when one matches (RAG), else policies.json
    chk(latest_log.data_source == "policies.json" or latest_log.data_source.endswith((".pdf", ".docx", ".txt")),
        "ChatLog recorded policy data_source (policies.json or document)", f"Got: {latest_log.data_source}")
    chk(latest_log.response_time_ms is not None and latest_log.response_time_ms >= 0,
        f"ChatLog recorded response_time_ms ({latest_log.response_time_ms}ms)", "Missing response_time_ms")
    chk(latest_log.error is not None and "network timeout" in latest_log.error,
        "ChatLog recorded provider error message", f"Error: {latest_log.error}")

    print("\n" + SEP)
    print(f"  Results: {passed} passed, {failed} failed")
    print(SEP)

except Exception as exc:
    print(f"\n[ERROR] Exception occurred: {exc}")
    import traceback
    traceback.print_exc()
    failed += 1
finally:
    client.cleanup_chat_logs()
    db.close()

if failed > 0:
    sys.exit(1)
else:
    sys.exit(0)
