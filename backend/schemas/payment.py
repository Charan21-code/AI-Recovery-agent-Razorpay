"""
Transaction, Order, Subscription, and Invoice schemas.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PaymentRecordSchema(BaseModel):
    payment_id: str = Field(...)
    order_id: Optional[str] = Field(default=None)
    customer_id: str = Field(...)
    merchant_id: str = Field(default="mer_default")
    amount: float = Field(..., ge=0)
    currency: str = Field(default="INR")
    status: str = Field(default="created", description="created, authorized, captured, failed, refunded")
    payment_method: Optional[str] = Field(default=None)
    failure_code: Optional[str] = Field(default=None)
    failure_reason: Optional[str] = Field(default=None)
    attempt_number: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=utc_now)


class OrderRecordSchema(BaseModel):
    order_id: str = Field(...)
    customer_id: str = Field(...)
    merchant_id: str = Field(default="mer_default")
    amount: float = Field(..., ge=0)
    currency: str = Field(default="INR")
    status: str = Field(default="created", description="created, attempted, paid")
    attempts_count: int = Field(default=0, ge=0)
    is_recovered: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)


class SubscriptionRecordSchema(BaseModel):
    subscription_id: str = Field(...)
    customer_id: str = Field(...)
    merchant_id: str = Field(default="mer_default")
    plan_name: Optional[str] = Field(default="Standard Recurring")
    recurring_amount: float = Field(..., ge=0)
    currency: str = Field(default="INR")
    status: str = Field(default="active", description="active, pending, halted, cancelled, completed")
    grace_period_days: int = Field(default=7, ge=0)
    dunning_attempt_count: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)


class InvoiceRecordSchema(BaseModel):
    invoice_id: str = Field(...)
    customer_id: str = Field(...)
    merchant_id: str = Field(default="mer_default")
    amount: float = Field(..., ge=0)
    currency: str = Field(default="INR")
    status: str = Field(default="issued", description="issued, paid, overdue, cancelled")
    due_date: datetime
    aging_days: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)
