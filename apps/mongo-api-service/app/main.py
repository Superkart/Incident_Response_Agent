import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
import time

from app.config import settings
from app import database
from app.metrics import dependency_last_check_timestamp_seconds, dependency_up
from app.routes import items, health
from app.logger import get_logger

log = get_logger(__name__)

SERVICE_NAME = "mongo-api-service"
MONGO_DEPENDENCY = "mongodb"
DEPENDENCY_CHECK_INTERVAL_SECONDS = 5


async def check_mongo_dependency():
    try:
        client = database.get_client()
        if client is None:
            await database.connect()
        else:
            await client.admin.command("ping")
        dependency_up.labels(SERVICE_NAME, MONGO_DEPENDENCY).set(1)
    except Exception:
        dependency_up.labels(SERVICE_NAME, MONGO_DEPENDENCY).set(0)
        log.exception("Dependency check failed dependency=%s", MONGO_DEPENDENCY)
    finally:
        dependency_last_check_timestamp_seconds.labels(
            SERVICE_NAME,
            MONGO_DEPENDENCY,
        ).set(datetime.now(timezone.utc).timestamp())


async def dependency_monitor():
    while True:
        await check_mongo_dependency()
        await asyncio.sleep(DEPENDENCY_CHECK_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    monitor_task = asyncio.create_task(dependency_monitor())
    await check_mongo_dependency()
    yield
    monitor_task.cancel()
    with suppress(asyncio.CancelledError):
        await monitor_task
    await database.disconnect()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)
Instrumentator().instrument(app).expose(app)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        elapsed = round((time.perf_counter() - start) * 1000, 2)
        log.exception(f"{request.method} {request.url.path} failed ({elapsed}ms)")
        raise

    elapsed = round((time.perf_counter() - start) * 1000, 2)
    message = f"{request.method} {request.url.path} -> {response.status_code} ({elapsed}ms)"
    if response.status_code >= 500:
        log.error(message)
    elif response.status_code >= 400:
        log.warning(message)
    else:
        log.info(message)
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    log.warning(
        f"Validation failed on {request.method} {request.url.path}: {exc.errors()}"
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    log.exception(f"Unhandled error on {request.method} {request.url.path}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(health.router)
app.include_router(items.router)
