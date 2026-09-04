"""
Feature Engineering Service: Extracts decision-relevant signals and feature vectors from DecisionContext.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List
import numpy as np
from backend.core.constants import FailureCategory
from backend.core.logging import get_logger
from backend.schemas.context import DecisionContext

logger = get_logger("feature_engine")

FAILURE_CATEGORY_MAP = {
    FailureCategory.TRANSIENT_BANK_TIMEOUT.value: 1,
    FailureCategory.INSUFFICIENT_FUNDS.value: 2,
    FailureCategory.AUTHENTICATION_FAILED.value: 3,
    FailureCategory.EXPIRED_OR_BLOCKED_CARD.value: 4,
    FailureCategory.MANDATE_REJECTED.value: 5,
    FailureCategory.USER_CANCELLED.value: 6,
    FailureCategory.INACTIVITY_DROPOFF.value: 7,
    FailureCategory.UNKNOWN.value: 0,
}

PAYMENT_METHOD_MAP = {
    "upi": 1,
    "card": 2,
    "netbanking": 3,
    "wallet": 4,
    "emi": 5,
    "unknown": 0,
}


class FeatureEngine:
    """Extracts numerical & categorical features from DecisionContext."""

    FEATURE_NAMES = [
        "historical_success_rate",
        "total_transactions",
        "total_revenue_generated",
        "average_transaction_value",
        "historical_recovery_rate",
        "total_recovery_attempts",
        "consecutive_failures_count",
        "intervention_fatigue_score",
        "recent_intervention_count",
        "revenue_at_risk",
        "estimated_clv_at_risk",
        "amount_to_avg_ratio",
        "failure_category_code",
        "payment_method_code",
        "attempt_count",
        "hour_of_day",
        "day_of_week",
        "is_merchant_system_degraded",
        "is_vip_customer",
        "is_opted_out",
    ]

    def extract_features(self, context: DecisionContext) -> Dict[str, float]:
        """Extracts a structured feature dictionary from DecisionContext."""
        state = context.customer_state
        profile = context.customer_profile
        event = context.current_event

        # Synchronize and harmonize attempts and fatigue between customer_state and history_summary
        hist = context.history_summary
        attempts = float(max(state.total_recovery_attempts, hist.previous_recovery_attempts))
        consecutive_failures = float(max(state.consecutive_failures_count, hist.consecutive_failures_count, int(attempts)))

        # Dynamic fatigue score derivation if not explicitly stored
        fatigue_score = float(max(state.intervention_fatigue_score, hist.intervention_fatigue_score))
        if fatigue_score == 0.0 and attempts > 0:
            fatigue_score = float(min(1.0, attempts * 0.22))

        recent_interventions = float(max(state.recent_intervention_count, int(attempts)))
        historical_recovery_rate = float(state.historical_recovery_rate if state.historical_recovery_rate > 0 else hist.historical_recovery_rate)

        # Financial ratio
        avg_val = state.average_transaction_value if state.average_transaction_value > 0 else event.amount
        amount_to_avg = round(event.amount / avg_val, 4) if avg_val > 0 else 1.0

        # Temporal signals from event timestamp
        ts = event.timestamp
        hour = float(ts.hour)
        day_of_week = float(ts.weekday())

        # Category encodings
        cat_key = event.failure_category.value if hasattr(event.failure_category, "value") else str(event.failure_category)
        fail_code = float(FAILURE_CATEGORY_MAP.get(cat_key, 0))

        method_str = (event.payment_method or state.preferred_payment_method or "unknown").lower()
        method_code = float(PAYMENT_METHOD_MAP.get(method_str, 0))

        features: Dict[str, float] = {
            "historical_success_rate": float(state.success_rate),
            "total_transactions": float(state.total_transactions),
            "total_revenue_generated": float(state.total_revenue_generated),
            "average_transaction_value": float(state.average_transaction_value),
            "historical_recovery_rate": historical_recovery_rate,
            "total_recovery_attempts": attempts,
            "consecutive_failures_count": consecutive_failures,
            "intervention_fatigue_score": fatigue_score,
            "recent_intervention_count": recent_interventions,
            "revenue_at_risk": float(context.revenue_at_risk),
            "estimated_clv_at_risk": float(context.estimated_clv_at_risk),
            "amount_to_avg_ratio": float(amount_to_avg),
            "failure_category_code": fail_code,
            "payment_method_code": method_code,
            "attempt_count": float(max(event.attempt_count, int(attempts))),
            "hour_of_day": hour,
            "day_of_week": day_of_week,
            "is_merchant_system_degraded": 1.0 if context.is_merchant_system_degraded else 0.0,
            "is_vip_customer": 1.0 if profile.is_vip else 0.0,
            "is_opted_out": 1.0 if profile.opted_out_of_outreach else 0.0,
        }
        return features

    def extract_feature_vector(self, context: DecisionContext) -> np.ndarray:
        """Extracts an ordered 1D NumPy float array aligned with FEATURE_NAMES."""
        features_dict = self.extract_features(context)
        return np.array([features_dict[name] for name in self.FEATURE_NAMES], dtype=np.float32)


feature_engine = FeatureEngine()
