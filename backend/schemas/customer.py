"""
Customer profile and rolling state schemas.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from backend.core.constants import LanguagePreference


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CustomerProfile(BaseModel):
    customer_id: str = Field(..., description="Unique internal customer ID")
    merchant_id: str = Field(default="mer_default")
    name: Optional[str] = Field(default="Valued Customer")
    email: Optional[str] = Field(default=None)
    phone: Optional[str] = Field(default=None)
    preferred_language: LanguagePreference = Field(default=LanguagePreference.HINGLISH)
    is_vip: bool = Field(default=False)
    opted_out_of_outreach: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)


class CustomerState(BaseModel):
    customer_id: str = Field(...)
    merchant_id: str = Field(default="mer_default")

    # Transaction Statistics
    total_transactions: int = Field(default=0, ge=0)
    successful_transactions: int = Field(default=0, ge=0)
    failed_transactions: int = Field(default=0, ge=0)
    success_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    total_revenue_generated: float = Field(default=0.0, ge=0.0)
    average_transaction_value: float = Field(default=0.0, ge=0.0)

    # Recovery Statistics
    total_recovery_attempts: int = Field(default=0, ge=0)
    successful_recoveries: int = Field(default=0, ge=0)
    failed_recoveries: int = Field(default=0, ge=0)
    historical_recovery_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    average_recovery_time_minutes: float = Field(default=0.0, ge=0.0)

    # Recency & Fatigue
    last_transaction_at: Optional[datetime] = Field(default=None)
    last_failure_at: Optional[datetime] = Field(default=None)
    last_intervention_at: Optional[datetime] = Field(default=None)
    recent_intervention_count: int = Field(default=0, ge=0)
    consecutive_failures_count: int = Field(default=0, ge=0)
    intervention_fatigue_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Method & Channel Preferences
    preferred_payment_method: Optional[str] = Field(default=None)
    preferred_channel: Optional[str] = Field(default=None)
    estimated_clv: float = Field(default=0.0, ge=0.0)
    last_updated_at: datetime = Field(default_factory=utc_now)
