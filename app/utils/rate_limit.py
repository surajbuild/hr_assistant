"""
app/utils/rate_limit.py
-----------------------
In-memory sliding-window rate limiting for abuse-prone endpoints (D-031).

Limiters
--------
login_ip_limiter        — every POST /auth/login attempt, per client IP
login_failure_limiter   — failed logins per (client IP, email); cleared by a successful login
chat_limiter            — POST /chat per authenticated user (protects the LLM budget)

Limits come from the environment (see .env.example):
    RATE_LIMIT_ENABLED                    default true
    RATE_LIMIT_LOGIN_PER_MINUTE           default 30
    RATE_LIMIT_LOGIN_FAILURES             default 5
    RATE_LIMIT_LOGIN_FAILURE_WINDOW_SECONDS default 900
    RATE_LIMIT_CHAT_PER_MINUTE            default 20
    TRUSTED_PROXY_IPS                     default 127.0.0.1,::1 — IPs/CIDRs whose X-Forwarded-For is believed

State lives in process memory: it resets on restart and is per worker. A multi-worker
deployment needs a shared store (e.g. Redis) — see KNOWN_ISSUES KI-031.
"""

import math
import os
import threading
import time
from collections import deque
from ipaddress import IPv4Network, IPv6Network, ip_address, ip_network
from typing import Callable, Deque, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import HTTPException, Request, status

load_dotenv()


# ---------------------------------------------------------------------------
# Limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Sliding-window counter: at most `limit` hits per `window_seconds` for each key."""

    def __init__(
        self,
        name: str,
        limit: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.name = name
        self.limit = limit
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: Dict[str, Deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: str, now: float) -> Deque[float]:
        hits = self._hits.setdefault(key, deque())
        while hits and hits[0] <= now - self.window_seconds:
            hits.popleft()
        return hits

    def retry_after(self, key: str) -> Optional[int]:
        """Seconds until `key` may try again, or None when it is under the limit."""
        with self._lock:
            now = self._clock()
            hits = self._prune(key, now)
            if len(hits) < self.limit:
                return None
            return max(1, math.ceil(hits[0] + self.window_seconds - now))

    def hit(self, key: str) -> None:
        """Record one hit for `key`."""
        with self._lock:
            now = self._clock()
            self._prune(key, now).append(now)

    def reset(self, key: Optional[str] = None) -> None:
        """Forget one key, or everything."""
        with self._lock:
            if key is None:
                self._hits.clear()
            else:
                self._hits.pop(key, None)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def is_enabled() -> bool:
    return os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower() not in ("0", "false", "no", "off")


def _parse_networks(raw: str) -> List[IPv4Network | IPv6Network]:
    networks = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                networks.append(ip_network(part, strict=False))
            except ValueError:
                pass
    return networks


# IPs or CIDR ranges (e.g. a Docker network "172.28.0.0/16")
TRUSTED_PROXY_NETWORKS = _parse_networks(os.getenv("TRUSTED_PROXY_IPS", "127.0.0.1,::1"))


def _is_trusted_proxy(host: str) -> bool:
    try:
        address = ip_address(host)
    except ValueError:
        return False
    return any(address in network for network in TRUSTED_PROXY_NETWORKS)

login_ip_limiter = RateLimiter("login_ip", _int_env("RATE_LIMIT_LOGIN_PER_MINUTE", 30), 60)
login_failure_limiter = RateLimiter(
    "login_failures",
    _int_env("RATE_LIMIT_LOGIN_FAILURES", 5),
    _int_env("RATE_LIMIT_LOGIN_FAILURE_WINDOW_SECONDS", 900),
)
chat_limiter = RateLimiter("chat", _int_env("RATE_LIMIT_CHAT_PER_MINUTE", 20), 60)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def client_ip(request: Request) -> str:
    """
    The caller's IP. X-Forwarded-For is only believed when the direct peer is a trusted
    proxy (the Bun server overwrites the header with the real client address), so a client
    talking to the backend directly cannot spoof its way out of the limit.
    """
    peer = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and _is_trusted_proxy(peer):
        return forwarded.split(",")[-1].strip() or peer
    return peer


def raise_too_many_requests(retry_after: int, what: str) -> None:
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=f"Too many {what}. Please try again in {retry_after} seconds.",
        headers={"Retry-After": str(retry_after)},
    )


def enforce(limiter: RateLimiter, key: str, what: str, record: bool = True) -> None:
    """Raise 429 when `key` is over `limiter`'s limit; otherwise record the hit (unless record=False)."""
    if not is_enabled():
        return
    wait = limiter.retry_after(key)
    if wait is not None:
        raise_too_many_requests(wait, what)
    if record:
        limiter.hit(key)
