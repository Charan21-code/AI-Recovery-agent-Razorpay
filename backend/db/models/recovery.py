"""
SQLAlchemy models for Multi-Agent Recovery Decisions, Policy Checks, Executions, and Outcomes.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.core.constants import (
    AgentType,
    Environment,
    PolicyVerdictStatus,
    RecoveryActionType,
)
from backend.db.base import Base, IDMixin, TimestampMixin


class RecoveryDecisionRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "recovery_decisions"

    decision_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    agent_type: Mapped[str] = mapped_column(String(64), default=AgentType.PAYMENT_FAILURE.value, index=True, nullable=False)

    selected_action: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_citations_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=list)

    multi_step_plan_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    communication_payload_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False)


class PolicyCheckRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "policy_checks"

    verdict_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    decision_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    proposal_action: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_action: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default=PolicyVerdictStatus.APPROVED.value, nullable=False)
    rules_checked_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=list)
    modification_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    requires_escalation: Mapped[bool] = mapped_column(Boolean, default=False)


class ExecutionLogRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "execution_logs"

    execution_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    verdict_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), default=Environment.TEST.value, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    external_reference_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_payload_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class OutcomeRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "recovery_outcomes"

    outcome_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    execution_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    outcome_type: Mapped[str] = mapped_column(String(64), nullable=False)
    recovered_amount: Mapped[float] = mapped_column(Float, default=0.0)
    is_success: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    time_to_recovery_seconds: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    details_json: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
