"""
DevOps Incident Agent — FastAPI Application Entry Point.

Production-grade autonomous incident response system powered by
a 5-agent LangGraph pipeline with Google Gemini.
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from database import init_db, close_db, check_db_health
from services.log_monitor import start_log_monitor, stop_log_monitor

# ── Logging Configuration ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if get_settings().DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("devops_agent")


# ── Lifespan ───────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup and shutdown lifecycle.
    - Startup: Initialize database tables, start background services.
    - Shutdown: Close DB connections, stop background tasks.
    """
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"LLM Model: {settings.GEMINI_MODEL}")
    logger.info(f"Debug Mode: {settings.DEBUG}")

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Start background tasks
    await start_log_monitor()

    yield

    # Shutdown
    await stop_log_monitor()
    await close_db()
    logger.info("Application shutdown complete")


# ── FastAPI App ────────────────────────────────────────────────────────
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Autonomous DevOps Incident Response Agent — "
        "5-agent AI pipeline for anomaly detection, root cause analysis, "
        "and automated incident response."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS Middleware ────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global Exception Handler ──────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler returning consistent JSON responses."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "error": "Internal server error. Check logs for details.",
        },
    )


# ── Import & Register Routers ─────────────────────────────────────────
from routers import logs, incidents, apps, analytics  # noqa: E402

app.include_router(logs.router, prefix="/api/v1", tags=["Logs"])
app.include_router(incidents.router, prefix="/api/v1", tags=["Incidents"])
app.include_router(apps.router, prefix="/api/v1", tags=["Apps"])
app.include_router(analytics.router, prefix="/api/v1", tags=["Analytics"])


# ── Health Check ───────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health_check():
    """
    System health check endpoint.
    Verifies API and database connectivity.
    """
    db_healthy = await check_db_health()
    status = "healthy" if db_healthy else "degraded"

    return {
        "success": True,
        "data": {
            "status": status,
            "version": settings.APP_VERSION,
            "model": settings.GEMINI_MODEL,
            "database": "connected" if db_healthy else "disconnected",
        },
        "error": None,
    }


@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API information."""
    return {
        "success": True,
        "data": {
            "name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "health": "/health",
        },
        "error": None,
    }
