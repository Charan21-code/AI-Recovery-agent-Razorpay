"""
Unit tests for Feature Engine and Degradation Detector.
"""

from datetime import datetime, timezone
import numpy as np
import pytest
from backend.core.constants import Environment, EventType, FailureCategory
from backend.db.init_db import drop_sync_db, init_sync_db
from backend.db.session import SyncSessionLocal
from backend.schemas.events import NormalizedEvent
from backend.services.context.context_builder import context_builder
from backend.services.features.degradation_detector import degradation_detector
from backend.services.features.feature_engine import feature_engine
from backend.services.state.state_store import state_store


@pytest.fixture(autouse=True)
def setup_db():
    init_sync_db()
    yield
    drop_sync_db()


def test_feature_extraction_and_vector_alignment():
    """Verify feature dictionary and vector extraction from DecisionContext."""
    with SyncSessionLocal() as session:
        # Create event
        event = NormalizedEvent(
            event_id="evt_feat_001",
            customer_id="cust_feat_101",
            event_type=EventType.PAYMENT_FAILED,
            amount=2999.0,
            payment_method="upi",
            failure_code="GATEWAY_TIMEOUT",
            failure_category=FailureCategory.TRANSIENT_BANK_TIMEOUT,
            timestamp=datetime(2026, 8, 30, 14, 30, 0, tzinfo=timezone.utc),
        )
        state_store.record_normalized_event(session, event)

        ctx = context_builder.build_context(session, event)
        features = feature_engine.extract_features(ctx)

        # Assert feature contents
        assert features["revenue_at_risk"] == 2999.0
        assert features["hour_of_day"] == 14.0
        assert features["day_of_week"] == 6.0  # Sunday
        assert features["failure_category_code"] == 1.0  # TRANSIENT_BANK_TIMEOUT
        assert features["payment_method_code"] == 1.0   # UPI

        # Assert vector
        vec = feature_engine.extract_feature_vector(ctx)
        assert isinstance(vec, np.ndarray)
        assert len(vec) == len(feature_engine.FEATURE_NAMES)
        assert not np.isnan(vec).any()
        assert not np.isinf(vec).any()


def test_degradation_detector_logic():
    """Verify merchant payment system degradation detector."""
    with SyncSessionLocal() as session:
        base_time = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
        merchant_id = "mer_degrade_test"

        # Create 8 failed events and 2 success events on UPI (80% failure rate)
        for i in range(8):
            ev_fail = NormalizedEvent(
                event_id=f"evt_fail_{i}",
                merchant_id=merchant_id,
                customer_id=f"cust_{i}",
                event_type=EventType.PAYMENT_FAILED,
                amount=1000.0,
                payment_method="upi",
                timestamp=base_time,
            )
            state_store.record_normalized_event(session, ev_fail)

        for j in range(2):
            ev_succ = NormalizedEvent(
                event_id=f"evt_succ_{j}",
                merchant_id=merchant_id,
                customer_id=f"cust_succ_{j}",
                event_type=EventType.PAYMENT_SUCCESS,
                amount=1000.0,
                payment_method="upi",
                timestamp=base_time,
            )
            state_store.record_normalized_event(session, ev_succ)

        is_deg, factor, rates = degradation_detector.evaluate_merchant_status(
            session=session,
            merchant_id=merchant_id,
            as_of_timestamp=base_time,
            window_minutes=60,
        )

        assert is_deg
        assert factor >= 2.5
        assert rates["upi"] == 0.80
