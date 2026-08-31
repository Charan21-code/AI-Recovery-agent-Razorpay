"""
Outcome and state update schemas.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from backend.core.constants import EventType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RecoveryOutcome(BaseModel):
    outcome_id: str
    execution_id: str
    event_id: str
    customer_id: str
    outcome_type: EventType = Field(..., description="RECOVERY_SUCCESS, RECOVERY_FAILED, RECOVERY_STOPPED, RECOVERY_ESCALATED")
    recovered_amount: float = Field(default=0.0, ge=0.0)
    currency: str = Field(default="INR")
    time_to_recovery_seconds: Optional[float] = Field(default=None)
    is_success: bool = Field(default=False)
    raw_details: Dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=utc_now)


class StateUpdateSummary(BaseModel):
    customer_id: str
    previous_recovery_rate: float
    updated_recovery_rate: float
    previous_total_revenue: float
    updated_total_revenue: float
    updated_fatigue_score: float
    timestamp: datetime = Field(default_factory=utc_now)
