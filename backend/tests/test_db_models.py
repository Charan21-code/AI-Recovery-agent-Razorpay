"""
Integration tests for database ORM models and operations.
"""

from datetime import datetime, timezone
import pytest
from sqlalchemy import select
from backend.core.constants import (
    AgentType,
    Environment,
    EventType,
    FailureCategory,
    PolicyVerdictStatus,
    RecoveryActionType,
)
from backend.db.init_db import drop_sync_db, init_sync_db
from backend.db.models import (
    CustomerRecord,
    NormalizedEventRecord,
    OrderRecord,
    PaymentAttemptRecord,
    PolicyCheckRecord,
    RawEventRecord,
    RecoveryDecisionRecord,
)
from backend.db.session import SyncSessionLocal


@pytest.fixture(autouse=True)
def setup_database():
    """Setup and teardown tables for each test."""
    init_sync_db()
    yield
    drop_sync_db()


def test_customer_and_order_relationships():
    """Test customer creation, order tracking, and payment attempt relationship."""
    with SyncSessionLocal() as session:
        # Create Customer
        cust = CustomerRecord(
            customer_id="cust_test_101",
            name="Rahul Sharma",
            email="rahul@example.com",
            phone="+919876543210",
            is_vip=True,
        )
        session.add(cust)

        # Create Order
        order = OrderRecord(
            order_id="order_test_101",
            customer_id="cust_test_101",
            amount=4999.0,
            currency="INR",
            status="attempted",
            attempts_count=2,
        )
        session.add(order)

        # Create Payment Attempts
        pay1 = PaymentAttemptRecord(
            payment_id="pay_test_001",
            order_id="order_test_101",
            customer_id="cust_test_101",
            amount=4999.0,
            currency="INR",
            status="failed",
            payment_method="card",
            failure_code="GATEWAY_TIMEOUT",
            attempt_number=1,
        )
        pay2 = PaymentAttemptRecord(
            payment_id="pay_test_002",
            order_id="order_test_101",
            customer_id="cust_test_101",
            amount=4999.0,
            currency="INR",
            status="captured",
            payment_method="upi",
            attempt_number=2,
        )
        session.add_all([pay1, pay2])
        session.commit()

        # Query Order and Verify Relationship
        stmt = select(OrderRecord).where(OrderRecord.order_id == "order_test_101")
        fetched_order = session.execute(stmt).scalar_one()

        assert fetched_order is not None
        assert fetched_order.amount == 4999.0
        assert len(fetched_order.payment_attempts) == 2
        assert fetched_order.payment_attempts[0].payment_id == "pay_test_001"
        assert fetched_order.payment_attempts[1].status == "captured"


def test_agent_decision_and_policy_check_persistence():
    """Test saving recovery decision and deterministic policy check."""
    with SyncSessionLocal() as session:
        decision = RecoveryDecisionRecord(
            decision_id="dec_001",
            event_id="evt_001",
            customer_id="cust_test_101",
            agent_type=AgentType.PAYMENT_FAILURE.value,
            selected_action=RecoveryActionType.DELAYED_RETRY.value,
            confidence=0.89,
            reasoning="Customer has high recovery propensity for delayed retries.",
            evidence_citations_json=["7 of 9 historical payments succeeded"],
        )

        policy_check = PolicyCheckRecord(
            verdict_id="ver_001",
            decision_id="dec_001",
            proposal_action=RecoveryActionType.DELAYED_RETRY.value,
            approved_action=RecoveryActionType.DELAYED_RETRY.value,
            status=PolicyVerdictStatus.APPROVED.value,
            rules_checked_json=[
                {"rule": "max_retries", "passed": True, "details": "1/3 attempts used"},
                {"rule": "min_confidence", "passed": True, "details": "0.89 >= 0.70"},
            ],
        )

        session.add_all([decision, policy_check])
        session.commit()

        # Query and Verify
        stmt = select(RecoveryDecisionRecord).where(RecoveryDecisionRecord.decision_id == "dec_001")
        fetched_dec = session.execute(stmt).scalar_one()
        assert fetched_dec.agent_type == AgentType.PAYMENT_FAILURE.value
        assert fetched_dec.confidence == 0.89

        stmt_pol = select(PolicyCheckRecord).where(PolicyCheckRecord.verdict_id == "ver_001")
        fetched_pol = session.execute(stmt_pol).scalar_one()
        assert fetched_pol.status == PolicyVerdictStatus.APPROVED.value
