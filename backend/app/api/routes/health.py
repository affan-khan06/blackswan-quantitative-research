from datetime import datetime, timezone
from fastapi import APIRouter
from sqlalchemy import text

from backend.app.core.config import get_settings
from backend.database.session import engine

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
def health_check() -> dict:
    settings = get_settings()
    db_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "ok" if db_ok else "degraded",
        "service": "BLACKSWAN Quantitative Risk API",
        "version": settings.model_version,
        "database_connected": db_ok,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
