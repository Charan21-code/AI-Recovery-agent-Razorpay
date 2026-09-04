"""
Unit tests for Phase 9: Outcome Engine (RevenueCalculator, AuditTrailService, OutcomeProcessor).
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.core.constants import (
    CommunicationChannel,
    Environment,
    EventType,
    FailureCategory,
    RecoveryActionType,
)
from backend.db.base import Base
from backend.schemas.events import NormalizedEvent
from backend.schemas.outcomes import RecoveryOutcome
from backend.services.outcomes.audit_trail import AuditTrailService
from backend.services.outcomes.outcome_processor import OutcomeProcessor
from backend.services.outcomes.revenue_calculator import RevenueCalculator
from backend.services.state.state_store import StateStore


@pytest.fixture
def db_session():
    """In-memory SQLite session for isolated outcome tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_revenue_calculator_costs():
    calc = RevenueCalculator()
    assert calc.get_intervention_cost(RecoveryActionType.IMMEDIATE_RETRY) == 0.00
    assert calc.get_intervention_cost(RecoveryActionType.DELAYED_RETRY) == 0.00
    assert calc.get_intervention_cost(RecoveryActionType.START_VOICE_RECOVERY) == 2.00
    assert calc.get_intervention_cost(RecoveryActionType.ESCALATE_TO_HUMAN) == 15.00
    assert calc.get_intervention_cost(RecoveryActionType.SEND_PERSONALIZED_MESSAGE, CommunicationChannel.WHATSAPP) == 0.50
    assert calc.get_intervention_cost(RecoveryActionType.SEND_PAYMENT_REMINDER, CommunicationChannel.SMS) == 0.15


def test_revenue_calculator_net_reward():
    calc = RevenueCalculator()

    # Success case: Rs. 5,000 recovered via WhatsApp with 0.2 fatigue
    reward_success = calc.calculate_reward(
        recovered_amount=5000.0,
        is_success=True,
        action=RecoveryActionType.SEND_PERSONALIZED_MESSAGE,
        channel=CommunicationChannel.WHATSAPP,
        intervention_fatigue_score=0.2,
    )
    assert reward_success.recovered_revenue == 5000.0
    assert reward_success.intervention_cost == 0.50
    assert reward_success.customer_friction_penalty == 1.00  # 0.2 * 5.0
    assert reward_success.net_reward == 4998.50

    # Failure case: Rs. 0 recovered via Voice AI
    reward_failure = calc.calculate_reward(
        recovered_amount=0.0,
        is_success=False,
        action=RecoveryActionType.START_VOICE_RECOVERY,
        channel=CommunicationChannel.VOICE,
    )
    assert reward_failure.recovered_revenue == 0.0
    assert reward_failure.intervention_cost == 2.00
    assert reward_failure.net_reward == -2.00


def test_audit_trail_service(db_session: Session):
    audit_svc = AuditTrailService()

    audit_svc.record_entry(
        session=db_session,
        event_id="evt_audit_001",
        stage="INGESTION",
        actor="EventIngestion",
        action="NORMALIZE_EVENT",
        details={"amount": 4999.0},
    )

    audit_svc.record_entry(
        session=db_session,
        event_id="evt_audit_001",
        stage="POLICY_CHECK",
        actor="PolicyEngine",
        action="APPROVED",
        details={"verdict": "APPROVED"},
    )

    trail = audit_svc.get_trail_for_event(db_session, "evt_audit_001")
    assert len(trail) == 2
    assert trail[0].stage == "INGESTION"
    assert trail[1].stage == "POLICY_CHECK"

    timeline = audit_svc.format_readable_timeline(db_session, "evt_audit_001")
    assert len(timeline) == 2
    assert timeline[0]["actor"] == "EventIngestion"
    assert timeline[1]["action"] == "APPROVED"


def test_outcome_processor_recovery_success(db_session: Session):
    processor = OutcomeProcessor()
    store = StateStore()

    customer_id = "cust_outcome_test_1"
    store.get_or_create_customer_profile(db_session, customer_id=customer_id, name="Alice Doe")

    # Initial failed event
    initial_event = NormalizedEvent(
        event_id="evt_init_fail",
        source="razorpay_webhook",
        environment=Environment.TEST,
        event_type=EventType.PAYMENT_FAILED,
        timestamp=datetime.now(timezone.utc),
        merchant_id="mer_default",
        customer_id=customer_id,
        amount=4999.0,
        currency="INR",
        failure_category=FailureCategory.TRANSIENT_BANK_TIMEOUT,
    )
    store.record_normalized_event(db_session, initial_event)

    outcome = RecoveryOutcome(
        outcome_id="out_test_001",
        execution_id="exec_test_001",
        event_id="evt_init_fail",
        customer_id=customer_id,
        outcome_type=EventType.RECOVERY_SUCCESS,
        recovered_amount=4999.0,
        currency="INR",
        time_to_recovery_seconds=120.0,
        is_success=True,
    )

    summary, reward = processor.process_outcome(
        session=db_session,
        outcome=outcome,
        action_executed=RecoveryActionType.DELAYED_RETRY,
    )

    assert summary.customer_id == customer_id
    assert summary.updated_total_revenue == 4999.0
    assert reward.recovered_revenue == 4999.0
    assert reward.net_reward == 4999.0  # Retry cost is 0.00


def test_outcome_processor_recovery_failure(db_session: Session):
    processor = OutcomeProcessor()
    store = StateStore()

    customer_id = "cust_outcome_test_2"
    store.get_or_create_customer_profile(db_session, customer_id=customer_id, name="Bob Smith")

    outcome = RecoveryOutcome(
        outcome_id="out_test_002",
        execution_id="exec_test_002",
        event_id="evt_fail_002",
        customer_id=customer_id,
        outcome_type=EventType.RECOVERY_FAILED,
        recovered_amount=0.0,
        currency="INR",
        is_success=False,
    )

    summary, reward = processor.process_outcome(
        session=db_session,
        outcome=outcome,
        action_executed=RecoveryActionType.START_VOICE_RECOVERY,
    )

    assert summary.customer_id == customer_id
    assert reward.recovered_revenue == 0.0
    assert reward.intervention_cost == 2.00
    assert reward.net_reward == -2.00
