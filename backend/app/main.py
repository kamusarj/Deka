import logging
import time
import asyncio
from uuid import uuid4
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.core.http_limits import BodyLimitMiddleware
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import api_router
from app.core.config import settings

# ── Logging configuration ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("smart-exam-ai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    settings.check_deployment()
    logger.info(f"Starting {settings.APP_NAME} v0.1.0 in {settings.ENV} mode")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Smart Exam Matrix AI - API hỗ trợ giáo viên tạo đề kiểm tra KHTN",
    lifespan=lifespan,
)

# ── CORS Middleware ────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Session Middleware (required for OAuth) ───────────────────
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    session_cookie="smart_exam_session",
    max_age=3600,
    https_only=settings.deployed,
    same_site="lax",
)


app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.TRUSTED_HOSTS)
app.add_middleware(BodyLimitMiddleware, max_bytes=settings.MAX_REQUEST_BODY_BYTES)

# ── Request logging middleware ─────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    request.state.request_id = str(uuid4())
    start_time = time.time()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    duration_ms = round((time.time() - start_time) * 1000)
    logger.info(
        "request_id=%s %s %s → %d (%.0fms)",
        request.state.request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# ── Global exception handlers ──────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error('request_failed request_id=%s error_type=%s',
                 getattr(request.state, 'request_id', None), type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Đã xảy ra lỗi máy chủ. Vui lòng thử lại sau.",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# ── API Router ─────────────────────────────────────────────────
app.include_router(api_router, prefix="/api")


# ── Health check ───────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}


@app.get('/ready')
async def readiness():
    def check():
        from sqlalchemy import text
        from app.core.database import get_session_factory
        from app.core.migrations import check_schema
        settings.check_deployment()
        factory = get_session_factory()
        with factory() as db:
            db.execute(text('SELECT 1'))
            engine = db.get_bind()
        check_schema(engine)
        # Chroma is an optional cache; retrieval has a bounded in-memory fallback.
    try:
        await asyncio.wait_for(asyncio.to_thread(check), timeout=6)
    except Exception:
        return JSONResponse({'status': 'not_ready'}, 503)
    return {'status': 'ready'}
