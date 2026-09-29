"""
scripts/smoke_test_chat.py
--------------------------
Comprehensive live end-to-end smoke test for POST /chat using real OpenRouter LLM,
real JWT authentication, and live seeded MySQL HR data.
"""

import sys
import httpx

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8")

from app.database.connection import SessionLocal
from app.database.models import ChatLog

BASE_URL = "http://127.0.0.1:8000"


def run_smoke_tests():
    print("=" * 80)
    print("  LIVE SMOKE TEST: FastAPI + Real LLM + Seeded MySQL HR Data")
    print("=" * 80)

    # 1. Login Neha (HR)
    r_hr_login = httpx.post(
        f"{BASE_URL}/auth/login",
        json={"email": "neha.hr@company.com", "password": "Demo@12345"},
        timeout=10.0,
    )
    if r_hr_login.status_code != 200:
        print(f"[ERROR] HR login failed: {r_hr_login.status_code} - {r_hr_login.text}")
        return
    hr_token = r_hr_login.json()["access_token"]
    hr_headers = {"Authorization": f"Bearer {hr_token}"}

    # 2. Login Aman (Employee)
    r_aman_login = httpx.post(
        f"{BASE_URL}/auth/login",
        json={"email": "aman@company.com", "password": "Demo@12345"},
        timeout=10.0,
    )
    if r_aman_login.status_code != 200:
        print(f"[ERROR] Aman login failed: {r_aman_login.status_code} - {r_aman_login.text}")
        return
    aman_token = r_aman_login.json()["access_token"]
    aman_headers = {"Authorization": f"Bearer {aman_token}"}

    test_cases = [
        # --- Core Demo Questions ---
        {
            "category": "Core Demo Question 1",
            "headers": hr_headers,
            "user": "Neha Verma (HR Manager)",
            "question": "How many days was Aman present in August?",
            "expected_source": "MySQL (attendance)",
        },
        {
            "category": "Core Demo Question 2",
            "headers": hr_headers,
            "user": "Neha Verma (HR Manager)",
            "question": "What is Rahul's overtime in September?",
            "expected_source": "MySQL (attendance)",
        },
        {
            "category": "Core Demo Question 3",
            "headers": aman_headers,
            "user": "Aman Gupta (Senior Software Engineer - Employee)",
            "question": "What is my latest salary?",
            "expected_source": "MySQL (salary)",
        },
        {
            "category": "Core Demo Question 4",
            "headers": aman_headers,
            "user": "Aman Gupta (Employee)",
            "question": "What is the company leave policy?",
            "expected_source": "policies.json",
        },
        # --- RBAC Security Scenarios ---
        {
            "category": "RBAC: Employee asks for own salary (Allowed)",
            "headers": aman_headers,
            "user": "Aman Gupta (Employee)",
            "question": "Can I see my salary for August 2024?",
            "expected_source": "MySQL (salary)",
        },
        {
            "category": "RBAC: Employee asks for another employee's salary (Blocked)",
            "headers": aman_headers,
            "user": "Aman Gupta (Employee)",
            "question": "What is Rahul's salary?",
            "expected_source": "RBAC Guardrail (Blocked)",
        },
        {
            "category": "RBAC: Employee asks for another employee's attendance (Blocked)",
            "headers": aman_headers,
            "user": "Aman Gupta (Employee)",
            "question": "What is Rahul's attendance?",
            "expected_source": "RBAC Guardrail (Blocked)",
        },
        {
            "category": "RBAC: HR asks for employee information (Allowed)",
            "headers": hr_headers,
            "user": "Neha Verma (HR Manager)",
            "question": "Tell me about employee Aman Gupta",
            "expected_source": "MySQL (employees)",
        },
        # --- Missing Data / Anti-Hallucination Scenario ---
        {
            "category": "Missing Data: Non-existent employee query",
            "headers": hr_headers,
            "user": "Neha Verma (HR Manager)",
            "question": "What is the salary of John Doe?",
            "expected_source": "MySQL (salary)",
        },
    ]

    results = []

    for tc in test_cases:
        print(f"\n[{tc['category']}]")
        print(f"Requester : {tc['user']}")
        print(f"Question  : {tc['question']}")

        resp = httpx.post(
            f"{BASE_URL}/chat",
            json={"question": tc["question"]},
            headers=tc["headers"],
            timeout=40.0,
        )
        status_code = resp.status_code
        print(f"HTTP Status: {status_code}")

        if status_code == 200:
            data = resp.json()
            intent = data.get("intent")
            answer = data.get("answer")
            print(f"Intent     : {intent}")
            print(f"Answer     : {answer}")
            results.append({
                "question": tc["question"],
                "intent": intent,
                "status": status_code,
                "answer": answer,
                "category": tc["category"],
            })
        else:
            print(f"Error      : {resp.text}")
            results.append({
                "question": tc["question"],
                "intent": "ERROR",
                "status": status_code,
                "answer": resp.text,
                "category": tc["category"],
            })

    # Verify chat_logs table in MySQL
    db = SessionLocal()
    db.commit()
    recent_logs = db.query(ChatLog).order_by(ChatLog.id.desc()).limit(len(test_cases)).all()
    print("\n" + "=" * 80)
    print("  VERIFICATION OF MySQL chat_logs TABLE")
    print("=" * 80)
    for log in reversed(recent_logs):
        print(f"Log ID: {log.id} | User ID: {log.user_id} | Intent: {log.detected_intent} | Source: {log.data_source} | Time: {log.response_time_ms}ms")
        print(f"  Question : {log.question}")
        print(f"  Response : {log.response[:100]}...")
        if log.error:
            print(f"  Error    : {log.error}")
        print("-" * 60)
    db.close()

    return results


if __name__ == "__main__":
    run_smoke_tests()
