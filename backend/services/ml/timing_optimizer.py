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
        hist = context.history_summary
        attempts = max(state.total_recovery_attempts, hist.previous_recovery_attempts)
        fatigue = max(state.intervention_fatigue_score, hist.intervention_fatigue_score)

        # Mandate rejected / Card expired: payment method update required immediately (zero delay)
        if cat in [FailureCategory.EXPIRED_OR_BLOCKED_CARD, FailureCategory.MANDATE_REJECTED]:
            return 0

        # Base delay in minutes based on failure category
        if cat == FailureCategory.TRANSIENT_BANK_TIMEOUT:
            base_delay = 30
        elif cat == FailureCategory.INSUFFICIENT_FUNDS:
            base_delay = 720  # 12 hours (wait for funds deposit / next morning)
        elif cat == FailureCategory.AUTHENTICATION_FAILED:
            base_delay = 15   # Quick retry for OTP/3DS
        elif cat == FailureCategory.INACTIVITY_DROPOFF:
            base_delay = 45   # Cart drop-off buffer
        else:
            base_delay = 30

        # If system is degraded, ensure at least 90 minutes
        if context.is_merchant_system_degraded:
            base_delay = max(base_delay, 90)

        # Exponential backoff timing multiplier based on previous failed attempts:
        # Attempt 0: 1x (30m / 720m)
        # Attempt 1: 2x (60m / 1440m)
        # Attempt 2: 4x (120m / 2880m)
        # Attempt >= 3: cooldown 1440m - 2880m (24h - 48h)
        if attempts == 1:
            delay = base_delay * 2
        elif attempts == 2:
            delay = base_delay * 4
        elif attempts >= 3:
            delay = max(1440, base_delay * 6)
        else:
            delay = base_delay

        # Back off if severe intervention fatigue detected
        if fatigue > 0.6:
            delay = max(delay, 120)

        return delay


timing_optimizer = TimingOptimizer()
