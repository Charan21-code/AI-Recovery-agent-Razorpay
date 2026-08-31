"""
Execution layer schemas for Razorpay and Simulation dispatches.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from backend.core.constants import Environment, RecoveryActionType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ExecutionRequest(BaseModel):
    execution_id: str
    verdict_id: str
    action: RecoveryActionType
    environment: Environment = Field(default=Environment.TEST)
    target_event_id: str
    customer_id: str
    amount: float = Field(..., ge=0)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    scheduled_at: datetime = Field(default_factory=utc_now)


class ExecutionResult(BaseModel):
    execution_id: str
    status: str = Field(..., description="SUCCESS, FAILED, SCHEDULED, REJECTED")
    dispatched_action: RecoveryActionType
    environment: Environment
    external_reference_id: Optional[str] = Field(default=None, description="Razorpay payment_link_id, payment_id, order_id, etc.")
    is_simulated: bool = Field(default=False)
    error_message: Optional[str] = Field(default=None)
    response_payload: Dict[str, Any] = Field(default_factory=dict)
    executed_at: datetime = Field(default_factory=utc_now)
