"""GET /health — Render healthCheckPath and local smoke tests."""

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine
from app.schemas.envelope import ok

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    db_ok = True
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    status = "ok" if db_ok else "degraded"
    return ok({"status": status, "database": "up" if db_ok else "down"})
