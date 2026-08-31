"""
Policy engine check and verdict schemas.
"""

from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field
from backend.core.constants import PolicyVerdictStatus, RecoveryActionType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PolicyRuleCheck(BaseModel):
    rule_name: str
    passed: bool
    details: str
    evaluated_value: Optional[str] = None
    threshold_value: Optional[str] = None


class PolicyVerdict(BaseModel):
    verdict_id: str
    proposal_id: str
    status: PolicyVerdictStatus
    original_action: RecoveryActionType
    approved_action: RecoveryActionType
    rules_checked: List[PolicyRuleCheck] = Field(default_factory=list)
    modification_reason: Optional[str] = Field(default=None)
    requires_escalation: bool = Field(default=False)
    timestamp: datetime = Field(default_factory=utc_now)
