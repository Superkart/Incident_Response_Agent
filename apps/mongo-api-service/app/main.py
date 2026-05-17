from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
import time

from app.config import settings
from app.database import connect, disconnect
from app.routes import items, health
from app.logger import get_logger

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect()
    yield
    await disconnect()


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
