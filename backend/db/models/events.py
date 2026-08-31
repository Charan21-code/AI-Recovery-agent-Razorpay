"""
SQLAlchemy models for Raw and Normalized Events.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.core.constants import Environment, EventType, FailureCategory
from backend.db.base import Base, IDMixin, TimestampMixin


class RawEventRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "raw_events"

    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="razorpay", nullable=False)
    environment: Mapped[str] = mapped_column(String(32), default=Environment.TEST.value, nullable=False)
    headers: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    raw_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class NormalizedEventRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "normalized_events"

    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="razorpay", nullable=False)
    environment: Mapped[str] = mapped_column(String(32), default=Environment.TEST.value, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(64), default="mer_default", index=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    order_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    payment_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    subscription_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    invoice_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)

    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    payment_method: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    failure_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_category: Mapped[str] = mapped_column(String(64), default=FailureCategory.UNKNOWN.value)
    checkout_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    is_actionable: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
