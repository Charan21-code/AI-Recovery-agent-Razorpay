"""
Unit tests for Pydantic domain schemas.
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError
from backend.core.constants import (
    AgentType,
    CommunicationChannel,
    Environment,
    EventType,
    FailureCategory,
    LanguagePreference,
    PolicyVerdictStatus,
    RecoveryActionType,
)
from backend.schemas.agent import (
    ActionProposal,
    CommunicationPayload,
    MultiStepPlan,
    PlanStep,
)
from backend.schemas.analytics import AgentPerformanceMetrics, BusinessKPIs
from backend.schemas.context import (
    CustomerHistorySummary,
    DecisionContext,
    MerchantPolicyContext,
)
from backend.schemas.customer import CustomerProfile, CustomerState
from backend.schemas.events import NormalizedEvent, RawEventPayload
from backend.schemas.execution import ExecutionRequest, ExecutionResult
from backend.schemas.feedback import FeedbackRecord, RewardBreakdown
from backend.schemas.outcomes import RecoveryOutcome
from backend.schemas.policy import PolicyRuleCheck, PolicyVerdict
from backend.schemas.predictions import (
    ActionPrediction,
    ModelPredictions,
    OpportunityScore,
)


def test_normalized_event_actionability():
    """Verify actionable vs historical event logic."""
    failed_event = NormalizedEvent(
        event_id="evt_001",
        customer_id="cust_001",
        event_type=EventType.PAYMENT_FAILED,
        amount=2499.0,
        currency="INR",
        failure_code="BANK_TIMEOUT",
        failure_category=FailureCategory.TRANSIENT_BANK_TIMEOUT,
    )
    assert failed_event.is_actionable

    success_event = NormalizedEvent(
        event_id="evt_002",
        customer_id="cust_001",
        event_type=EventType.PAYMENT_SUCCESS,
        amount=2499.0,
        currency="INR",
    )
    assert not success_event.is_actionable


def test_normalized_event_negative_amount_fails():
    """Verify validation rejects invalid negative amount."""
    with pytest.raises(ValidationError):
        NormalizedEvent(
            event_id="evt_invalid",
            customer_id="cust_001",
            event_type=EventType.PAYMENT_FAILED,
            amount=-50.0,
        )


def test_reward_breakdown_calculation():
    """Verify business reward computation formula."""
    reward = RewardBreakdown.calculate(
        recovered_revenue=4999.0,
        intervention_cost=2.50,
        customer_friction_penalty=5.0,
        unnecessary_action_penalty=0.0,
    )
    assert reward.recovered_revenue == 4999.0
    assert reward.intervention_cost == 2.50
    assert reward.net_reward == 4991.50


def test_action_proposal_and_multi_step_plan():
    """Verify multi-step plan construction and action proposal schema."""
    steps = [
        PlanStep(
            step_number=1,
            action=RecoveryActionType.DELAYED_RETRY,
            delay_minutes=30,
            description="Wait 30m for bank gateway stabilization, then retry.",
        ),
        PlanStep(
            step_number=2,
            action=RecoveryActionType.SEND_PERSONALIZED_MESSAGE,
            delay_minutes=120,
            channel=CommunicationChannel.WHATSAPP,
            condition_to_advance="ON_FAILURE",
            description="If retry fails, send Hinglish payment link on WhatsApp.",
        ),
    ]

    plan = MultiStepPlan(
        plan_id="plan_001",
        target_event_id="evt_001",
        customer_id="cust_001",
        total_steps=2,
        steps=steps,
    )

    comm = CommunicationPayload(
        channel=CommunicationChannel.WHATSAPP,
        language=LanguagePreference.HINGLISH,
        recipient_phone="+919876543210",
        message_body="Namaste Rahul! Aapka ₹2,499 ka payment bank timeout ke wajah se ruk gaya tha. Click karein to complete: https://rzp.io/l/xyz",
        payment_link_url="https://rzp.io/l/xyz",
    )

    proposal = ActionProposal(
        proposal_id="prop_001",
        agent_type=AgentType.PAYMENT_FAILURE,
        event_id="evt_001",
        customer_id="cust_001",
        selected_action=RecoveryActionType.DELAYED_RETRY,
        confidence=0.84,
        reasoning="Customer has 85% historical recovery rate with delayed retry.",
        evidence_citations=["Customer has 7/9 successful payments", "Transient bank timeout detected"],
        multi_step_plan=plan,
        communication=comm,
    )

    assert proposal.agent_type == AgentType.PAYMENT_FAILURE
    assert proposal.confidence == 0.84
    assert len(proposal.multi_step_plan.steps) == 2
    assert proposal.communication.language == LanguagePreference.HINGLISH
