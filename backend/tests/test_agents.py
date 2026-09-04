import pytest
from datetime import datetime, timezone, timedelta

from backend.core.constants import (
    AgentType,
    CommunicationChannel,
    EventType,
    FailureCategory,
    RecoveryActionType,
)
from backend.schemas.predictions import OpportunityScore
from backend.schemas.context import CustomerHistorySummary, DecisionContext, MerchantPolicyContext
from backend.schemas.customer import CustomerProfile, CustomerState
from backend.schemas.events import NormalizedEvent
from backend.schemas.predictions import ActionPrediction, ModelPredictions

from backend.services.agents.orchestrator import orchestrator


@pytest.fixture
def base_context():
    base_time = datetime.now(timezone.utc)
    return DecisionContext(
        context_id="ctx_test",
        as_of_timestamp=base_time,
        customer_profile=CustomerProfile(
            customer_id="cust_test",
            name="Test Customer",
        ),
        customer_state=CustomerState(
            customer_id="cust_test",
            total_transactions=5,
            consecutive_failures_count=1,
            estimated_clv=1000.0,
        ),
        history_summary=CustomerHistorySummary(),
        policy_context=MerchantPolicyContext(),
        current_event=NormalizedEvent(
            event_id="evt_test",
            customer_id="cust_test",
            event_type=EventType.PAYMENT_FAILED,
            amount=500.0,
            currency="INR",
            failure_category=FailureCategory.TRANSIENT_BANK_TIMEOUT,
            timestamp=base_time,
        ),
        revenue_at_risk=500.0,
        is_merchant_system_degraded=False,
    )


@pytest.fixture
def base_predictions():
    return ModelPredictions(
        prediction_id="pred_test",
        context_id="ctx_test",
        overall_recovery_propensity=0.75,
        best_candidate_action=RecoveryActionType.DELAYED_RETRY,
        best_expected_value=375.0,
        opportunity_score=75.0,
        optimal_delay_minutes=30,
        action_predictions={},
    )


@pytest.fixture
def base_opportunity():
    return OpportunityScore(
        opportunity_id="opp_test",
        event_id="evt_test",
        context_id="ctx_test",
        customer_id="cust_test",
        customer_name="Test Customer",
        event_type=EventType.PAYMENT_FAILED.value,
        amount=500.0,
        recovery_propensity=0.75,
        expected_recovery_value=375.0,
        recommended_action=RecoveryActionType.DELAYED_RETRY,
        score=75.0,
        priority_level="HIGH",
    )


def test_orchestrator_routes_to_payment_failure_agent(base_context, base_predictions, base_opportunity):
    """Test that PAYMENT_FAILED routes to PaymentFailureAgent."""
    proposal = orchestrator.dispatch(base_context, base_predictions, base_opportunity)
    
    assert proposal.agent_type == AgentType.PAYMENT_FAILURE
    assert proposal.selected_action == RecoveryActionType.DELAYED_RETRY
    assert proposal.confidence == 0.75


def test_payment_failure_agent_hard_decline(base_context, base_predictions, base_opportunity):
    """Test that hard declines force a payment method update."""
    # Modify event to be a hard decline
    base_context.current_event.failure_category = FailureCategory.EXPIRED_OR_BLOCKED_CARD
    
    proposal = orchestrator.dispatch(base_context, base_predictions, base_opportunity)
    
    assert proposal.agent_type == AgentType.PAYMENT_FAILURE
    assert proposal.selected_action == RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE
    assert proposal.communication is not None
    assert proposal.communication.channel == CommunicationChannel.EMAIL


def test_payment_failure_agent_system_degradation(base_context, base_predictions, base_opportunity):
    """Test that system degradation forces a delayed retry."""
    base_context.is_merchant_system_degraded = True
    # Model recommends immediate retry, but agent should override
    base_opportunity.recommended_action = RecoveryActionType.IMMEDIATE_RETRY
    
    proposal = orchestrator.dispatch(base_context, base_predictions, base_opportunity)
    
    assert proposal.agent_type == AgentType.PAYMENT_FAILURE
    assert proposal.selected_action == RecoveryActionType.DELAYED_RETRY
    assert proposal.confidence == 0.9


def test_orchestrator_routes_to_checkout_abandonment_agent(base_context, base_predictions, base_opportunity):
    """Test that CHECKOUT_ABANDONED routes to CheckoutAbandonmentAgent."""
    base_context.current_event.event_type = EventType.CHECKOUT_ABANDONED
    base_context.current_event.failure_category = FailureCategory.INACTIVITY_DROPOFF
    
    proposal = orchestrator.dispatch(base_context, base_predictions, base_opportunity)
    
    assert proposal.agent_type == AgentType.CHECKOUT_ABANDONMENT
    assert proposal.selected_action == RecoveryActionType.SEND_CHECKOUT_RECOVERY
    assert proposal.communication is not None
    assert "https://rzp.io/i/checkout_" in proposal.communication.payment_link_url


