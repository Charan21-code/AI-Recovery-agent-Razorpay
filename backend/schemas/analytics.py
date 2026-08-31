"""
Analytics, KPIs, and multi-agent metrics schemas.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from backend.core.constants import AgentType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentPerformanceMetrics(BaseModel):
    agent_type: AgentType
    events_routed: int = Field(default=0)
    actions_attempted: int = Field(default=0)
    successful_recoveries: int = Field(default=0)
    failed_recoveries: int = Field(default=0)
    revenue_at_risk: float = Field(default=0.0)
    total_recovered_revenue: float = Field(default=0.0)
    recovery_rate: float = Field(default=0.0)
    net_recovered_revenue: float = Field(default=0.0)
    roi: float = Field(default=0.0)
    average_recovery_time_minutes: float = Field(default=0.0)


class BusinessKPIs(BaseModel):
    total_events_processed: int = Field(default=0)
    actionable_events_count: int = Field(default=0)
    total_revenue_at_risk: float = Field(default=0.0)
    expected_recovery_value: float = Field(default=0.0)
    actual_recovered_revenue: float = Field(default=0.0)
    total_intervention_cost: float = Field(default=0.0)
    net_revenue_recovered: float = Field(default=0.0)
    overall_recovery_rate: float = Field(default=0.0)
    overall_roi: float = Field(default=0.0)
    average_recovery_time_minutes: float = Field(default=0.0)
    agent_breakdowns: Dict[str, AgentPerformanceMetrics] = Field(default_factory=dict)
    as_of: datetime = Field(default_factory=utc_now)
