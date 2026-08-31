"""
Decision context schemas enforcing temporal boundary integrity.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.core.constants import EventType, FailureCategory, LanguagePreference
from backend.schemas.customer import CustomerProfile, CustomerState
from backend.schemas.events import NormalizedEvent


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CustomerHistorySummary(BaseModel):
    total_transactions: int = Field(default=0)
    successful_transactions: int = Field(default=0)
    failed_transactions: int = Field(default=0)
    success_rate: float = Field(default=0.0)
    total_revenue_generated: float = Field(default=0.0)
    previous_recovery_attempts: int = Field(default=0)
    successful_recoveries: int = Field(default=0)
    historical_recovery_rate: float = Field(default=0.0)
    consecutive_failures_count: int = Field(default=0)
    intervention_fatigue_score: float = Field(default=0.0)
    recent_attempts_summary: List[str] = Field(default_factory=list)


class MerchantPolicyContext(BaseModel):
    max_payment_retries: int = Field(default=3)
    min_confidence_threshold: float = Field(default=0.70)
    retry_window_hours: int = Field(default=24)
    min_retry_interval_minutes: int = Field(default=30)
    max_automated_interventions: int = Field(default=3)
    allow_discount: bool = Field(default=False)
    max_discount_percent: float = Field(default=10.0)
    human_escalation_after_attempts: int = Field(default=3)


class DecisionContext(BaseModel):
    context_id: str = Field(...)
    as_of_timestamp: datetime = Field(default_factory=utc_now, description="Strict cutoff timestamp for historical query")
    current_event: NormalizedEvent
    customer_profile: CustomerProfile
    customer_state: CustomerState
    history_summary: CustomerHistorySummary
    policy_context: MerchantPolicyContext

    # Computed financial values
    revenue_at_risk: float = Field(..., ge=0)
    estimated_clv_at_risk: float = Field(default=0.0, ge=0)
    is_merchant_system_degraded: bool = Field(default=False)
    degradation_factor: float = Field(default=1.0)