def test_orchestrator_routes_to_subscription_agent(base_context, base_predictions, base_opportunity):
    """Test that SUBSCRIPTION_PAYMENT_FAILED routes to SubscriptionRecoveryAgent."""
    base_context.current_event.event_type = EventType.SUBSCRIPTION_PAYMENT_FAILED
    
    proposal = orchestrator.dispatch(base_context, base_predictions, base_opportunity)
    
    assert proposal.agent_type == AgentType.SUBSCRIPTION_RECOVERY
    # For early stage, it should schedule dunning
    assert proposal.selected_action == RecoveryActionType.SCHEDULE_DUNNING_STEP
    assert proposal.multi_step_plan is not None
    assert proposal.multi_step_plan.total_steps == 3
    assert proposal.multi_step_plan.steps[0].action == RecoveryActionType.DELAYED_RETRY


def test_orchestrator_routes_to_overdue_invoice_agent(base_context, base_predictions, base_opportunity):
    """Test that INVOICE_OVERDUE routes to OverdueReceivableAgent."""
    base_context.current_event.event_type = EventType.INVOICE_OVERDUE
    
    proposal = orchestrator.dispatch(base_context, base_predictions, base_opportunity)
    
    assert proposal.agent_type == AgentType.OVERDUE_RECEIVABLE
    assert proposal.selected_action == RecoveryActionType.PROGRESSIVE_FOLLOWUP
    assert proposal.multi_step_plan is not None
    assert proposal.communication is not None


def test_overdue_invoice_escalates_high_value(base_context, base_predictions, base_opportunity):
    """Test that high value overdue invoices are escalated to human."""
    base_context.current_event.event_type = EventType.INVOICE_OVERDUE
    base_context.revenue_at_risk = 150000.0  # Above 100k threshold
    
    proposal = orchestrator.dispatch(base_context, base_predictions, base_opportunity)
    
    assert proposal.agent_type == AgentType.OVERDUE_RECEIVABLE
    assert proposal.selected_action == RecoveryActionType.ESCALATE_TO_HUMAN
    assert proposal.requires_human_review is True


def test_payment_failure_agent_attempt_tiers(base_context, base_predictions, base_opportunity):
    """Test that PaymentFailureAgent adapts strategy dynamically across attempts 0, 2, and 3."""
    # Attempt 0: Delayed retry for transient timeout
    base_context.customer_state.total_recovery_attempts = 0
    base_context.history_summary.previous_recovery_attempts = 0
    prop_0 = orchestrator.dispatch(base_context, base_predictions, base_opportunity)
    assert prop_0.selected_action in [RecoveryActionType.DELAYED_RETRY, RecoveryActionType.IMMEDIATE_RETRY]

    # Attempt 2: Channel switch to personalized messaging (WhatsApp)
    base_context.customer_state.total_recovery_attempts = 2
    base_context.history_summary.previous_recovery_attempts = 2
    prop_2 = orchestrator.dispatch(base_context, base_predictions, base_opportunity)
    assert prop_2.selected_action == RecoveryActionType.SEND_PERSONALIZED_MESSAGE
    assert prop_2.communication is not None
    assert prop_2.communication.channel == CommunicationChannel.WHATSAPP

    # Attempt 3: Exhausted attempts on high value -> Escalate to human
    base_context.customer_state.total_recovery_attempts = 3
    base_context.history_summary.previous_recovery_attempts = 3
    base_context.revenue_at_risk = 12000.0
    prop_3 = orchestrator.dispatch(base_context, base_predictions, base_opportunity)
    assert prop_3.selected_action == RecoveryActionType.ESCALATE_TO_HUMAN
    assert prop_3.requires_human_review is True


def test_checkout_abandonment_agent_anti_fatigue(base_context, base_predictions, base_opportunity):
    """Test that CheckoutAbandonmentAgent stops outreach after 2 failed attempts to prevent fatigue."""
    base_context.current_event.event_type = EventType.CHECKOUT_ABANDONED
    base_context.customer_state.total_recovery_attempts = 2
    base_context.history_summary.previous_recovery_attempts = 2
    
    proposal = orchestrator.dispatch(base_context, base_predictions, base_opportunity)
    assert proposal.agent_type == AgentType.CHECKOUT_ABANDONMENT
    assert proposal.selected_action == RecoveryActionType.STOP


def test_subscription_agent_imminent_cancellation(base_context, base_predictions, base_opportunity):
    """Test that SubscriptionRecoveryAgent escalates at attempt 3 to prevent cancellation."""
    base_context.current_event.event_type = EventType.SUBSCRIPTION_PAYMENT_FAILED
    base_context.customer_state.total_recovery_attempts = 3
    base_context.history_summary.previous_recovery_attempts = 3
    base_context.revenue_at_risk = 2499.0
    
    proposal = orchestrator.dispatch(base_context, base_predictions, base_opportunity)
    assert proposal.agent_type == AgentType.SUBSCRIPTION_RECOVERY
    assert proposal.selected_action == RecoveryActionType.ESCALATE_TO_HUMAN
    assert proposal.requires_human_review is True

