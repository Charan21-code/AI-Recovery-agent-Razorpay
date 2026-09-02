"""
Unit tests for Predictive Intelligence Layer (ML Models, Scorer, Timing, Trainer).
"""

from datetime import datetime, timezone
import numpy as np
import pytest
from backend.core.constants import Environment, EventType, FailureCategory, RecoveryActionType
from backend.db.init_db import drop_sync_db, init_sync_db
from backend.db.session import SyncSessionLocal
from backend.schemas.events import NormalizedEvent
from backend.services.context.context_builder import context_builder
from backend.services.ml.opportunity_scorer import opportunity_scorer
from backend.services.ml.predictor import recovery_predictor
from backend.services.ml.timing_optimizer import timing_optimizer
from backend.services.ml.trainer import ml_trainer
from backend.services.state.state_store import state_store


@pytest.fixture(autouse=True)
def setup_db():
    init_sync_db()
    yield
    drop_sync_db()


def test_recovery_predictor_inference():
    """Verify predictive model generates valid probabilities, expected values, and action rankings."""
    with SyncSessionLocal() as session:
        event = NormalizedEvent(
            event_id="evt_pred_001",
            customer_id="cust_pred_101",
            event_type=EventType.PAYMENT_FAILED,
            amount=4999.0,
            payment_method="upi",
            failure_code="BANK_TIMEOUT",
            failure_category=FailureCategory.TRANSIENT_BANK_TIMEOUT,
        )
        state_store.record_normalized_event(session, event)
        ctx = context_builder.build_context(session, event)

        predictions = recovery_predictor.predict_actions(ctx)

        assert 0.0 <= predictions.overall_recovery_propensity <= 1.0
        assert predictions.best_expected_value > 0.0
        assert predictions.best_candidate_action in [RecoveryActionType.DELAYED_RETRY, RecoveryActionType.IMMEDIATE_RETRY]
        assert len(predictions.action_predictions) >= 8

        # Delayed retry for bank timeout should have higher probability than immediate
        delayed = predictions.action_predictions[RecoveryActionType.DELAYED_RETRY.value]
        assert delayed.recovery_probability > 0.5
        assert delayed.expected_recovery_value == round(4999.0 * delayed.recovery_probability, 2)


def test_opportunity_scorer_ranking():
    """Verify Opportunity Scorer prioritization and ordering."""
    with SyncSessionLocal() as session:
        # High value event
        e_high = NormalizedEvent(
            event_id="evt_high",
            customer_id="cust_high",
            event_type=EventType.PAYMENT_FAILED,
            amount=25000.0,
            payment_method="card",
            failure_category=FailureCategory.TRANSIENT_BANK_TIMEOUT,
        )
        # Low value event
        e_low = NormalizedEvent(
            event_id="evt_low",
            customer_id="cust_low",
            event_type=EventType.PAYMENT_FAILED,
            amount=499.0,
            payment_method="upi",
            failure_category=FailureCategory.INACTIVITY_DROPOFF,
        )
        state_store.record_normalized_event(session, e_high)
        state_store.record_normalized_event(session, e_low)

        ctx_high = context_builder.build_context(session, e_high)
        ctx_low = context_builder.build_context(session, e_low)

        preds_high = recovery_predictor.predict_actions(ctx_high)
        preds_low = recovery_predictor.predict_actions(ctx_low)

        opp_high = opportunity_scorer.score_opportunity(ctx_high, preds_high)
        opp_low = opportunity_scorer.score_opportunity(ctx_low, preds_low)

        assert opp_high.priority_level in ["CRITICAL", "HIGH"]
        assert opp_low.priority_level in ["LOW", "MEDIUM"]

        ranked = opportunity_scorer.rank_opportunities([opp_low, opp_high])
        assert ranked[0].event_id == "evt_high"
        assert ranked[1].event_id == "evt_low"


def test_timing_optimizer_predictions():
    """Verify timing delay recommendations per failure type."""
    with SyncSessionLocal() as session:
        event_timeout = NormalizedEvent(
            event_id="evt_t1",
            customer_id="cust_t1",
            event_type=EventType.PAYMENT_FAILED,
            amount=1000.0,
            failure_category=FailureCategory.TRANSIENT_BANK_TIMEOUT,
        )
        ctx_timeout = context_builder.build_context(session, event_timeout)
        assert timing_optimizer.predict_optimal_delay(ctx_timeout) == 30

        event_funds = NormalizedEvent(
            event_id="evt_t2",
            customer_id="cust_t2",
            event_type=EventType.PAYMENT_FAILED,
            amount=1000.0,
            failure_category=FailureCategory.INSUFFICIENT_FUNDS,
        )
        ctx_funds = context_builder.build_context(session, event_funds)
        assert timing_optimizer.predict_optimal_delay(ctx_funds) >= 720


def test_ml_trainer_evaluation():
    """Verify offline training and evaluation metrics."""
    np.random.seed(42)
    X = np.random.uniform(0, 1, size=(100, 20))
    y = (X[:, 0] + X[:, 1] > 1.0).astype(int)

    X_train, X_test = X[:80], X[80:]
    y_train, y_test = y[:80], y[80:]

    model, metrics = ml_trainer.train_and_evaluate(X_train, y_train, X_test, y_test)
    assert model is not None
    assert "roc_auc" in metrics
    assert "brier_score" in metrics
    assert 0.0 <= metrics["brier_score"] <= 1.0
