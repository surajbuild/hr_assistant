"""
app/main.py
-----------
FastAPI application: middleware, routers and health endpoints.

    GET /              — legacy liveness message
    GET /health        — liveness (the process answers)
    GET /health/ready  — readiness: the database answers `SELECT 1` (200) or not (503); used by the Docker
                         healthcheck so the frontend only starts once the API can serve data
"""

import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware

from app.database.connection import engine
from app.utils.logging import configure_logging
from app.utils.security import load_secret

from app.api.auth import router as auth_router
from app.api.employees import router as employees_router
from app.api.leaves import router as leaves_router
from app.api.attendance import router as attendance_router
from app.api.salary import router as salary_router
from app.api.chat import router as chat_router
from app.api.dashboard import router as dashboard_router
from app.api.reports import router as reports_router
from app.api.departments import router as departments_router
from app.api.documents import router as documents_router
from app.api.users import router as users_router
from app.api.holidays import router as holidays_router

configure_logging()
logger = logging.getLogger("app.main")

app = FastAPI(
    title="AI HR Assistant",
    version="0.1.0",
    description="AI-powered HR assistant — FastAPI backend.",
)

# ── Session Middleware (Required by Authlib for OAuth CSRF state/nonce) ───────
# No fallback: a missing / short secret stops the app at startup (KI-011).
SESSION_SECRET_KEY = load_secret("SESSION_SECRET_KEY")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET_KEY)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(employees_router)
app.include_router(leaves_router)
app.include_router(attendance_router)
app.include_router(salary_router)
app.include_router(chat_router)
app.include_router(dashboard_router)
app.include_router(reports_router)
app.include_router(departments_router)
app.include_router(documents_router)
app.include_router(users_router)
app.include_router(holidays_router)


@app.get("/", tags=["Health"])
def root():
    return {"message": "AI HR Assistant is Running"}


@app.get("/health", tags=["Health"], summary="Liveness")
def health():
    return {"status": "ok"}


@app.get("/health/ready", tags=["Health"], summary="Readiness (database reachable)")
def health_ready():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.warning("Readiness check failed: %s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "unreachable"})
    return {"status": "ok", "database": "ok"}