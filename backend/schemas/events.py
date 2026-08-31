"""
Event schemas for Raw, Normalized, and Batch events.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.core.constants import Environment, EventType, FailureCategory


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RawEventPayload(BaseModel):
    event_id: str = Field(..., description="Unique event identifier or idempotency key")
    source: str = Field(default="razorpay", description="Event source (razorpay, simulator, custom)")
    environment: Environment = Field(default=Environment.TEST, description="Execution environment")
    raw_payload: Dict[str, Any] = Field(default_factory=dict, description="Raw unchanged payload from provider")
    headers: Dict[str, str] = Field(default_factory=dict, description="HTTP headers (e.g. X-Razorpay-Signature)")
    received_at: datetime = Field(default_factory=utc_now)


class NormalizedEvent(BaseModel):
    event_id: str = Field(..., description="Unique internal event ID")
    source: str = Field(default="razorpay")
    environment: Environment = Field(default=Environment.TEST)
    event_type: EventType = Field(..., description="Internal classified event type")

    # Timestamps & Identification
    timestamp: datetime = Field(default_factory=utc_now, description="Event occurrence timestamp")
    merchant_id: str = Field(default="mer_default", description="Merchant account ID")
    customer_id: str = Field(..., description="Internal or external customer ID")
    order_id: Optional[str] = Field(default=None, description="Associated Order ID")
    payment_id: Optional[str] = Field(default=None, description="Associated Payment Attempt ID")
    subscription_id: Optional[str] = Field(default=None, description="Associated Subscription ID")
    invoice_id: Optional[str] = Field(default=None, description="Associated Invoice ID")

    # Financial & Channel
    amount: float = Field(..., ge=0, description="Amount in standard currency units (e.g. INR)")
    currency: str = Field(default="INR", max_length=3)
    payment_method: Optional[str] = Field(default=None, description="upi, card, netbanking, wallet, emi")

    # Failure / Contextual details
    failure_code: Optional[str] = Field(default=None, description="Provider error code (e.g., BAD_REQUEST_ERROR)")
    failure_reason: Optional[str] = Field(default=None, description="Human/Provider failure description")
    failure_category: FailureCategory = Field(default=FailureCategory.UNKNOWN)
    checkout_stage: Optional[str] = Field(default=None, description="cart, address, payment_method, otp")
    attempt_count: int = Field(default=1, ge=1, description="Sequence attempt number for this order/event")

    # Metadata & Extensibility
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def is_actionable(self) -> bool:
        """Determines if this event represents a recoverable revenue loss opportunity."""
        return self.event_type in {
            EventType.PAYMENT_FAILED,
            EventType.CHECKOUT_ABANDONED,
            EventType.SUBSCRIPTION_PAYMENT_FAILED,
            EventType.INVOICE_OVERDUE,
            EventType.MANDATE_FAILED,
        }


class EventBatch(BaseModel):
    batch_id: str
    events: List[NormalizedEvent]
    total_count: int
