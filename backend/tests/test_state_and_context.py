"""
Tests for Chronological State Store and Temporal Context Builder.
Verifies strict temporal integrity (zero future data leakage).
"""

from datetime import datetime, timedelta, timezone
import pytest
from backend.core.constants import Environment, EventType, FailureCategory
from backend.db.init_db import drop_sync_db, init_sync_db
from backend.db.session import SyncSessionLocal
from backend.schemas.events import NormalizedEvent
from backend.services.context.context_builder import ContextBuilder
from backend.services.state.state_store import StateStore


@pytest.fixture(autouse=True)
def setup_db():
    init_sync_db()
    yield
    drop_sync_db()


def test_chronological_state_evolution_and_no_future_leakage():
    """
    Simulates a stream of events across time T1 to T7:
    T1: Success (₹2,000)
    T2: Success (₹3,000)
    T3: Success (₹2,500)
    T4: Payment Failed (₹4,999) -> Decision point!
    T5: Recovery Attempted
    T6: Recovery Success (₹4,999)
    T7: Payment Failed (₹1,500) -> Second Decision point!

    Verifies:
    1. At T4, state only sees T1, T2, T3 (3 success, 0 failure, 0 recovery attempts, ₹7,500 rev).
    2. At T7, state sees T1-T6 (4 success, 1 failure, 1 recovery attempt, 100% recovery rate, ₹12,499 rev).
    """
    store = StateStore()
    builder = ContextBuilder()
    base_time = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)
    cust_id = "cust_temporal_001"

    with SyncSessionLocal() as session:
        # T1
        e1 = NormalizedEvent(
            event_id="E001",
            customer_id=cust_id,
            event_type=EventType.PAYMENT_SUCCESS,
            amount=2000.0,
            timestamp=base_time + timedelta(minutes=10),
            payment_method="upi",
        )
        # T2
        e2 = NormalizedEvent(
            event_id="E002",
            customer_id=cust_id,
            event_type=EventType.PAYMENT_SUCCESS,
            amount=3000.0,
            timestamp=base_time + timedelta(minutes=20),
            payment_method="upi",
        )
        # T3
        e3 = NormalizedEvent(
            event_id="E003",
            customer_id=cust_id,
            event_type=EventType.PAYMENT_SUCCESS,
            amount=2500.0,
            timestamp=base_time + timedelta(minutes=30),
            payment_method="card",
        )
        # T4: Failed
        e4 = NormalizedEvent(
            event_id="E004",
            customer_id=cust_id,
            event_type=EventType.PAYMENT_FAILED,
            amount=4999.0,
            timestamp=base_time + timedelta(minutes=40),
            payment_method="upi",
            failure_code="BANK_TIMEOUT",
            failure_category=FailureCategory.TRANSIENT_BANK_TIMEOUT,
        )
        # T5: Recovery Attempted
        e5 = NormalizedEvent(
            event_id="R001",
            customer_id=cust_id,
            event_type=EventType.RECOVERY_ATTEMPTED,
            amount=4999.0,
            timestamp=base_time + timedelta(minutes=50),
        )
        # T6: Recovery Success
        e6 = NormalizedEvent(
            event_id="R002",
            customer_id=cust_id,
            event_type=EventType.RECOVERY_SUCCESS,
            amount=4999.0,
            timestamp=base_time + timedelta(minutes=60),
            metadata={"time_to_recovery_minutes": 20.0},
        )
        # T7: Another Failure
        e7 = NormalizedEvent(
            event_id="E007",
            customer_id=cust_id,
            event_type=EventType.PAYMENT_FAILED,
            amount=1500.0,
            timestamp=base_time + timedelta(minutes=120),
            payment_method="card",
            failure_code="INSUFFICIENT_FUNDS",
            failure_category=FailureCategory.INSUFFICIENT_FUNDS,
        )

        # Ingest ALL events E001-E007 into database (simulating a populated event store)
        for event in [e1, e2, e3, e4, e5, e6, e7]:
            store.record_normalized_event(session, event)

        # TEST POINT 1: Build context for E004 at T4 (Minutes=40)
        ctx_t4 = builder.build_context(session, e4)
        state_t4 = ctx_t4.customer_state

        # Assert zero future data leakage at T4
        assert state_t4.total_transactions == 4  # e1, e2, e3, e4
        assert state_t4.successful_transactions == 3
        assert state_t4.failed_transactions == 1
        assert state_t4.success_rate == 0.75
        assert state_t4.total_revenue_generated == 7500.0
        assert state_t4.total_recovery_attempts == 0  # e5 hasn't happened yet!
        assert state_t4.successful_recoveries == 0     # e6 hasn't happened yet!
        assert state_t4.historical_recovery_rate == 0.0

        # TEST POINT 2: Build context for E007 at T7 (Minutes=120)
        ctx_t7 = builder.build_context(session, e7)
        state_t7 = ctx_t7.customer_state

        # At T7, e5 and e6 are now legitimate historical information!
        assert state_t7.total_transactions == 5  # e1, e2, e3, e4, e7
        assert state_t7.successful_transactions == 3
        assert state_t7.total_revenue_generated == 12499.0  # 7500 + 4999 (from R002 recovery)
        assert state_t7.total_recovery_attempts == 1  # R001
        assert state_t7.successful_recoveries == 1    # R002
        assert state_t7.historical_recovery_rate == 1.0
        assert state_t7.average_recovery_time_minutes == 20.0
        assert ctx_t7.revenue_at_risk == 1500.0


def test_order_multi_attempt_lifecycle():
    """Verify order tracks multiple payment attempts."""
    store = StateStore()
    cust_id = "cust_order_test"
    order_id = "ord_multi_101"
    base_time = datetime.now(timezone.utc)

    with SyncSessionLocal() as session:
        # Attempt 1: Failed
        att1 = NormalizedEvent(
            event_id="evt_att_1",
            customer_id=cust_id,
            order_id=order_id,
            payment_id="pay_att_1",
            event_type=EventType.PAYMENT_FAILED,
            amount=3500.0,
            attempt_count=1,
            timestamp=base_time,
        )
        store.record_normalized_event(session, att1)

        # Attempt 2: Success
        att2 = NormalizedEvent(
            event_id="evt_att_2",
            customer_id=cust_id,
            order_id=order_id,
            payment_id="pay_att_2",
            event_type=EventType.PAYMENT_SUCCESS,
            amount=3500.0,
            attempt_count=2,
            timestamp=base_time + timedelta(minutes=5),
        )
        store.record_normalized_event(session, att2)

        # Verify state
        state = store.get_customer_state_as_of(session, cust_id, base_time + timedelta(minutes=10))
        assert state.total_transactions == 2
        assert state.successful_transactions == 1
        assert state.total_revenue_generated == 3500.0
