"""
AegisLab AI — FastAPI Application Entry Point
Run with: uvicorn main:app --reload
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from shared.config import settings
from api.routes.diagnostics import router as diagnostics_router

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Clinical Diagnostic Copilot — AI-powered lab result analysis",
    version="1.0.0",
)

# ── CORS (allow frontend to talk to backend) ────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ───────────────────────────────────────────────────────────
app.include_router(diagnostics_router, prefix="/api/v1")

# ── Static frontend (optional — serve index.html) ───────────────────
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

# ── Startup ──────────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    from core.database import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("✓ Database tables created/verified")
    logger.info("✓ %s is running", settings.PROJECT_NAME)
