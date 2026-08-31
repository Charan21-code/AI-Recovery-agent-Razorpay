"""
Temporal Context Builder: Assembles complete decision context for actionable revenue recovery events.
Enforces zero future leakage by restricting all historical state queries to t <= as_of_timestamp.
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy.orm import Session
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.schemas.context import (
    CustomerHistorySummary,
    DecisionContext,
    MerchantPolicyContext,
)
from backend.schemas.events import NormalizedEvent
from backend.services.state.state_store import state_store

logger = get_logger("context_builder")


class ContextBuilder:
    """Builds clean, structured DecisionContext models with strict temporal isolation."""

    def build_context(
        self,
        session: Session,
        event: NormalizedEvent,
        custom_policy: Optional[MerchantPolicyContext] = None,
    ) -> DecisionContext:
        """
        Builds a DecisionContext for the given actionable event.
        Guarantees that state is evaluated strictly as of event.timestamp.
        """
        as_of = event.timestamp

        # 1. Customer Profile
        profile = state_store.get_or_create_customer_profile(
            session=session,
            customer_id=event.customer_id,
            merchant_id=event.merchant_id,
        )

        # 2. Chronological Customer State (strictly up to as_of timestamp)
        customer_state = state_store.get_customer_state_as_of(
            session=session,
            customer_id=event.customer_id,
            as_of_timestamp=as_of,
        )

        # 3. History Summary
        recent_summaries = []
        if customer_state.total_transactions > 0:
            recent_summaries.append(
                f"{customer_state.successful_transactions} of {customer_state.total_transactions} historical transactions succeeded."
            )
        if customer_state.total_recovery_attempts > 0:
            recent_summaries.append(
                f"{customer_state.successful_recoveries} of {customer_state.total_recovery_attempts} previous recoveries succeeded ({int(customer_state.historical_recovery_rate * 100)}%)."
            )
        if customer_state.consecutive_failures_count > 1:
            recent_summaries.append(
                f"Customer currently has {customer_state.consecutive_failures_count} consecutive payment failures."
            )

        history_summary = CustomerHistorySummary(
            total_transactions=customer_state.total_transactions,
            successful_transactions=customer_state.successful_transactions,
            failed_transactions=customer_state.failed_transactions,
            success_rate=customer_state.success_rate,
            total_revenue_generated=customer_state.total_revenue_generated,
            previous_recovery_attempts=customer_state.total_recovery_attempts,
            successful_recoveries=customer_state.successful_recoveries,
            historical_recovery_rate=customer_state.historical_recovery_rate,
            consecutive_failures_count=customer_state.consecutive_failures_count,
            intervention_fatigue_score=customer_state.intervention_fatigue_score,
            recent_attempts_summary=recent_summaries,
        )

        # 4. Policy Context
        policy_context = custom_policy or MerchantPolicyContext(
            max_payment_retries=settings.MAX_PAYMENT_RETRIES,
            min_confidence_threshold=settings.MIN_CONFIDENCE_THRESHOLD,
            retry_window_hours=settings.RETRY_WINDOW_HOURS,
            min_retry_interval_minutes=settings.MIN_RETRY_INTERVAL_MINUTES,
            max_automated_interventions=settings.MAX_AUTOMATED_INTERVENTIONS,
            allow_discount=settings.ALLOW_DISCOUNT,
            max_discount_percent=settings.MAX_DISCOUNT_PERCENT,
            human_escalation_after_attempts=settings.HUMAN_ESCALATION_AFTER_ATTEMPTS,
        )

        # 5. Financial Exposure Calculations
        revenue_at_risk = event.amount
        clv_at_risk = customer_state.estimated_clv + revenue_at_risk

        context = DecisionContext(
            context_id=f"ctx_{uuid.uuid4().hex[:12]}",
            as_of_timestamp=as_of,
            current_event=event,
            customer_profile=profile,
            customer_state=customer_state,
            history_summary=history_summary,
            policy_context=policy_context,
            revenue_at_risk=round(revenue_at_risk, 2),
            estimated_clv_at_risk=round(clv_at_risk, 2),
            is_merchant_system_degraded=False,
            degradation_factor=1.0,
        )

        logger.debug(
            "Decision context built successfully",
            context_id=context.context_id,
            customer_id=context.customer_profile.customer_id,
            as_of=as_of.isoformat(),
        )
        return context


context_builder = ContextBuilder()
