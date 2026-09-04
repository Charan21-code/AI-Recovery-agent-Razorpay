"""
FastAPI Main Application Entry Point.
Autonomous Revenue Recovery Intelligence Engine & Voice Agent API.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.db.init_db import init_sync_db
from backend.api.v1.router import router as api_v1_router

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler: initializes SQLite database schemas on startup."""
    logger.info("Initializing database schemas...")
    try:
        init_sync_db()
        logger.info("Database schemas verified successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
    yield
    logger.info("Shutting down Revenue Recovery Intelligence Engine...")


app = FastAPI(
    title="Razorpay Autonomous Revenue Recovery Intelligence Engine",
    description="Multi-agent AI recovery pipeline with real-time autonomous voice calling, LLM reasoning, and closed-loop bandit feedback.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Configuration for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Permits Vite development server (localhost:5173) and production hosts
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API v1 router
app.include_router(api_v1_router, prefix="/api/v1")


@app.get("/health", summary="Health Check")
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database": "connected",
        "voice_agent": "ready",
        "llm_provider": settings.LLM_PROVIDER,
    }


@app.get("/", summary="Root Documentation")
async def root():
    return {
        "message": "Welcome to Razorpay Autonomous Revenue Recovery Intelligence Engine API",
        "docs_url": "/docs",
        "api_v1": "/api/v1",
        "endpoints": {
            "kpis": "/api/v1/analytics/kpis",
            "opportunity_queue": "/api/v1/analytics/queue",
            "event_explorer": "/api/v1/analytics/events",
            "bandit": "/api/v1/analytics/bandit",
            "customer_360": "/api/v1/customers/{customer_id}",
            "pipeline_simulate": "/api/v1/pipeline/simulate",
            "stream_events": "/api/v1/stream/live-events",
            "webhook": "/api/v1/webhooks/razorpay",
            "voice_start": "/api/v1/voice/session/start",
            "voice_turn": "/api/v1/voice/session/turn",
        },
    }

