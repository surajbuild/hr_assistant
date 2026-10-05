"""
tests/test_rbac_matrix.py
-------------------------
Complete Role-Based Access Control (RBAC) & Privacy Verification Test Suite.

Verifies:
1. Unauthorized requests return 401.
2. Authenticated but unauthorized role requests return 403.
3. Employee role permissions (own data allowed, other employee data restricted).
4. Manager role permissions (subordinate team data, leave approvals, salary restricted).
5. HR role permissions (HR-level company-wide access).
6. Admin role permissions (Full access across all modules).
7. AI /chat endpoint privacy & guardrail enforcement.
"""

import os
import sys
from datetime import date
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from tests.helpers import TrackingClient
from app.database.connection import SessionLocal
from app.database.models import Employee, Leave, LeaveStatus, User
from app.utils.security import create_access_token

db = SessionLocal()
# TrackingClient removes the chat_logs rows this test causes (tests must leave the dev DB unchanged)
client = TrackingClient(app, db)

# Counters
passed_count = 0
failed_count = 0


def chk(condition: bool, msg: str, fail_detail: str = ""):
    global passed_count, failed_count
    if condition:
        print(f"  [PASS] {msg}")
        passed_count += 1
    else:
        print(f"  [FAIL] {msg} -> {fail_detail}")
        failed_count += 1


