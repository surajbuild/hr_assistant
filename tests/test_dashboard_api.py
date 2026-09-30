"""
tests/test_dashboard_api.py
---------------------------
Integration tests for the HR Dashboard endpoint:
  GET /dashboard/summary
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app.main import app
from app.utils.security import create_access_token

client = TestClient(app)


def test_dashboard_summary_unauthorized():
    """Request without token must return 401."""
    res = client.get("/dashboard/summary")
    assert res.status_code == 401, f"Expected 401, got {res.status_code}"


def get_test_token(role="hr"):
    from app.database.connection import SessionLocal
    from app.database.models import User
    db = SessionLocal()
    user = db.query(User).filter(User.role == role).first()
    if not user:
        user = db.query(User).first()
    db.close()
    return create_access_token(user_id=user.id, role=user.role)


def test_dashboard_summary_authorized():
    """Request with valid JWT returns complete dashboard metrics."""
    token = get_test_token(role="hr")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/dashboard/summary", headers=headers)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"

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
    print("[PASS] test_dashboard_summary_authorized")


def test_dashboard_summary_custom_date():
    """Request with specific date filter returns metrics for that date."""
    token = get_test_token(role="employee")
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/dashboard/summary?date=2024-08-30", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["reference_date"] == "2024-08-30"
    assert data["is_fallback_date"] is False
    print("[PASS] test_dashboard_summary_custom_date")


if __name__ == "__main__":
    test_dashboard_summary_unauthorized()
    test_dashboard_summary_authorized()
    test_dashboard_summary_custom_date()
    print("\nAll Dashboard API tests passed successfully!")
