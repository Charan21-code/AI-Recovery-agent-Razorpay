"""
Unit and integration tests for Phase 10: Feedback System & Contextual Bandit Tracker.
"""

from datetime import datetime, timezone
import numpy as np
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.constants import (
    AgentType,
    CommunicationChannel,
    Environment,
    EventType,
    FailureCategory,
    RecoveryActionType,
)
from backend.db.base import Base
from backend.schemas.context import CustomerHistorySummary, DecisionContext, MerchantPolicyContext
from backend.schemas.customer import CustomerProfile, CustomerState
from backend.schemas.events import NormalizedEvent
from backend.schemas.feedback import RewardBreakdown
from backend.schemas.outcomes import RecoveryOutcome
from backend.services.feedback.bandit_learner import ContextualBanditTracker
from backend.services.feedback.feedback_store import FeedbackStore
from backend.services.ml.trainer import MLTrainer
from backend.services.outcomes.outcome_processor import OutcomeProcessor
from backend.services.state.state_store import StateStore


@pytest.fixture
def db_session():
    """In-memory SQLite session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def sample_context():
    norm_ev = NormalizedEvent(
        event_id="evt_fb_001",
        source="razorpay_webhook",
        environment=Environment.TEST,
        event_type=EventType.PAYMENT_FAILED,
        timestamp=datetime.now(timezone.utc),
        merchant_id="mer_default",
        customer_id="cust_fb_001",
        amount=4999.0,
        currency="INR",
        failure_category=FailureCategory.TRANSIENT_BANK_TIMEOUT,
        payment_method="upi",
    )
    return DecisionContext(
        context_id="ctx_fb_001",
        as_of_timestamp=datetime.now(timezone.utc),
        current_event=norm_ev,
        customer_profile=CustomerProfile(
            customer_id="cust_fb_001",
            name="Alice Doe",
        ),
        customer_state=CustomerState(
            customer_id="cust_fb_001",
            total_transactions=10,
            successful_transactions=8,
            failed_transactions=2,
            success_rate=0.8,
            total_revenue_generated=40000.0,
            average_transaction_value=5000.0,
            total_recovery_attempts=1,
            successful_recoveries=1,
            historical_recovery_rate=1.0,
            intervention_fatigue_score=0.2,
        ),
        history_summary=CustomerHistorySummary(
            total_transactions=10,
            successful_transactions=8,
            failed_transactions=2,
            success_rate=0.8,
            previous_recovery_attempts=1,
            historical_recovery_rate=1.0,
            intervention_fatigue_score=0.2,
        ),
        policy_context=MerchantPolicyContext(),
        revenue_at_risk=4999.0,
    )


def test_record_learning_event(db_session: Session, sample_context: DecisionContext):
    store = FeedbackStore()

    outcome = RecoveryOutcome(
        outcome_id="out_fb_001",
        execution_id="exec_fb_001",
        event_id="evt_fb_001",
        customer_id="cust_fb_001",
        outcome_type=EventType.RECOVERY_SUCCESS,
        recovered_amount=4999.0,
        currency="INR",
        is_success=True,
    )

    reward = RewardBreakdown.calculate(
        recovered_revenue=4999.0,
        intervention_cost=0.50,
        customer_friction_penalty=1.00,
    )

    rec = store.record_learning_event(
        session=db_session,
        context=sample_context,
        action_taken=RecoveryActionType.SEND_PERSONALIZED_MESSAGE,
        outcome=outcome,
        reward=reward,
        agent_type=AgentType.PAYMENT_FAILURE,
    )

    assert rec.feedback_id.startswith("fb_")
    assert rec.action_taken == RecoveryActionType.SEND_PERSONALIZED_MESSAGE.value
    assert rec.outcome_status == EventType.RECOVERY_SUCCESS.value
    assert rec.recovered_revenue == 4999.0
    assert rec.net_reward == 4997.50
    assert "historical_success_rate" in rec.context_vector_json
    assert rec.context_vector_json["historical_success_rate"] == 0.8


def test_training_dataset_export(db_session: Session, sample_context: DecisionContext):
    store = FeedbackStore()

    # Record 3 events: 2 successes, 1 failure
    for i in range(3):
        is_success = (i % 2 == 0)
        outcome = RecoveryOutcome(
            outcome_id=f"out_exp_{i}",
            execution_id=f"exec_exp_{i}",
            event_id=f"evt_exp_{i}",
            customer_id="cust_fb_001",
            outcome_type=EventType.RECOVERY_SUCCESS if is_success else EventType.RECOVERY_FAILED,
            recovered_amount=4999.0 if is_success else 0.0,
            currency="INR",
            is_success=is_success,
        )
        reward = RewardBreakdown.calculate(
            recovered_revenue=4999.0 if is_success else 0.0,
            intervention_cost=0.50,
        )
        store.record_learning_event(
            session=db_session,
            context=sample_context,
            action_taken=RecoveryActionType.DELAYED_RETRY,
            outcome=outcome,
            reward=reward,
        )

    X, y, rewards = store.get_training_dataset(db_session)
    assert X.shape == (3, 20)
    assert y.shape == (3,)
    assert rewards.shape == (3,)
    assert list(y) == [1, 0, 1]


def test_bandit_tracker_and_ucb(db_session: Session, sample_context: DecisionContext):
    store = FeedbackStore()
    tracker = ContextualBanditTracker(exploration_constant=1.0)

    # Action 1: DELAYED_RETRY pulled twice, 2 successes
    for i in range(2):
        outcome = RecoveryOutcome(
            outcome_id=f"out_b1_{i}",
            execution_id=f"exec_b1_{i}",
            event_id=f"evt_b1_{i}",
            customer_id="cust_fb_001",
            outcome_type=EventType.RECOVERY_SUCCESS,
            recovered_amount=1000.0,
            currency="INR",
            is_success=True,
        )
        reward = RewardBreakdown.calculate(recovered_revenue=1000.0, intervention_cost=0.0)
        store.record_learning_event(db_session, sample_context, RecoveryActionType.DELAYED_RETRY, outcome, reward)

    # Action 2: START_VOICE_RECOVERY pulled once, 1 failure
    outcome_fail = RecoveryOutcome(
        outcome_id="out_b2_0",
        execution_id="exec_b2_0",
        event_id="evt_b2_0",
        customer_id="cust_fb_001",
        outcome_type=EventType.RECOVERY_FAILED,
        recovered_amount=0.0,
        currency="INR",
        is_success=False,
    )
    reward_fail = RewardBreakdown.calculate(recovered_revenue=0.0, intervention_cost=2.0)
    store.record_learning_event(db_session, sample_context, RecoveryActionType.START_VOICE_RECOVERY, outcome_fail, reward_fail)

    stats = tracker.compute_arm_statistics(db_session)
    assert stats[RecoveryActionType.DELAYED_RETRY.value]["pulls"] == 2
    assert stats[RecoveryActionType.DELAYED_RETRY.value]["conversions"] == 2
    assert stats[RecoveryActionType.DELAYED_RETRY.value]["conversion_rate"] == 1.0
    assert stats[RecoveryActionType.DELAYED_RETRY.value]["mean_reward"] == 1000.0

    assert stats[RecoveryActionType.START_VOICE_RECOVERY.value]["pulls"] == 1
    assert stats[RecoveryActionType.START_VOICE_RECOVERY.value]["conversions"] == 0
    assert stats[RecoveryActionType.START_VOICE_RECOVERY.value]["mean_reward"] == -2.0

    # Test allowed actions ranking
    allowed = [RecoveryActionType.DELAYED_RETRY, RecoveryActionType.START_VOICE_RECOVERY]
    ranked = tracker.rank_allowed_actions(db_session, allowed)
    assert len(ranked) == 2
    assert ranked[0]["action"] == RecoveryActionType.DELAYED_RETRY.value


def test_outcome_processor_auto_records_feedback(db_session: Session, sample_context: DecisionContext):
    processor = OutcomeProcessor()
    store_state = StateStore()
    feedback_repo = FeedbackStore()

    store_state.get_or_create_customer_profile(db_session, customer_id="cust_fb_001")

    outcome = RecoveryOutcome(
        outcome_id="out_auto_001",
        execution_id="exec_auto_001",
        event_id="evt_fb_001",
        customer_id="cust_fb_001",
        outcome_type=EventType.RECOVERY_SUCCESS,
        recovered_amount=4999.0,
        currency="INR",
        is_success=True,
    )

    summary, reward = processor.process_outcome(
        session=db_session,
        outcome=outcome,
        action_executed=RecoveryActionType.DELAYED_RETRY,
        context=sample_context,
        agent_type=AgentType.PAYMENT_FAILURE,
    )

    records = feedback_repo.get_feedback_records(db_session)
    assert len(records) == 1
    assert records[0].outcome_status == EventType.RECOVERY_SUCCESS.value
    assert records[0].recovered_revenue == 4999.0
