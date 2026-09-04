"""
Tests for LLM Reasoning Engine (Section 69 output contract and Section 61 fallback).
"""

import pytest
from datetime import datetime, timezone
from backend.core.constants import Environment, EventType, FailureCategory, RecoveryActionType
from backend.schemas.customer import CustomerProfile, CustomerState
from backend.schemas.events import NormalizedEvent
from backend.schemas.context import (
    CustomerHistorySummary,
    DecisionContext,
    MerchantPolicyContext,
)
from backend.services.llm.reasoning_engine import llm_reasoning_service


def test_llm_reasoning_deterministic_fallback():
    now = datetime.now(timezone.utc)
    context = DecisionContext(
        context_id="ctx_test_llm_1",
        as_of_timestamp=now,
        current_event=NormalizedEvent(
            event_id="evt_test_1",
            source="razorpay",
            environment=Environment.TEST,
            event_type=EventType.PAYMENT_FAILED,
            timestamp=now,
            merchant_id="mer_test",
            customer_id="cust_test",
            amount=4999.00,
            currency="INR",
            failure_category=FailureCategory.TRANSIENT_BANK_TIMEOUT,
            failure_reason="Gateway timeout after 30 seconds",
            attempt_count=1,
            is_actionable=True,
        ),
        customer_profile=CustomerProfile(
            customer_id="cust_test",
            name="Priya Sharma",
            is_vip=True,
        ),
        customer_state=CustomerState(
            customer_id="cust_test",
            as_of_timestamp=now,
            total_transactions=15,
            successful_transactions=14,
            failed_transactions=1,
            success_rate=0.933,
            total_recovery_attempts=1,
            intervention_fatigue_score=0.12,
        ),
        history_summary=CustomerHistorySummary(
            previous_recovery_attempts=1,
        ),
        policy_context=MerchantPolicyContext(),
        revenue_at_risk=4999.00,
    )

    reasoning = llm_reasoning_service.generate_reasoning(
        context=context,
        recommended_action=RecoveryActionType.DELAYED_RETRY,
        predicted_propensity=0.88,
    )

    # Validate Section 69 Contract
    assert reasoning.action == RecoveryActionType.DELAYED_RETRY
    assert 0.0 <= reasoning.confidence <= 1.0
    assert len(reasoning.evidence) >= 2
    assert "Priya Sharma" in context.customer_profile.name
    assert "transient" in reasoning.reason.lower() or "delayed retry" in reasoning.reason.lower()
