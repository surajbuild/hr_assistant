import os
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

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

app = FastAPI(
    title="AI HR Assistant",
    version="0.1.0",
    description="AI-powered HR assistant — FastAPI backend.",
)

# ── Session Middleware (Required by Authlib for OAuth CSRF state/nonce) ───────
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY") or os.getenv("JWT_SECRET_KEY") or "default-session-secret-key"
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


@app.get("/", tags=["Health"])
def root():
    return {"message": "AI HR Assistant is Running"}