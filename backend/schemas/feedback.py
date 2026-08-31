"""
Closed-loop learning and reward calculation schemas.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List
from pydantic import BaseModel, Field
from backend.core.constants import AgentType, RecoveryActionType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RewardBreakdown(BaseModel):
    recovered_revenue: float = Field(default=0.0, ge=0.0)
    intervention_cost: float = Field(default=0.0, ge=0.0)
    customer_friction_penalty: float = Field(default=0.0, ge=0.0)
    unnecessary_action_penalty: float = Field(default=0.0, ge=0.0)
    net_reward: float = Field(...)

    @classmethod
    def calculate(
        cls,
        recovered_revenue: float,
        intervention_cost: float,
        customer_friction_penalty: float = 0.0,
        unnecessary_action_penalty: float = 0.0,
    ) -> "RewardBreakdown":
        net = recovered_revenue - intervention_cost - customer_friction_penalty - unnecessary_action_penalty
        return cls(
            recovered_revenue=recovered_revenue,
            intervention_cost=intervention_cost,
            customer_friction_penalty=customer_friction_penalty,
            unnecessary_action_penalty=unnecessary_action_penalty,
            net_reward=round(net, 2),
        )


class FeedbackRecord(BaseModel):
    feedback_id: str
    event_id: str
    customer_id: str
    agent_type: AgentType
    action_taken: RecoveryActionType
    context_vector: Dict[str, Any] = Field(default_factory=dict)
    outcome_status: str
    recovered_revenue: float = Field(default=0.0, ge=0.0)
    reward_breakdown: RewardBreakdown
    model_version: str
    policy_version: str = Field(default="v1.0")
    created_at: datetime = Field(default_factory=utc_now)
