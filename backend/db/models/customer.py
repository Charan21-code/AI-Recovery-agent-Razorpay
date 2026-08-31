"""
SQLAlchemy models for Customer Profile and State Snapshots.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from backend.core.constants import LanguagePreference
from backend.db.base import Base, IDMixin, TimestampMixin


class CustomerRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(64), default="mer_default", index=True, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(128), default="Valued Customer")
    email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    preferred_language: Mapped[str] = mapped_column(String(16), default=LanguagePreference.HINGLISH.value)
    is_vip: Mapped[bool] = mapped_column(Boolean, default=False)
    opted_out_of_outreach: Mapped[bool] = mapped_column(Boolean, default=False)


class CustomerStateSnapshotRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "customer_state_snapshots"

    customer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    as_of_event_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    as_of_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)

    total_transactions: Mapped[int] = mapped_column(Integer, default=0)
    successful_transactions: Mapped[int] = mapped_column(Integer, default=0)
    failed_transactions: Mapped[int] = mapped_column(Integer, default=0)
    success_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_revenue_generated: Mapped[float] = mapped_column(Float, default=0.0)
    average_transaction_value: Mapped[float] = mapped_column(Float, default=0.0)

    total_recovery_attempts: Mapped[int] = mapped_column(Integer, default=0)
    successful_recoveries: Mapped[int] = mapped_column(Integer, default=0)
    failed_recoveries: Mapped[int] = mapped_column(Integer, default=0)
    historical_recovery_rate: Mapped[float] = mapped_column(Float, default=0.0)
    average_recovery_time_minutes: Mapped[float] = mapped_column(Float, default=0.0)

    recent_intervention_count: Mapped[int] = mapped_column(Integer, default=0)
    consecutive_failures_count: Mapped[int] = mapped_column(Integer, default=0)
    intervention_fatigue_score: Mapped[float] = mapped_column(Float, default=0.0)

    preferred_payment_method: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    estimated_clv: Mapped[float] = mapped_column(Float, default=0.0)
    state_payload_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
