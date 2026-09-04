import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, timezone
from backend.schemas.context import DecisionContext, CustomerHistorySummary, MerchantPolicyContext
from backend.schemas.customer import CustomerProfile, CustomerState
from backend.schemas.events import NormalizedEvent
from backend.core.constants import EventType, FailureCategory, Environment
from backend.services.ml.predictor import recovery_predictor

event = NormalizedEvent(
    event_id="test",
    source="razorpay",
    environment=Environment.TEST,
    event_type=EventType.PAYMENT_FAILED,
    timestamp=datetime.now(timezone.utc),
    merchant_id="test",
    customer_id="test",
    amount=4999.0,
    currency="INR",
    failure_category=FailureCategory.TRANSIENT_BANK_TIMEOUT,
    attempt_count=4
)

context = DecisionContext(
    context_id="test",
    as_of_timestamp=datetime.now(timezone.utc),
    current_event=event,
    customer_profile=CustomerProfile(
        customer_id="test",
        name="test",
        is_vip=False,
        opted_out_of_outreach=False
    ),
    customer_state=CustomerState(
        customer_id="test",
        total_transactions=10,
        successful_transactions=8,
        failed_transactions=5,
        success_rate=0.8,
        total_recovery_attempts=3,
        consecutive_failures_count=3,
        recent_intervention_count=3,
        intervention_fatigue_score=0.66,
        estimated_clv=50000.0,
    ),
    history_summary=CustomerHistorySummary(
        total_transactions=10,
        successful_transactions=8,
        failed_transactions=5,
        success_rate=0.8,
        previous_recovery_attempts=3,
        consecutive_failures_count=3,
        intervention_fatigue_score=0.66,
        historical_recovery_rate=0.5
    ),
    policy_context=MerchantPolicyContext(),
    revenue_at_risk=4999.0,
    is_merchant_system_degraded=False
)

preds = recovery_predictor.predict_actions(context)
print(f"Overall Propensity: {preds.overall_recovery_propensity}")
print(f"Best Action: {preds.best_candidate_action}")
print(f"Best Expected Value: {preds.best_expected_value}")
for k, v in preds.action_predictions.items():
    print(f"Action: {k} -> Net E[V]: {v.net_expected_value}")
