"""
tests/test_pagination_cleanups.py
---------------------------------
Session-7 cleanups (read-only against the dev database — creates no rows):

  KI-007  limit/offset + X-Total-Count on GET /users, /leaves, /documents
  KI-034  user administration lives in app/services/user_service.py (domain errors, no HTTPException)
  KI-035  chat `confidence` is "not_found" when the LLM says it could not find the information

Assumes `python scripts/seed_db.py` has been run (admin@company.com, neha.hr@company.com,
priya.mgr@company.com, aman@company.com).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.api.chat import NO_DOCUMENT_ANSWER, _confidence
from app.database.connection import SessionLocal
from app.database.models import User
from app.main import app
from app.services import user_service
from app.utils.security import create_access_token

client = TestClient(app)
db = SessionLocal()
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


def headers_for(email: str):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise RuntimeError(f"Seed user {email} missing — run scripts/seed_db.py")
    return user, {"Authorization": f"Bearer {create_access_token(user_id=user.id, role=user.role)}"}


try:
    admin_u, admin_h = headers_for("admin@company.com")
    hr_u, hr_h = headers_for("neha.hr@company.com")
    mgr_u, mgr_h = headers_for("priya.mgr@company.com")
    aman_u, aman_h = headers_for("aman@company.com")

    # ---------------- /users ----------------
    print("\n[/users pagination + service]")
    full = client.get("/users", headers=admin_h)
    total = int(full.headers.get("X-Total-Count", -1))
    chk(full.status_code == 200 and total == len(full.json()), "Unpaginated /users returns all rows, total header matches")
    page = client.get("/users?limit=2&offset=1", headers=admin_h)
    chk(
        page.status_code == 200
        and len(page.json()) == min(2, max(total - 1, 0))
        and [u["id"] for u in page.json()] == [u["id"] for u in full.json()[1:3]]
        and int(page.headers.get("X-Total-Count", -1)) == total,
        "limit/offset slice /users in id order and keep the full total",
    )
    chk(client.get("/users?limit=0", headers=admin_h).status_code == 422, "limit=0 rejected -> 422")
    chk(client.get("/users").status_code == 401, "/users unauthenticated -> 401")
    chk(client.get("/users", headers=hr_h).status_code == 403, "/users as HR -> 403")
    chk(client.get("/users", headers=aman_h).status_code == 403, "/users as employee -> 403")
    chk(client.patch("/users/999999", json={"status": "active"}, headers=admin_h).status_code == 404,
        "PATCH unknown user -> 404")
    chk(client.patch(f"/users/{admin_u.id}", json={"status": "inactive"}, headers=admin_h).status_code == 400,
        "Admin cannot deactivate self -> 400")

    try:
        user_service.update_user(db, admin_u, 999999, role="hr")
        chk(False, "Service raises UserNotFoundError")
    except user_service.UserNotFoundError:
        chk(True, "Service raises UserNotFoundError")
    try:
        user_service.update_user(db, admin_u, admin_u.id, role="employee")
        chk(False, "Service raises SelfModificationError")
    except user_service.SelfModificationError:
        chk(True, "Service raises SelfModificationError")
    db.rollback()

    # ---------------- /leaves ----------------
    print("\n[/leaves pagination]")
    all_leaves = client.get("/leaves", headers=hr_h)
    l_total = int(all_leaves.headers.get("X-Total-Count", -1))
    chk(all_leaves.status_code == 200 and l_total == len(all_leaves.json()), "HR /leaves total header matches rows")
    p1 = client.get("/leaves?limit=1", headers=hr_h)
    chk(
        p1.status_code == 200
        and len(p1.json()) == min(1, l_total)
        and int(p1.headers.get("X-Total-Count", -1)) == l_total,
        "limit=1 returns one row, total unchanged",
    )
    if l_total > 1:
        p2 = client.get("/leaves?limit=1&offset=1", headers=hr_h)
        chk(p2.json()[0]["id"] == all_leaves.json()[1]["id"], "offset=1 returns the second row")
    mgr_leaves = client.get("/leaves?limit=500", headers=mgr_h)
    chk(
        mgr_leaves.status_code == 200
        and int(mgr_leaves.headers.get("X-Total-Count", -1)) <= l_total,
        "Manager total counts only the manager's scope",
    )
    chk(client.get("/leaves").status_code == 401, "/leaves unauthenticated -> 401")
    chk(client.get("/leaves?limit=1", headers=aman_h).status_code == 403, "/leaves as employee -> 403")

    # ---------------- /documents ----------------
    print("\n[/documents pagination]")
    docs = client.get("/documents", headers=aman_h)
    d_total = int(docs.headers.get("X-Total-Count", -1))
    chk(docs.status_code == 200 and d_total == len(docs.json()), "Employee /documents total header matches rows")
    dp = client.get("/documents?limit=1", headers=aman_h)
    chk(
        dp.status_code == 200
        and len(dp.json()) == min(1, d_total)
        and int(dp.headers.get("X-Total-Count", -1)) == d_total,
        "limit=1 returns one document, total unchanged",
    )
    emp_archived = client.get("/documents?include_archived=true", headers=aman_h)
    hr_archived = client.get("/documents?include_archived=true", headers=hr_h)
    chk(
        int(emp_archived.headers.get("X-Total-Count", -1)) == d_total
        and int(hr_archived.headers.get("X-Total-Count", -1)) >= d_total,
        "Employees never see archived documents in the total; HR may",
    )
    chk(client.get("/documents").status_code == 401, "/documents unauthenticated -> 401")

    # ---------------- chat confidence ----------------
    print("\n[chat confidence post-check]")
    chk(_confidence("document_rag", False, "ctx", NO_DOCUMENT_ANSWER) == "not_found",
        "RAG answer 'could not find' -> not_found")
    chk(_confidence("document_rag", False, "ctx", "Employees get 20 days of leave.") == "document_grounded",
        "Grounded RAG answer stays document_grounded")
    chk(_confidence("document_rag", True, "ctx", NO_DOCUMENT_ANSWER) == "access_denied",
        "Denied stays access_denied")
    chk(_confidence("mysql", False, "Attendance: 20 days", "You were present 20 days.") == "data_verified",
        "Database answer stays data_verified")

except Exception as exc:  # report unexpected crashes as failures
    import traceback
    traceback.print_exc()
    chk(False, "Unexpected exception", str(exc))
finally:
    db.close()

print("\n" + "=" * 65)
print(f"  PAGINATION / CLEANUP TEST RESULTS: {passed_count} PASSED, {failed_count} FAILED")
print("=" * 65)
sys.exit(1 if failed_count else 0)
