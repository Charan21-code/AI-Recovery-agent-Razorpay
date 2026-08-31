"""
Agent proposal, multi-step plan, and communication schemas.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from backend.core.constants import (
    AgentType,
    CommunicationChannel,
    LanguagePreference,
    RecoveryActionType,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CommunicationPayload(BaseModel):
    channel: CommunicationChannel
    language: LanguagePreference = Field(default=LanguagePreference.HINGLISH)
    recipient_phone: Optional[str] = Field(default=None)
    recipient_email: Optional[str] = Field(default=None)
    subject: Optional[str] = Field(default=None)
    message_body: str
    payment_link_url: Optional[str] = Field(default=None)
    call_script: Optional[str] = Field(default=None, description="Voice agent script if voice channel")


class PlanStep(BaseModel):
    step_number: int = Field(..., ge=1)
    action: RecoveryActionType
    delay_minutes: int = Field(default=0, ge=0)
    channel: CommunicationChannel = Field(default=CommunicationChannel.NONE)
    condition_to_advance: str = Field(default="ON_FAILURE", description="ON_FAILURE, ON_NO_RESPONSE, UNCONDITIONAL")
    description: str


class MultiStepPlan(BaseModel):
    plan_id: str
    target_event_id: str
    customer_id: str
    total_steps: int
    current_step_index: int = Field(default=1)
    steps: List[PlanStep]
    created_at: datetime = Field(default_factory=utc_now)


class ActionProposal(BaseModel):
    proposal_id: str
    agent_type: AgentType
    event_id: str
    customer_id: str
    selected_action: RecoveryActionType
    confidence: float = Field(..., ge=0.0, le=1.0)
    reasoning: str
    evidence_citations: List[str] = Field(default_factory=list)
    multi_step_plan: Optional[MultiStepPlan] = Field(default=None)
    communication: Optional[CommunicationPayload] = Field(default=None)
    requires_human_review: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)
