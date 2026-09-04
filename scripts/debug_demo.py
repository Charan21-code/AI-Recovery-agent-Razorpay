import sys
import os
import json
from datetime import datetime, timezone
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.normalization.normalizer import normalize_razorpay_event
from backend.services.ml.predictor import recovery_predictor
from backend.schemas.context import DecisionContext, CustomerProfile, CustomerState, CustomerHistorySummary, MerchantPolicyContext

raw_payload = {
    "id": "evt_sim_123",
    "created_at": int(datetime.now().timestamp()),
    "attempt_count": 1,
    "event": "payment.failed",
    "payload": {
        "payment": {
            "entity": {
                "id": "pay_test_123",
                "amount": 499900,
                "currency": "INR",
                "method": "upi",
                "error_code": "GATEWAY_TIMEOUT",
                "error_description": "Bank Timeout / Server Busy",
                "contact": "+919876543210",
                "email": "test@example.com"
            }
        }
    }
}

normalized_event = normalize_razorpay_event(raw_payload)
print(f"Normalized Amount: {normalized_event.amount}")
print(f"Failure Category: {normalized_event.failure_category.value}")

context = DecisionContext(
    context_id=f"ctx_{normalized_event.event_id}",
    as_of_timestamp=datetime.now(timezone.utc),
    current_event=normalized_event,
    customer_profile=CustomerProfile(
        customer_id=normalized_event.customer_id or "cust_default",
        name="Test Customer",
        is_vip=False,
        opted_out_of_outreach=False
    ),
    customer_state=CustomerState(
        customer_id=normalized_event.customer_id or "cust_default",
        total_transactions=10,
        successful_transactions=8,
        failed_transactions=2,
        success_rate=0.8,
        total_recovery_attempts=0,
        consecutive_failures_count=0,
        recent_intervention_count=0,
        intervention_fatigue_score=0.0,
        estimated_clv=50000.0,
    ),
    history_summary=CustomerHistorySummary(
        total_transactions=10,
        successful_transactions=8,
        failed_transactions=2,
        success_rate=0.8,
        previous_recovery_attempts=0,
        consecutive_failures_count=0,
        intervention_fatigue_score=0.0,
        historical_recovery_rate=0.0
    ),
    policy_context=MerchantPolicyContext(
        max_automated_interventions=3,
        min_confidence_threshold=0.6,
        human_escalation_after_attempts=3
    ),
    revenue_at_risk=normalized_event.amount,
    is_merchant_system_degraded=False
)

preds = recovery_predictor.predict_actions(context)
print(f"Best Action: {preds.best_candidate_action}")
