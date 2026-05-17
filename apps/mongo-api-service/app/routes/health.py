from fastapi import APIRouter, Response, status as http_status
from datetime import datetime, timezone

from app import database
from app.config import settings
from app.logger import get_logger

router = APIRouter(tags=["health"])
log = get_logger(__name__)

START_TIME = datetime.now(timezone.utc)


@router.get("/health")
async def health():
    """Liveness probe — returns 200 if the service is running."""
    return {"status": "ok", "service": settings.APP_NAME}


@router.get("/health/ready")
async def readiness(response: Response):
    """Readiness probe — checks MongoDB connectivity."""
    try:
        client = database.get_client()
        if client is None:
            raise RuntimeError("MongoDB client is not initialized")
        await client.admin.command("ping")
        db = database.get_db()
        stats = await db.command("dbStats")
        mongo_ok = True
        collections = stats.get("collections", 0)
    except Exception as exc:
        log.error(f"Readiness check failed: {exc}")
        mongo_ok = False
        collections = None

    uptime_seconds = (datetime.now(timezone.utc) - START_TIME).total_seconds()

    readiness_status = "ready" if mongo_ok else "degraded"
    if not mongo_ok:
        response.status_code = http_status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": readiness_status,
        "uptime_seconds": round(uptime_seconds, 1),
        "mongo": {
            "connected": mongo_ok,
            "database": settings.MONGO_DB,
            "collections": collections,
        },
    }
