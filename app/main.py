from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.employees import router as employees_router
from app.api.leaves import router as leaves_router
from app.api.attendance import router as attendance_router
from app.api.salary import router as salary_router

app = FastAPI(
    title="AI HR Assistant",
    version="0.1.0",
    description="AI-powered HR assistant — FastAPI backend.",
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(employees_router)
app.include_router(leaves_router)
app.include_router(attendance_router)
app.include_router(salary_router)


@app.get("/", tags=["Health"])
def root():
    return {"message": "AI HR Assistant is Running"}