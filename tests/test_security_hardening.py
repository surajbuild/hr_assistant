"""
tests/test_security_hardening.py
--------------------------------
Security hardening (KI-003, KI-011, D-031):

  [1] load_secret: missing / placeholder / short secrets are refused, 32+ bytes accepted
  [2] RateLimiter: sliding window, retry-after, reset (fake clock)
  [3] client_ip: X-Forwarded-For only believed from a trusted proxy (IPs and CIDRs)
  [4] POST /auth/login: failed attempts per (IP, email) → 429 with Retry-After; other emails unaffected;
      per-IP attempt limit → 429
  [5] POST /chat: per-user limit → 429, the blocked message reaches neither the LLM nor chat_logs;
      another user is unaffected

Creates no database rows except chat_logs rows for its own questions (removed in `finally`).
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from starlette.requests import Request

from app.database.connection import SessionLocal
from app.database.models import ChatLog, User, UserStatus
from app.main import app
from app.utils import rate_limit
from app.utils.rate_limit import RateLimiter
from app.utils.security import MIN_SECRET_BYTES, create_access_token, load_secret
from tests.helpers import TrackingClient

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


def raises_env_error(name: str, value) -> bool:
    old = os.environ.get(name)
    try:
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
        load_secret(name)
        return False
    except EnvironmentError:
        return True
    finally:
        if old is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = old


def fake_request(peer: str, forwarded: str = "") -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers, "client": (peer, 1234)})


db = SessionLocal()
client = TrackingClient(app, db, reset_chat_rate_limit=False)
saved_limits = {
    lim: lim.limit
    for lim in (rate_limit.login_ip_limiter, rate_limit.login_failure_limiter, rate_limit.chat_limiter)
}

try:
    print("\n[1] load_secret")
    var = "HRTEST_SECRET_PROBE"
    chk(raises_env_error(var, None), "missing secret is refused")
    chk(raises_env_error(var, ""), "empty secret is refused")
    chk(raises_env_error(var, "x" * (MIN_SECRET_BYTES - 1)), f"{MIN_SECRET_BYTES - 1}-byte secret is refused")
    chk(raises_env_error(var, "your-super-secret-key-change-this-in-production"), ".env.example placeholder is refused")
    os.environ[var] = "k" * MIN_SECRET_BYTES
    try:
        chk(load_secret(var) == "k" * MIN_SECRET_BYTES, f"{MIN_SECRET_BYTES}-byte secret is accepted")
    finally:
        os.environ.pop(var, None)
    chk(len(os.environ["JWT_SECRET_KEY"].encode()) >= MIN_SECRET_BYTES, "configured JWT_SECRET_KEY is >= 32 bytes")
    chk(len(os.environ["SESSION_SECRET_KEY"].encode()) >= MIN_SECRET_BYTES, "configured SESSION_SECRET_KEY is >= 32 bytes")
    main_src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", "main.py"), encoding="utf-8").read()
    chk("default-session-secret-key" not in main_src, "no hard-coded session secret fallback in app/main.py")

    print("\n[2] RateLimiter (fake clock)")
    now = [1000.0]
    lim = RateLimiter("probe", limit=3, window_seconds=60, clock=lambda: now[0])
    for _ in range(3):
        lim.hit("a")
    chk(lim.retry_after("a") == 60, "4th hit within the window is blocked for 60 s", str(lim.retry_after("a")))
    chk(lim.retry_after("b") is None, "other keys are independent")
    now[0] += 30
    chk(lim.retry_after("a") == 30, "retry-after shrinks as time passes", str(lim.retry_after("a")))
    now[0] += 30
    chk(lim.retry_after("a") is None, "window expiry releases the key")
    lim.hit("a"); lim.hit("a"); lim.hit("a")
    lim.reset("a")
    chk(lim.retry_after("a") is None, "reset(key) clears the key")

    print("\n[3] client_ip and trusted proxies")
    chk(rate_limit.client_ip(fake_request("127.0.0.1", "203.0.113.9")) == "203.0.113.9", "XFF believed from 127.0.0.1")
    chk(rate_limit.client_ip(fake_request("198.51.100.7", "203.0.113.9")) == "198.51.100.7", "XFF ignored from an untrusted peer")
    chk(rate_limit.client_ip(fake_request("127.0.0.1", "1.1.1.1, 203.0.113.9")) == "203.0.113.9", "last XFF hop is used")
    chk(rate_limit.client_ip(fake_request("127.0.0.1")) == "127.0.0.1", "no XFF → peer address")
    saved_networks = rate_limit.TRUSTED_PROXY_NETWORKS
    rate_limit.TRUSTED_PROXY_NETWORKS = rate_limit._parse_networks("172.28.0.0/16, not-an-ip")
    try:
        chk(rate_limit.client_ip(fake_request("172.28.0.5", "203.0.113.9")) == "203.0.113.9", "CIDR-trusted proxy (Docker network)")
        chk(rate_limit.client_ip(fake_request("127.0.0.1", "203.0.113.9")) == "127.0.0.1", "peer outside the configured CIDR is not trusted")
    finally:
        rate_limit.TRUSTED_PROXY_NETWORKS = saved_networks

    print("\n[4] POST /auth/login rate limits")
    rate_limit.login_ip_limiter.reset()
    rate_limit.login_failure_limiter.reset()
    rate_limit.login_failure_limiter.limit = 3
    probe = "ratelimit-probe@hrtest.dev"
    codes = [client.post("/auth/login", json={"email": probe, "password": "wrong"}).status_code for _ in range(3)]
    chk(codes == [401, 401, 401], "first 3 failures → 401 (generic)", str(codes))
    r = client.post("/auth/login", json={"email": probe, "password": "wrong"})
    chk(r.status_code == 429, "4th attempt for the same email → 429", f"{r.status_code} {r.text}")
    chk(r.headers.get("retry-after", "").isdigit(), "429 carries Retry-After", str(r.headers))
    chk("Too many" in r.json().get("detail", ""), "429 detail explains the limit", r.text)
    r = client.post("/auth/login", json={"email": probe.upper(), "password": "wrong"})
    chk(r.status_code == 429, "email case does not bypass the limit", str(r.status_code))
    r = client.post("/auth/login", json={"email": "ratelimit-other@hrtest.dev", "password": "wrong"})
    chk(r.status_code == 401, "a different email is not blocked", str(r.status_code))

    rate_limit.login_ip_limiter.reset()
    rate_limit.login_failure_limiter.reset()
    rate_limit.login_failure_limiter.limit = saved_limits[rate_limit.login_failure_limiter]
    rate_limit.login_ip_limiter.limit = 4
    codes = [
        client.post("/auth/login", json={"email": f"ratelimit-ip{i}@hrtest.dev", "password": "wrong"}).status_code
        for i in range(5)
    ]
    chk(codes[:4] == [401] * 4 and codes[4] == 429, "per-IP attempt limit → 429 on attempt 5", str(codes))
    rate_limit.login_ip_limiter.limit = saved_limits[rate_limit.login_ip_limiter]
    rate_limit.login_ip_limiter.reset()

    print("\n[5] POST /chat per-user limit")
    users = (
        db.query(User).filter(User.status == UserStatus.ACTIVE.value).order_by(User.id.asc()).limit(2).all()
    )
    if len(users) < 2:
        raise RuntimeError("Need 2 active seeded users — run scripts/seed_db.py")
    h1 = {"Authorization": f"Bearer {create_access_token(user_id=users[0].id, role=users[0].role)}"}
    h2 = {"Authorization": f"Bearer {create_access_token(user_id=users[1].id, role=users[1].role)}"}
    rate_limit.chat_limiter.reset()
    rate_limit.chat_limiter.limit = 2
    with patch("app.api.chat.generate_response") as mock_llm:
        mock_llm.return_value = "MOCK"
        codes = [
            client.post("/chat", json={"message": f"RATELIMIT-PROBE what is the leave policy {i}"}, headers=h1).status_code
            for i in range(2)
        ]
        calls_before = mock_llm.call_count
        blocked = client.post("/chat", json={"message": "RATELIMIT-PROBE blocked question"}, headers=h1)
        chk(codes == [200, 200], "first 2 messages → 200", str(codes))
        chk(blocked.status_code == 429, "3rd message within a minute → 429", f"{blocked.status_code} {blocked.text}")
        chk(mock_llm.call_count == calls_before, "blocked message never reaches the LLM")
        other = client.post("/chat", json={"message": "RATELIMIT-PROBE other user question"}, headers=h2)
        chk(other.status_code == 200, "another user is not affected", str(other.status_code))
    db.commit()
    chk(
        db.query(ChatLog).filter(ChatLog.id > client.chat_start_id, ChatLog.question == "RATELIMIT-PROBE blocked question").count() == 0,
        "blocked message is not written to chat_logs",
    )

    r = client.post("/chat", json={"message": "RATELIMIT-PROBE unauthenticated"})
    chk(r.status_code == 401, "unauthenticated chat is still 401 (auth before limit)", str(r.status_code))
finally:
    for lim, value in saved_limits.items():
        lim.limit = value
        lim.reset()
    removed = client.cleanup_chat_logs()
    print(f"\n  (cleanup: removed {removed} chat_logs rows created by this test)")
    db.close()

print(f"\nResult: {passed_count} passed, {failed_count} failed")
sys.exit(1 if failed_count else 0)
