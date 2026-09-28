from fastapi import FastAPI

from app.api.auth import router as auth_router

app = FastAPI(
    title="AI HR Assistant",
    version="0.1.0",
    description="AI-powered HR assistant — FastAPI backend.",
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth_router)


@app.get("/", tags=["Health"])
def root():
    return {"message": "AI HR Assistant is Running"}