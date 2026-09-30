"""
tests/test_dashboard_api.py
---------------------------
Integration tests for the HR Dashboard endpoint:
  GET /dashboard/summary

RBAC Requirements:
- Unauthenticated (no token) -> 401 Unauthorized
- Employee role -> 403 Forbidden
- Manager role -> 403 Forbidden
- HR role -> 200 OK
- Admin role -> 200 OK
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from app.utils.security import create_access_token

client = TestClient(app)


def get_test_token(role="hr"):
    from app.database.connection import SessionLocal
    from app.database.models import User
    db = SessionLocal()
    user = db.query(User).filter(User.role == role).first()
    if not user:
        user = db.query(User).first()
    db.close()
    return create_access_token(user_id=user.id, role=user.role)


def test_dashboard_summary_unauthorized():
    """Request without token must return 401."""
    res = client.get("/dashboard/summary")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"
    print("[PASS] test_dashboard_summary_unauthorized -> 401")


def test_dashboard_summary_employee_forbidden():
    """Employee attempting to access dashboard summary must return 403."""
    token = get_test_token(role="employee")
    res = client.get("/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403, f"Expected 403 for employee, got {res.status_code}"
    print("[PASS] test_dashboard_summary_employee_forbidden -> 403")


def test_dashboard_summary_manager_forbidden():
    """Manager attempting to access company-wide dashboard summary must return 403."""
    token = get_test_token(role="manager")
    res = client.get("/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403, f"Expected 403 for manager, got {res.status_code}"
    print("[PASS] test_dashboard_summary_manager_forbidden -> 403")


def test_dashboard_summary_hr_allowed():
    """HR role can access company-wide dashboard summary -> 200."""
    token = get_test_token(role="hr")
    res = client.get("/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Expected 200 for HR, got {res.status_code}: {res.text}"

    data = res.json()
    assert "kpis" in data
    assert "total_employees" in data["kpis"]
    assert data["kpis"]["total_employees"] > 0
    assert "department_attendance" in data
    assert isinstance(data["department_attendance"], list)
    assert "overtime_leaders" in data
    assert "late_leaders" in data
    assert "leave_breakdown" in data
    assert "recent_leaves" in data
    print("[PASS] test_dashboard_summary_hr_allowed -> 200")


def test_dashboard_summary_admin_allowed():
    """Admin role can access company-wide dashboard summary -> 200."""
    token = get_test_token(role="admin")
    res = client.get("/dashboard/summary", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Expected 200 for Admin, got {res.status_code}: {res.text}"
    print("[PASS] test_dashboard_summary_admin_allowed -> 200")


def test_dashboard_summary_custom_date():
    """HR role with specific date filter returns metrics for that date."""
    token = get_test_token(role="hr")
    res = client.get("/dashboard/summary?date=2024-08-30", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["reference_date"] == "2024-08-30"
    assert data["is_fallback_date"] is False
    print("[PASS] test_dashboard_summary_custom_date -> 200")


if __name__ == "__main__":
    test_dashboard_summary_unauthorized()
    test_dashboard_summary_employee_forbidden()
    test_dashboard_summary_manager_forbidden()
    test_dashboard_summary_hr_allowed()
    test_dashboard_summary_admin_allowed()
    test_dashboard_summary_custom_date()
    print("\nAll Dashboard API RBAC tests passed successfully!")
