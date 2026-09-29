import sys, os
sys.path.insert(0, os.path.abspath("."))
sys.stdout.reconfigure(encoding="utf-8")

from datetime import date
from unittest.mock import AsyncMock, patch
from authlib.integrations.base_client.errors import OAuthError
from fastapi.testclient import TestClient

from app.main import app
from app.database.connection import SessionLocal
from app.database.models import Employee, User, UserRole, UserStatus
from app.database.queries import create_employee, create_user
from app.utils.oauth import oauth
from app.utils.security import hash_password

client = TestClient(app)
db = SessionLocal()

TEST_EMAILS = [
    "google.new@hr.dev",
    "google.link@hr.dev",
    "google.existing@hr.dev",
    "google.inact@hr.dev",
    "google.conflict@hr.dev",
]
TEST_CODES = [
    "GGL-LINK",
    "GGL-EXIST",
    "GGL-INACT",
    "GGL-CONF",
]

def cleanup():
    # Find all test users
    users = db.query(User).filter(
        (User.email.in_(TEST_EMAILS)) | (User.email.like("google.%@hr.dev"))
    ).all()
    test_emp_ids = [u.employee_id for u in users if u.employee_id]
    for u in users:
        db.delete(u)
    db.commit()

    # Remove test employees (explicit codes or employee IDs belonging to test users)
    emps = db.query(Employee).filter(
        (Employee.employee_code.in_(TEST_CODES)) | (Employee.id.in_(test_emp_ids))
    ).all()
    for e in emps:
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
    print("  Google OAuth 2.0 / OIDC - Integration Test Suite")
    print(SEP)
    cleanup()

    # -----------------------------------------------------------------------
    # [1] Google login route is registered, fast, & redirects to Google
    # -----------------------------------------------------------------------
    print("\n[1] GET and HEAD /auth/google/login return fast 302 redirect with state & redirect_uri")
    import time
    t0 = time.perf_counter()
    r_login = client.get("/auth/google/login", follow_redirects=False)
    elapsed = time.perf_counter() - t0
    chk(elapsed < 1.0, f"login endpoint returns quickly ({round(elapsed, 4)}s < 1.0s)", f"Too slow: {elapsed}s")
    chk(r_login.status_code == 302, "GET status 302 redirect", f"status {r_login.status_code}")
    loc = r_login.headers.get("location", "")
    chk("accounts.google.com/o/oauth2/v2/auth" in loc, "location points to Google auth endpoint", f"Got: {loc}")
    chk("response_type=code" in loc, "contains response_type=code", "missing response_type")
    chk("redirect_uri=" in loc, "contains redirect_uri parameter", "missing redirect_uri")
    chk("scope=openid" in loc or "scope=openid+email+profile" in loc or "openid" in loc, "contains openid scope", "missing openid")
    chk("state=" in loc, "contains CSRF state parameter", "missing state")
    chk("nonce=" in loc, "contains nonce parameter", "missing nonce")

    # Test HEAD request (curl.exe -I)
    r_head = client.head("/auth/google/login", follow_redirects=False)
    chk(r_head.status_code == 302, "HEAD status 302 redirect (for curl.exe -I)", f"status {r_head.status_code}")
    loc_head = r_head.headers.get("location", "")
    chk("accounts.google.com/o/oauth2/v2/auth" in loc_head, "HEAD location points to Google auth endpoint", f"Got: {loc_head}")

    # Verify explicit OIDC configuration (avoids runtime discovery & provides jwks_uri)
    chk(oauth.google.server_metadata.get("jwks_uri") == "https://www.googleapis.com/oauth2/v3/certs", "jwks_uri configured for OIDC token verification", f"Got: {oauth.google.server_metadata.get('jwks_uri')}")
    chk(oauth.google.authorize_url == "https://accounts.google.com/o/oauth2/v2/auth", "explicit authorize_url configured", f"Got: {oauth.google.authorize_url}")
    chk(oauth.google.access_token_url == "https://oauth2.googleapis.com/token", "explicit access_token_url configured", f"Got: {oauth.google.access_token_url}")

    # -----------------------------------------------------------------------
    # [2] OAuth callback handles successful authentication for a new user
    # -----------------------------------------------------------------------
    print("\n[2] OAuth callback provisions new user with nullable password_hash")
    mock_token_new = {
        "access_token": "mock-google-access-token-1",
        "token_type": "Bearer",
        "userinfo": {
            "sub": "google-sub-9001",
            "email": "google.new@hr.dev",
            "name": "New Google User",
            "email_verified": True,
        }
    }

    with patch.object(oauth.google, "authorize_access_token", new_callable=AsyncMock) as mock_auth:
        mock_auth.return_value = mock_token_new
        r_cb = client.get("/auth/google/callback?code=mock_code_1&state=mock_state_1")

    chk(r_cb.status_code == 200, "callback returns 200 OK", f"status {r_cb.status_code}, data: {r_cb.text}")
    data_new = r_cb.json()
    new_jwt = data_new.get("access_token")
    chk(bool(new_jwt), "access_token issued", "missing access_token")
    chk(data_new.get("token_type") == "bearer", "token_type is bearer", f"Got {data_new.get('token_type')}")
    chk(data_new.get("role") == "employee", "default role is employee", f"Got {data_new.get('role')}")
    chk(data_new.get("email") == "google.new@hr.dev", "email matches google profile", f"Got {data_new.get('email')}")

    # Verify database state for Google-only user
    u_new = db.query(User).filter(User.google_id == "google-sub-9001").first()
    chk(u_new is not None, "user found in DB by google_id", "User not in DB")
    chk(u_new.password_hash is None, "password_hash is NULL for Google-only user", f"Got: {u_new.password_hash}")
    chk(u_new.employee_id is not None, "employee profile automatically created", "Missing employee_id")
    chk(u_new.role == UserRole.EMPLOYEE.value, "stored role is employee", f"Got {u_new.role}")
    chk(u_new.status == UserStatus.ACTIVE.value, "stored status is active", f"Got {u_new.status}")

    # -----------------------------------------------------------------------
    # [3] Resulting application JWT works with get_current_user & protected APIs
    # -----------------------------------------------------------------------
    print("\n[3] Resulting application JWT works with get_current_user & protected routes")
    r_me = client.get("/employees/me", headers={"Authorization": f"Bearer {new_jwt}"})
    chk(r_me.status_code == 200, "GET /employees/me -> 200 OK", f"status {r_me.status_code}")
    chk(r_me.json().get("name") == "New Google User", "profile name matches", f"Got: {r_me.json()}")

    r_sal_me = client.get("/salary/me", headers={"Authorization": f"Bearer {new_jwt}"})
    chk(r_sal_me.status_code == 200, "GET /salary/me -> 200 OK", f"status {r_sal_me.status_code}")

    r_att_me = client.get("/attendance/me", headers={"Authorization": f"Bearer {new_jwt}"})
    chk(r_att_me.status_code == 200, "GET /attendance/me -> 200 OK", f"status {r_att_me.status_code}")

    # -----------------------------------------------------------------------
    # [4] Existing Google user can log in without creating duplicates
    # -----------------------------------------------------------------------
    print("\n[4] Existing Google user logs in without creating duplicates")
    with patch.object(oauth.google, "authorize_access_token", new_callable=AsyncMock) as mock_auth:
        mock_auth.return_value = mock_token_new
        r_cb2 = client.get("/auth/google/callback?code=mock_code_2&state=mock_state_2")

    chk(r_cb2.status_code == 200, "status 200 on subsequent login", f"status {r_cb2.status_code}")
    chk(r_cb2.json().get("user_id") == u_new.id, "user_id matches original user", f"Got {r_cb2.json().get('user_id')}")
    count_new_users = db.query(User).filter(User.email == "google.new@hr.dev").count()
    chk(count_new_users == 1, "exactly 1 user in DB (no duplicates)", f"Found {count_new_users}")

    # -----------------------------------------------------------------------
    # [5] Existing local user with matching email gets linked appropriately
    # -----------------------------------------------------------------------
    print("\n[5] Existing local user with matching email is safely linked")
    emp_link = create_employee(
        db, employee_code="GGL-LINK", name="Existing HR Staff",
        department="Human Resources", designation="HR Officer", joining_date=date(2023, 1, 1)
    )
    user_link = create_user(
        db, employee_id=emp_link.id, email="google.link@hr.dev",
        password_hash=hash_password("Password123!"), role=UserRole.HR.value
    )
    chk(user_link.google_id is None, "initially google_id is None", "Expected None")

    mock_token_link = {
        "access_token": "mock-token-2",
        "token_type": "Bearer",
        "userinfo": {
            "sub": "google-sub-9002",
            "email": "google.link@hr.dev",
            "name": "Existing HR Staff",
        }
    }
    with patch.object(oauth.google, "authorize_access_token", new_callable=AsyncMock) as mock_auth:
        mock_auth.return_value = mock_token_link
        r_cb3 = client.get("/auth/google/callback?code=mock_code_3&state=mock_state_3")

    chk(r_cb3.status_code == 200, "link callback -> 200 OK", f"status {r_cb3.status_code}")
    link_jwt = r_cb3.json().get("access_token")
    chk(r_cb3.json().get("role") == "hr", "local role preserved as 'hr'", f"Got {r_cb3.json().get('role')}")

    db.commit()
    user_link = db.query(User).filter(User.id == user_link.id).first()
    chk(user_link.google_id == "google-sub-9002", "google_id linked in DB", f"Got: {user_link.google_id}")
    chk(user_link.password_hash is not None, "original password hash preserved", "password hash erased")
    chk(user_link.role == "hr", "DB role preserved as hr", f"Got: {user_link.role}")

    # -----------------------------------------------------------------------
    # [6] Existing email/password login still works for linked user
    # -----------------------------------------------------------------------
    print("\n[6] Existing email/password login still works for linked user")
    r_pwd_login = client.post("/auth/login", json={
        "email": "google.link@hr.dev",
        "password": "Password123!",
    })
    chk(r_pwd_login.status_code == 200, "POST /auth/login -> 200 OK", f"status {r_pwd_login.status_code}")
    chk("access_token" in r_pwd_login.json(), "access_token returned", "missing token")

    # -----------------------------------------------------------------------
    # [7] Email/password login fails for Google-only user without password
    # -----------------------------------------------------------------------
    print("\n[7] Email/password login safely rejected for Google-only account")
    r_no_pwd = client.post("/auth/login", json={
        "email": "google.new@hr.dev",
        "password": "AnyRandomPassword123",
    })
    chk(r_no_pwd.status_code == 401, "POST /auth/login -> 401 Unauthorized", f"status {r_no_pwd.status_code}")

    # -----------------------------------------------------------------------
    # [8] Existing RBAC still works after Google login
    # -----------------------------------------------------------------------
    print("\n[8] Existing RBAC works with JWT issued from Google login")
    # Linked HR user has access to HR-only endpoints
    r_hr_access = client.get("/salary/summary", headers={"Authorization": f"Bearer {link_jwt}"})
    chk(r_hr_access.status_code == 200, "HR Google JWT can access /salary/summary -> 200 OK", f"status {r_hr_access.status_code}")

    # Regular employee Google user cannot access HR-only endpoints
    r_emp_blocked = client.get("/salary/summary", headers={"Authorization": f"Bearer {new_jwt}"})
    chk(r_emp_blocked.status_code == 403, "Employee Google JWT blocked from /salary/summary -> 403 Forbidden", f"status {r_emp_blocked.status_code}")

    # -----------------------------------------------------------------------
    # [9] Inactive user is rejected
    # -----------------------------------------------------------------------
    print("\n[9] Inactive user rejected during Google OAuth callback -> 403")
    emp_inact = create_employee(
        db, employee_code="GGL-INACT", name="Inactive User",
        department="Sales", designation="Rep", joining_date=date(2023, 1, 1)
    )
    user_inact = create_user(
        db, employee_id=emp_inact.id, email="google.inact@hr.dev",
        password_hash="hash", status=UserStatus.INACTIVE.value
    )
    mock_token_inact = {
        "access_token": "mock-token-inact",
        "token_type": "Bearer",
        "userinfo": {
            "sub": "google-sub-9003",
            "email": "google.inact@hr.dev",
            "name": "Inactive User",
        }
    }
    with patch.object(oauth.google, "authorize_access_token", new_callable=AsyncMock) as mock_auth:
        mock_auth.return_value = mock_token_inact
        r_inact_cb = client.get("/auth/google/callback?code=mock_code_inact&state=mock_state")

    chk(r_inact_cb.status_code == 403, "inactive user returns 403 Forbidden", f"status {r_inact_cb.status_code}")

    # -----------------------------------------------------------------------
    # [10] Conflicting Google ID on already-linked email is rejected -> 409
    # -----------------------------------------------------------------------
    print("\n[10] Conflicting Google ID on already-linked email is rejected -> 409")
    mock_token_conflict = {
        "access_token": "mock-token-conf",
        "token_type": "Bearer",
        "userinfo": {
            "sub": "google-sub-DIFFERENT",
            "email": "google.link@hr.dev",  # already linked to google-sub-9002
            "name": "Attacker",
        }
    }
    with patch.object(oauth.google, "authorize_access_token", new_callable=AsyncMock) as mock_auth:
        mock_auth.return_value = mock_token_conflict
        r_conf = client.get("/auth/google/callback?code=mock_code_conf&state=mock_state")

    chk(r_conf.status_code == 409, "conflicting google_id returns 409 Conflict", f"status {r_conf.status_code}")

    # -----------------------------------------------------------------------
    # [11] Invalid OAuth callback / OAuthError is rejected safely -> 400
    # -----------------------------------------------------------------------
    print("\n[11] Invalid OAuth callback is safely rejected -> 400")
    with patch.object(oauth.google, "authorize_access_token", new_callable=AsyncMock) as mock_auth:
        mock_auth.side_effect = OAuthError("access_denied", "User denied authorization")
        r_denied = client.get("/auth/google/callback?error=access_denied")

    chk(r_denied.status_code == 400, "OAuthError returns 400 Bad Request", f"status {r_denied.status_code}")

    # Incomplete userinfo (missing sub or email)
    mock_token_bad_profile = {
        "access_token": "mock-token-bad",
        "token_type": "Bearer",
        "userinfo": {"name": "No Email Or Sub"}
    }
    with patch.object(oauth.google, "authorize_access_token", new_callable=AsyncMock) as mock_auth:
        mock_auth.return_value = mock_token_bad_profile
        r_bad_prof = client.get("/auth/google/callback?code=code_bad&state=state_bad")

    chk(r_bad_prof.status_code == 400, "incomplete profile returns 400 Bad Request", f"status {r_bad_prof.status_code}")

except Exception as e:
    print("\nEXCEPTION:", e)
    import traceback
    traceback.print_exc()
    failed += 1
finally:
    cleanup()
    db.close()
    print("\n" + SEP)
    print(f"  Results: {passed} passed, {failed} failed")
    print(SEP)
    if failed > 0:
        sys.exit(1)
