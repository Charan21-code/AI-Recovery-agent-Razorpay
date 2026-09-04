import sys
import os
import json
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from datetime import datetime, timezone
from backend.schemas.context import DecisionContext, CustomerHistorySummary, MerchantPolicyContext
from backend.schemas.customer import CustomerProfile, CustomerState
from backend.services.normalization.normalizer import normalize_razorpay_event
from backend.services.ml.predictor import recovery_predictor
from backend.services.ml.opportunity_scorer import opportunity_scorer
from backend.services.agents.orchestrator import orchestrator

for previous_attempts in [0, 1, 2, 3]:
    raw_payload = {
        "id": "evt_sim_123",
        "created_at": int(datetime.now().timestamp()),
        "attempt_count": previous_attempts + 1,
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
                }
            }
        }
    }

    normalized_event = normalize_razorpay_event(raw_payload)
    
    context = DecisionContext(
        context_id="test",
        as_of_timestamp=datetime.now(timezone.utc),
        current_event=normalized_event,
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
            failed_transactions=2 + previous_attempts,
            success_rate=0.8,
            total_recovery_attempts=previous_attempts,
            consecutive_failures_count=previous_attempts,
            recent_intervention_count=previous_attempts,
            intervention_fatigue_score=previous_attempts * 0.22,
            estimated_clv=50000.0,
        ),
        history_summary=CustomerHistorySummary(
            total_transactions=10,
            successful_transactions=8,
            failed_transactions=2 + previous_attempts,
            success_rate=0.8,
            previous_recovery_attempts=previous_attempts,
            consecutive_failures_count=previous_attempts,
            intervention_fatigue_score=previous_attempts * 0.22,
            historical_recovery_rate=0.5 if previous_attempts > 0 else 0.0
        ),
        policy_context=MerchantPolicyContext(),
        revenue_at_risk=4999.0,
        is_merchant_system_degraded=False
    )
    
    predictions = recovery_predictor.predict_actions(context)
    opportunity = opportunity_scorer.score_opportunity(context, predictions)
    proposal = orchestrator.dispatch(context, predictions, opportunity)
    
    print(f"Attempts: {previous_attempts} | ML Action: {predictions.best_candidate_action.value} | Agent Action: {proposal.selected_action.value} | Reasoning: {proposal.reasoning}")