def get_user_and_token(role: str, email: str = None):
    """Retrieve an active seeded user for the specified role and generate a JWT."""
    q = db.query(User).filter(User.role == role)
    if email:
        q = q.filter(User.email == email)
    user = q.first()
    if not user:
        raise RuntimeError(f"Required user with role '{role}' not found in database.")
    token = create_access_token(user_id=user.id, role=user.role)
    return user, token, {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Setup Users for the 4 Roles
# ---------------------------------------------------------------------------
# Seeded accounts:
# - Admin: Vikram Sharma (admin@company.com)
# - HR: Neha Verma (neha.hr@company.com)
# - Manager: Priya Nair (priya.mgr@company.com) - manages Aman and Rahul
# - Employee: Aman Gupta (aman@company.com)
# - Employee 2: Rahul Sharma (rahul@company.com) - peer employee

admin_user, admin_token, admin_hdr = get_user_and_token("admin", "admin@company.com")
hr_user, hr_token, hr_hdr = get_user_and_token("hr", "neha.hr@company.com")
mgr_user, mgr_token, mgr_hdr = get_user_and_token("manager", "priya.mgr@company.com")
emp_user, emp_token, emp_hdr = get_user_and_token("employee", "aman@company.com")
peer_user, peer_token, peer_hdr = get_user_and_token("employee", "rahul@company.com")


def run_all_rbac_tests():
    print("=" * 65)
    print("  AI HR ASSISTANT — FULL RBAC VERIFICATION SUITE")
    print("=" * 65)

    # =======================================================================
    # SECTION 1: EMPLOYEES ENDPOINTS
    # =======================================================================
    print("\n--- 1. EMPLOYEES MODULE RBAC ---")

    # 1.1 GET /employees/me
    chk(client.get("/employees/me").status_code == 401, "GET /employees/me unauthenticated -> 401")
    r_emp_me = client.get("/employees/me", headers=emp_hdr)
    chk(r_emp_me.status_code == 200 and r_emp_me.json()["employee_code"] == "EMP004", "Employee can access own profile -> 200")
    chk(client.get("/employees/me", headers=mgr_hdr).status_code == 200, "Manager can access own profile -> 200")
    chk(client.get("/employees/me", headers=hr_hdr).status_code == 200, "HR can access own profile -> 200")
    chk(client.get("/employees/me", headers=admin_hdr).status_code == 200, "Admin can access own profile -> 200")

    # 1.2 GET /employees (Directory: HR & Admin all, Manager team only — PROJECT_DECISIONS D-010)
    chk(client.get("/employees").status_code == 401, "GET /employees unauthenticated -> 401")
    chk(client.get("/employees", headers=emp_hdr).status_code == 403, "Employee blocked from GET /employees -> 403")
    r_mgr_all = client.get("/employees", headers=mgr_hdr)
    mgr_team_ids = {sub.id for sub in mgr_user.employee.subordinates} | {mgr_user.employee_id}
    chk(r_mgr_all.status_code == 200 and {e["id"] for e in r_mgr_all.json()} == mgr_team_ids,
        "Manager sees only own team in GET /employees -> 200")
    r_hr_all = client.get("/employees", headers=hr_hdr)
    chk(r_hr_all.status_code == 200 and len(r_hr_all.json()) >= 6, "HR can list all employees -> 200")
    r_adm_all = client.get("/employees", headers=admin_hdr)
    chk(r_adm_all.status_code == 200 and len(r_adm_all.json()) >= 6, "Admin can list all employees -> 200")

    # 1.3 GET /employees/{id} (HR & Admin only)
    target_id = peer_user.employee_id
    chk(client.get(f"/employees/{target_id}").status_code == 401, f"GET /employees/{target_id} unauthenticated -> 401")
    chk(client.get(f"/employees/{target_id}", headers=emp_hdr).status_code == 403, "Employee blocked from GET /employees/{id} -> 403")
    expected_mgr = 200 if target_id in mgr_team_ids else 403
    chk(client.get(f"/employees/{target_id}", headers=mgr_hdr).status_code == expected_mgr,
        f"Manager GET /employees/{{id}} follows team scope -> {expected_mgr}")
    chk(client.get(f"/employees/{target_id}", headers=hr_hdr).status_code == 200, "HR can view any employee by ID -> 200")
    chk(client.get(f"/employees/{target_id}", headers=admin_hdr).status_code == 200, "Admin can view any employee by ID -> 200")

    # =======================================================================
    # SECTION 2: ATTENDANCE ENDPOINTS
    # =======================================================================
    print("\n--- 2. ATTENDANCE MODULE RBAC ---")

    # 2.1 GET /attendance/me
    chk(client.get("/attendance/me").status_code == 401, "GET /attendance/me unauthenticated -> 401")
    chk(client.get("/attendance/me", headers=emp_hdr).status_code == 200, "Employee can access own attendance -> 200")
    chk(client.get("/attendance/me", headers=mgr_hdr).status_code == 200, "Manager can access own attendance -> 200")
    chk(client.get("/attendance/me", headers=hr_hdr).status_code == 200, "HR can access own attendance -> 200")
    chk(client.get("/attendance/me", headers=admin_hdr).status_code == 200, "Admin can access own attendance -> 200")

    # 2.2 GET /attendance/summary
    chk(client.get("/attendance/summary").status_code == 401, "GET /attendance/summary unauthenticated -> 401")
    chk(client.get("/attendance/summary", headers=emp_hdr).status_code == 200, "Employee can access own attendance summary -> 200")

    # 2.3 POST /attendance (HR & Admin only)
    att_payload = {
        "employee_id": emp_user.employee_id,
        "attendance_date": "2026-09-01",
        "status": "present",
        "working_minutes": 480,
        "late_minutes": 0,
        "overtime_minutes": 0,
    }
    chk(client.post("/attendance", json=att_payload).status_code == 401, "POST /attendance unauthenticated -> 401")
    chk(client.post("/attendance", json=att_payload, headers=emp_hdr).status_code == 403, "Employee blocked from creating attendance -> 403")
    chk(client.post("/attendance", json=att_payload, headers=mgr_hdr).status_code == 403, "Manager blocked from creating attendance -> 403")

    # 2.4 GET /attendance/{employee_id} (HR & Admin only)
    chk(client.get(f"/attendance/{target_id}").status_code == 401, "GET /attendance/{id} unauthenticated -> 401")
    chk(client.get(f"/attendance/{target_id}", headers=emp_hdr).status_code == 403, "Employee blocked from another employee's attendance -> 403")
    chk(client.get(f"/attendance/{target_id}", headers=mgr_hdr).status_code == 403, "Manager blocked from GET /attendance/{id} -> 403")
    chk(client.get(f"/attendance/{target_id}", headers=hr_hdr).status_code == 200, "HR can view any employee attendance -> 200")
    chk(client.get(f"/attendance/{target_id}", headers=admin_hdr).status_code == 200, "Admin can view any employee attendance -> 200")

    # =======================================================================
    # SECTION 3: SALARY ENDPOINTS
    # =======================================================================
    print("\n--- 3. SALARY MODULE RBAC ---")

    # 3.1 GET /salary/me
    chk(client.get("/salary/me").status_code == 401, "GET /salary/me unauthenticated -> 401")
    chk(client.get("/salary/me", headers=emp_hdr).status_code == 200, "Employee can access own salary -> 200")
    chk(client.get("/salary/me", headers=mgr_hdr).status_code == 200, "Manager can access own salary -> 200")
    chk(client.get("/salary/me", headers=hr_hdr).status_code == 200, "HR can access own salary -> 200")
    chk(client.get("/salary/me", headers=admin_hdr).status_code == 200, "Admin can access own salary -> 200")

    # 3.2 GET /salary/summary (HR & Admin only)
    chk(client.get("/salary/summary").status_code == 401, "GET /salary/summary unauthenticated -> 401")
    chk(client.get("/salary/summary", headers=emp_hdr).status_code == 403, "Employee blocked from GET /salary/summary -> 403")
    chk(client.get("/salary/summary", headers=mgr_hdr).status_code == 403, "Manager blocked from GET /salary/summary -> 403")
    chk(client.get("/salary/summary", headers=hr_hdr).status_code == 200, "HR can access GET /salary/summary -> 200")
    chk(client.get("/salary/summary", headers=admin_hdr).status_code == 200, "Admin can access GET /salary/summary -> 200")

    # 3.3 GET /salary/{employee_id} (HR & Admin only)
    chk(client.get(f"/salary/{target_id}").status_code == 401, "GET /salary/{id} unauthenticated -> 401")
    chk(client.get(f"/salary/{target_id}", headers=emp_hdr).status_code == 403, "Employee blocked from viewing peer salary -> 403")
    chk(client.get(f"/salary/{target_id}", headers=mgr_hdr).status_code == 403, "Manager blocked from viewing subordinate salary -> 403")
    chk(client.get(f"/salary/{target_id}", headers=hr_hdr).status_code == 200, "HR can view any employee salary -> 200")
    chk(client.get(f"/salary/{target_id}", headers=admin_hdr).status_code == 200, "Admin can view any employee salary -> 200")

    # =======================================================================
    # SECTION 4: LEAVES ENDPOINTS
    # =======================================================================
    print("\n--- 4. LEAVES MODULE RBAC ---")

    # 4.1 POST /leaves (All authenticated employees)
    chk(client.post("/leaves", json={"leave_type": "sick", "start_date": "2026-10-01", "end_date": "2026-10-02"}).status_code == 401,
        "POST /leaves unauthenticated -> 401")

    # 4.2 GET /leaves/me
    chk(client.get("/leaves/me").status_code == 401, "GET /leaves/me unauthenticated -> 401")
    chk(client.get("/leaves/me", headers=emp_hdr).status_code == 200, "Employee can access own leaves -> 200")
    chk(client.get("/leaves/me", headers=mgr_hdr).status_code == 200, "Manager can access own leaves -> 200")
    chk(client.get("/leaves/me", headers=hr_hdr).status_code == 200, "HR can access own leaves -> 200")
    chk(client.get("/leaves/me", headers=admin_hdr).status_code == 200, "Admin can access own leaves -> 200")

    # 4.3 PATCH /leaves/{leave_id}/status (Manager, HR, Admin only; Employee blocked)
    # Create temporary pending leave for testing status transitions
    pending_leave = Leave(
        employee_id=emp_user.employee_id,
        leave_type="casual",
        from_date=date(2026, 12, 1),
        to_date=date(2026, 12, 2),
        status=LeaveStatus.PENDING.value,
    )
    db.add(pending_leave)
    db.commit()
    db.refresh(pending_leave)

    chk(client.patch(f"/leaves/{pending_leave.id}/status", json={"status": "approved"}).status_code == 401,
        "PATCH /leaves/{id}/status unauthenticated -> 401")
    chk(client.patch(f"/leaves/{pending_leave.id}/status", json={"status": "approved"}, headers=emp_hdr).status_code == 403,
        "Employee blocked from approving leave -> 403")
    r_mgr_appr = client.patch(f"/leaves/{pending_leave.id}/status", json={"status": "approved"}, headers=mgr_hdr)
    chk(r_mgr_appr.status_code == 200, "Manager can approve leave -> 200")

    # Test Admin can also approve pending leaves
    pending_leave2 = Leave(
        employee_id=peer_user.employee_id,
        leave_type="sick",
        from_date=date(2026, 12, 5),
        to_date=date(2026, 12, 6),
        status=LeaveStatus.PENDING.value,
    )
    db.add(pending_leave2)
    db.commit()
    db.refresh(pending_leave2)

    r_adm_appr = client.patch(f"/leaves/{pending_leave2.id}/status", json={"status": "rejected"}, headers=admin_hdr)
    chk(r_adm_appr.status_code == 200, "Admin can approve/reject leave -> 200")

    # Clean up test leaves
    db.delete(pending_leave)
    db.delete(pending_leave2)
    db.commit()

    # 4.4 GET /leaves/{employee_id} (HR & Admin only)
    chk(client.get(f"/leaves/{target_id}").status_code == 401, "GET /leaves/{id} unauthenticated -> 401")
    chk(client.get(f"/leaves/{target_id}", headers=emp_hdr).status_code == 403, "Employee blocked from viewing peer leaves -> 403")
    chk(client.get(f"/leaves/{target_id}", headers=mgr_hdr).status_code == 403, "Manager blocked from GET /leaves/{id} -> 403")
    chk(client.get(f"/leaves/{target_id}", headers=hr_hdr).status_code == 200, "HR can view any employee leaves -> 200")
    chk(client.get(f"/leaves/{target_id}", headers=admin_hdr).status_code == 200, "Admin can view any employee leaves -> 200")

    # =======================================================================
    # SECTION 5: DASHBOARD ENDPOINT
    # =======================================================================
    print("\n--- 5. DASHBOARD MODULE RBAC ---")
    chk(client.get("/dashboard/summary").status_code == 401, "GET /dashboard/summary unauthenticated -> 401")
    chk(client.get("/dashboard/summary", headers=emp_hdr).status_code == 403, "Employee blocked from GET /dashboard/summary -> 403")
    chk(client.get("/dashboard/summary", headers=mgr_hdr).status_code == 403, "Manager blocked from GET /dashboard/summary -> 403")
    chk(client.get("/dashboard/summary", headers=hr_hdr).status_code == 200, "HR can access dashboard -> 200")
    chk(client.get("/dashboard/summary", headers=admin_hdr).status_code == 200, "Admin can access dashboard -> 200")

    # =======================================================================
    # SECTION 6: AI /CHAT PRIVACY & RBAC GUARDRAILS
    # =======================================================================
    print("\n--- 6. AI /CHAT PRIVACY & RBAC GUARDRAILS ---")

    # 6.1 Unauthenticated request returns 401
    chk(client.post("/chat", json={"question": "What is my salary?"}).status_code == 401,
        "POST /chat unauthenticated -> 401")

    # Mock the external LLM provider call so test is fast, offline, and purely validates RBAC
    with patch("app.api.chat.generate_response", return_value="Verified information provided."):
        # 6.2 Policy inquiry allowed for all roles
        r_pol = client.post("/chat", json={"question": "What is the company leave policy?"}, headers=emp_hdr)
        chk(r_pol.status_code == 200 and r_pol.json()["intent"] == "POLICY",
            "Employee can query company policy via /chat -> 200")

        # 6.3 Employee querying own salary -> Allowed
        r_emp_sal = client.post("/chat", json={"question": "What is my latest salary?"}, headers=emp_hdr)
        chk(r_emp_sal.status_code == 200 and "Access denied" not in r_emp_sal.json()["answer"],
            "Employee querying own salary -> Allowed")

        # 6.4 Employee querying peer salary -> DENIED
        r_emp_peer_sal = client.post("/chat", json={"question": "What is Rahul's salary?"}, headers=emp_hdr)
        chk(r_emp_peer_sal.status_code == 200 and "Access denied" in r_emp_peer_sal.json()["answer"],
            "Employee querying Rahul's salary -> Access Denied")

        # 6.5 Manager querying subordinate salary -> DENIED (Salary is strictly private)
        r_mgr_sub_sal = client.post("/chat", json={"question": "What is Rahul's salary?"}, headers=mgr_hdr)
        chk(r_mgr_sub_sal.status_code == 200 and "Access denied" in r_mgr_sub_sal.json()["answer"],
            "Manager querying subordinate salary -> Access Denied")

        # 6.6 HR querying employee salary -> ALLOWED
        r_hr_sal = client.post("/chat", json={"question": "What is Rahul's salary in August 2024?"}, headers=hr_hdr)
        chk(r_hr_sal.status_code == 200 and "Access denied" not in r_hr_sal.json()["answer"],
            "HR querying employee salary -> Allowed")

        # 6.7 Admin querying employee salary -> ALLOWED
        r_adm_sal = client.post("/chat", json={"question": "What is Rahul's salary in August 2024?"}, headers=admin_hdr)
        chk(r_adm_sal.status_code == 200 and "Access denied" not in r_adm_sal.json()["answer"],
            "Admin querying employee salary -> Allowed")

        # 6.8 Employee querying peer attendance -> DENIED
        r_emp_peer_att = client.post("/chat", json={"question": "How many days was Rahul present in August?"}, headers=emp_hdr)
        chk(r_emp_peer_att.status_code == 200 and "Access denied" in r_emp_peer_att.json()["answer"],
            "Employee querying peer attendance -> Access Denied")

        # 6.9 Manager querying direct subordinate attendance -> ALLOWED (Team data)
        r_mgr_sub_att = client.post("/chat", json={"question": "How many days was Aman present in August?"}, headers=mgr_hdr)
        chk(r_mgr_sub_att.status_code == 200 and "Access denied" not in r_mgr_sub_att.json()["answer"],
            "Manager querying direct subordinate attendance -> Allowed")

        # 6.10 Manager querying non-subordinate attendance -> DENIED
        r_mgr_nonsub_att = client.post("/chat", json={"question": "How many days was Sneha present in August?"}, headers=mgr_hdr)
        chk(r_mgr_nonsub_att.status_code == 200 and "Access denied" in r_mgr_nonsub_att.json()["answer"],
            "Manager querying non-subordinate attendance -> Access Denied")

        # 6.11 Directory query: Employee blocked, HR allowed
        r_emp_dir = client.post("/chat", json={"question": "List all employees in the company"}, headers=emp_hdr)
        chk(r_emp_dir.status_code == 200 and "Access denied" in r_emp_dir.json()["answer"],
            "Employee listing all employees -> Access Denied")

        r_hr_dir = client.post("/chat", json={"question": "List all employees in the company"}, headers=hr_hdr)
        chk(r_hr_dir.status_code == 200 and "Access denied" not in r_hr_dir.json()["answer"],
            "HR listing all employees -> Allowed")

    # =======================================================================
    # FINAL SUMMARY
    # =======================================================================
    print("\n" + "=" * 65)
    print(f"  RBAC TEST RESULTS: {passed_count} PASSED, {failed_count} FAILED")
    print("=" * 65)


if __name__ == "__main__":
    try:
        run_all_rbac_tests()
    finally:
        client.cleanup_chat_logs()
        db.close()
    if failed_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)
