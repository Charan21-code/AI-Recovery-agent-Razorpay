"""
SQLAlchemy models for Feedback Learning, Audit Trail, and Merchant Policies.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.base import Base, IDMixin, TimestampMixin


class FeedbackRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "feedback_records"

    feedback_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    agent_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    action_taken: Mapped[str] = mapped_column(String(64), nullable=False)
    context_vector_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    outcome_status: Mapped[str] = mapped_column(String(64), nullable=False)
    recovered_revenue: Mapped[float] = mapped_column(Float, default=0.0)

    intervention_cost: Mapped[float] = mapped_column(Float, default=0.0)
    customer_friction_penalty: Mapped[float] = mapped_column(Float, default=0.0)
    unnecessary_action_penalty: Mapped[float] = mapped_column(Float, default=0.0)
    net_reward: Mapped[float] = mapped_column(Float, nullable=False)

    model_version: Mapped[str] = mapped_column(String(64), default="v1.0")
    policy_version: Mapped[str] = mapped_column(String(64), default="v1.0")


class AuditTrailRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "audit_trails"

    audit_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    decision_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    verdict_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    execution_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)
    outcome_id: Mapped[Optional[str]] = mapped_column(String(128), index=True, nullable=True)

    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    details_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MerchantPolicyRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "merchant_policies"

    merchant_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    max_payment_retries: Mapped[int] = mapped_column(Integer, default=3)
    min_confidence_threshold: Mapped[float] = mapped_column(Float, default=0.70)
    retry_window_hours: Mapped[int] = mapped_column(Integer, default=24)
    min_retry_interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    max_automated_interventions: Mapped[int] = mapped_column(Integer, default=3)
    allow_discount: Mapped[bool] = mapped_column(Boolean, default=False)
    max_discount_percent: Mapped[float] = mapped_column(Float, default=10.0)
    human_escalation_after_attempts: Mapped[int] = mapped_column(Integer, default=3)
    policy_version: Mapped[str] = mapped_column(String(32), default="v1.0")
    custom_rules_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
