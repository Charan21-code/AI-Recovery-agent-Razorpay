"""
Intervention Timing Optimizer: Estimates optimal delay minutes for recovery interventions.
"""

from typing import Optional
from backend.core.constants import FailureCategory
from backend.core.logging import get_logger
from backend.schemas.context import DecisionContext

logger = get_logger("timing_optimizer")


class TimingOptimizer:
    """Estimates optimal recovery delay based on failure reasons and customer patterns."""

    def predict_optimal_delay(self, context: DecisionContext) -> int:
        """
        Returns recommended delay in minutes before executing or scheduling recovery.
        """
        cat = context.current_event.failure_category
        state = context.customer_state

        # If system is degraded, delay at least 60-120 minutes
        if context.is_merchant_system_degraded:
            return 90

        # Transient bank timeouts: 30 minutes for gateway stabilization
        if cat == FailureCategory.TRANSIENT_BANK_TIMEOUT:
            return 30

        # Insufficient funds: typically recovered after salary credit or next business day (12-24 hours)
        if cat == FailureCategory.INSUFFICIENT_FUNDS:
            return 720  # 12 hours

        # Authentication failed / OTP: usually best retried in 15-30 minutes
        if cat == FailureCategory.AUTHENTICATION_FAILED:
            return 15

        # Cart abandonment: 45-60 minutes gives time without being pushy
        if cat == FailureCategory.INACTIVITY_DROPOFF:
            return 45

        # Mandate rejected / Card expired: payment method update required immediately
        if cat in [FailureCategory.EXPIRED_OR_BLOCKED_CARD, FailureCategory.MANDATE_REJECTED]:
            return 0

        # High intervention fatigue: back off to 2 hours
        if state.intervention_fatigue_score > 0.6:
            return 120

        # Default fallback
        return 30


timing_optimizer = TimingOptimizer()
