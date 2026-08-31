"""
Merchant Degradation Detector: Analyzes rolling failure rates across payment methods to detect gateway-wide degradation.
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from backend.core.constants import EventType
from backend.core.logging import get_logger
from backend.db.models.events import NormalizedEventRecord

logger = get_logger("degradation_detector")


class DegradationDetector:
    """Monitors rolling failure spikes by payment method or bank gateway."""

    def __init__(self, baseline_failure_rate: float = 0.10, spike_multiplier: float = 2.5):
        self.baseline_failure_rate = baseline_failure_rate
        self.spike_multiplier = spike_multiplier

    def evaluate_merchant_status(
        self,
        session: Session,
        merchant_id: str,
        as_of_timestamp: datetime,
        window_minutes: int = 60,
    ) -> Tuple[bool, float, Dict[str, float]]:
        """
        Calculates failure rate in the rolling window [as_of_timestamp - window, as_of_timestamp].
        Returns: (is_degraded, degradation_factor, method_failure_rates)
        """
        window_start = as_of_timestamp - timedelta(minutes=window_minutes)

        stmt = (
            select(
                NormalizedEventRecord.payment_method,
                NormalizedEventRecord.event_type,
                func.count(NormalizedEventRecord.id),
            )
            .where(
                NormalizedEventRecord.merchant_id == merchant_id,
                NormalizedEventRecord.timestamp >= window_start,
                NormalizedEventRecord.timestamp <= as_of_timestamp,
            )
            .group_by(NormalizedEventRecord.payment_method, NormalizedEventRecord.event_type)
        )
        results = session.execute(stmt).all()

        method_totals: Dict[str, int] = {}
        method_failures: Dict[str, int] = {}

        for method, ev_type, count in results:
            m = method or "unknown"
            method_totals[m] = method_totals.get(m, 0) + count
            if ev_type in [EventType.PAYMENT_FAILED.value, EventType.SUBSCRIPTION_PAYMENT_FAILED.value]:
                method_failures[m] = method_failures.get(m, 0) + count

        method_rates: Dict[str, float] = {}
        max_rate = 0.0

        for m, total in method_totals.items():
            if total >= 5:  # Minimum sample size threshold
                rate = method_failures.get(m, 0) / total
                method_rates[m] = round(rate, 4)
                if rate > max_rate:
                    max_rate = rate

        is_degraded = max_rate >= (self.baseline_failure_rate * self.spike_multiplier)
        degradation_factor = round(max_rate / self.baseline_failure_rate, 2) if self.baseline_failure_rate > 0 else 1.0

        if is_degraded:
            logger.warning(
                "Merchant payment system degradation detected",
                merchant_id=merchant_id,
                max_failure_rate=max_rate,
                degradation_factor=degradation_factor,
            )

        return is_degraded, degradation_factor, method_rates


degradation_detector = DegradationDetector()
