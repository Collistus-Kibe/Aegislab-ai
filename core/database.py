"""
AegisLab AI — Async Database Layer (TiDB / MySQL-compatible)
Uses SQLAlchemy async engine with aiomysql driver for non-blocking DB access.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, JSON, String
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from shared.config import settings

# ── Engine & Session Factory ────────────────────────────────────────────────

import ssl as _ssl

_ssl_ctx = _ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = _ssl.CERT_NONE

engine = create_async_engine(
    settings.TIDB_URL,
    echo=True,
    connect_args={"ssl": _ssl_ctx},
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


# ── ORM Models ──────────────────────────────────────────────────────────────

class LabRecord(Base):
    """
    Persists every lab-analysis transaction.

    Stores the raw input, AI-generated summary, and risk classification
    alongside Firebase user and optional patient identifiers.
    """

    __tablename__ = "lab_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(128), index=True, nullable=False, comment="Firebase UID")
    patient_id = Column(String(128), nullable=True)
    raw_data = Column(JSON, nullable=False, comment="Original lab test key-value pairs")
    ai_summary = Column(String(4096), nullable=False)
    risk_level = Column(String(16), nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<LabRecord id={self.id} user={self.user_id} "
            f"risk={self.risk_level} created={self.created_at}>"
        )


class Patient(Base):
    """
    Stores patient profiles linked to a Firebase user.

    Created automatically when a new patient is first analyzed.
    """

    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(String(128), index=True, nullable=False, comment="Firebase UID")
    patient_ref = Column(String(128), index=True, nullable=False, comment="Custom patient reference ID")
    name = Column(String(256), nullable=False, default="Unknown Patient")
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Patient id={self.id} ref={self.patient_ref} name={self.name}>"


# ── Dependency ──────────────────────────────────────────────────────────────

async def get_db():
    """
    FastAPI dependency that yields an async database session.

    Usage::

        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
