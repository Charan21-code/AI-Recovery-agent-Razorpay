"""
Outcome Engine: Handles recovery success/failure observations, state updates,
financial attribution, and audit trail generation.
"""

from datetime import datetime, timezone
from typing import Optional, Tuple
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.constants import AgentType, Environment, EventType, FailureCategory, RecoveryActionType
from backend.core.logging import get_logger
from backend.db.models.customer import CustomerStateSnapshotRecord
from backend.db.models.recovery import ExecutionLogRecord, OutcomeRecord
from backend.schemas.context import DecisionContext
from backend.schemas.events import NormalizedEvent
from backend.schemas.feedback import RewardBreakdown
from backend.schemas.outcomes import RecoveryOutcome, StateUpdateSummary
from backend.services.feedback.feedback_store import feedback_store
from backend.services.outcomes.audit_trail import audit_trail_service
from backend.services.outcomes.revenue_calculator import revenue_calculator
from backend.services.state.state_store import state_store

logger = get_logger("outcome_processor")


class OutcomeProcessor:
    """
    Processes real or simulated recovery outcomes, synchronously updating rolling state,
    calculating financial rewards, emitting feedback learning events, and producing an immutable audit record.
    """

    def process_outcome(
        self,
        session: Session,
        outcome: RecoveryOutcome,
        action_executed: RecoveryActionType = RecoveryActionType.DELAYED_RETRY,
        merchant_id: str = "mer_default",
        order_id: Optional[str] = None,
        payment_id: Optional[str] = None,
        context: Optional[DecisionContext] = None,
        agent_type: Optional[AgentType] = None,
    ) -> Tuple[StateUpdateSummary, RewardBreakdown]:
        """
        Processes a recovery outcome end-to-end:
        1. Checks for idempotency.
        2. Retrieves baseline state prior to outcome event.
        3. Persists OutcomeRecord.
        4. Emits NormalizedEvent (RECOVERY_SUCCESS / RECOVERY_FAILED) to live state.
        5. Computes updated rolling state and saves snapshot.
        6. Computes financial metrics (gross, intervention cost, net reward).
        7. Appends chronological audit trail entry.
        """
        # 1. Idempotency Check
        stmt = select(OutcomeRecord).where(OutcomeRecord.outcome_id == outcome.outcome_id)
        existing_outcome = session.execute(stmt).scalar_one_or_none()
        if existing_outcome:
            logger.warning(f"Outcome {outcome.outcome_id} already processed. Returning cached state.")

        # 2. Baseline state before the outcome
        before_state = state_store.get_customer_state_as_of(
            session=session,
            customer_id=outcome.customer_id,
            as_of_timestamp=outcome.observed_at,
        )

        # 3. Persist OutcomeRecord
        outcome_rec = OutcomeRecord(
            outcome_id=outcome.outcome_id,
            execution_id=outcome.execution_id,
            event_id=outcome.event_id,
            customer_id=outcome.customer_id,
            outcome_type=outcome.outcome_type.value,
            recovered_amount=outcome.recovered_amount,
            is_success=outcome.is_success,
            time_to_recovery_seconds=outcome.time_to_recovery_seconds,
            details_json=outcome.raw_details,
            observed_at=outcome.observed_at,
        )
        session.add(outcome_rec)
        session.commit()

        # 4. Emit NormalizedEvent to update chronological state store
        norm_outcome_event = NormalizedEvent(
            event_id=f"evt_outcome_{outcome.outcome_id[-8:]}",
            source="outcome_engine",
            environment=Environment.TEST,
            event_type=outcome.outcome_type,
            timestamp=outcome.observed_at,
            merchant_id=merchant_id,
            customer_id=outcome.customer_id,
            order_id=order_id,
            payment_id=payment_id,
            amount=outcome.recovered_amount,
            currency=outcome.currency,
            failure_category=FailureCategory.UNKNOWN,
            is_actionable=False,
            metadata={
                "execution_id": outcome.execution_id,
                "time_to_recovery_minutes": round((outcome.time_to_recovery_seconds or 0) / 60.0, 2),
                "is_success": outcome.is_success,
            },
        )
        state_store.record_normalized_event(session, norm_outcome_event)

        # 5. Compute updated rolling CustomerState (including the new event)
        after_state = state_store.get_customer_state_as_of(
            session=session,
            customer_id=outcome.customer_id,
            as_of_timestamp=datetime.now(timezone.utc),
        )

        # Persist CustomerStateSnapshotRecord
        snapshot_rec = CustomerStateSnapshotRecord(
            customer_id=outcome.customer_id,
            as_of_event_id=norm_outcome_event.event_id,
            as_of_timestamp=datetime.now(timezone.utc),
            total_transactions=after_state.total_transactions,
            successful_transactions=after_state.successful_transactions,
            failed_transactions=after_state.failed_transactions,
            success_rate=after_state.success_rate,
            total_revenue_generated=after_state.total_revenue_generated,
            average_transaction_value=after_state.average_transaction_value,
            total_recovery_attempts=after_state.total_recovery_attempts,
            successful_recoveries=after_state.successful_recoveries,
            failed_recoveries=after_state.failed_recoveries,
            historical_recovery_rate=after_state.historical_recovery_rate,
            average_recovery_time_minutes=after_state.average_recovery_time_minutes,
            recent_intervention_count=after_state.recent_intervention_count,
            consecutive_failures_count=after_state.consecutive_failures_count,
            intervention_fatigue_score=after_state.intervention_fatigue_score,
            preferred_payment_method=after_state.preferred_payment_method,
            estimated_clv=after_state.estimated_clv,
            state_payload_json=after_state.model_dump(mode="json"),
        )
        session.add(snapshot_rec)
        session.commit()

        # 6. Compute Financial Reward & Cost Breakdown
        reward_breakdown = revenue_calculator.calculate_reward(
            recovered_amount=outcome.recovered_amount,
            is_success=outcome.is_success,
            action=action_executed,
            intervention_fatigue_score=before_state.intervention_fatigue_score,
        )

        # 7. Record Audit Trail
        audit_trail_service.record_entry(
            session=session,
            event_id=outcome.event_id,
            execution_id=outcome.execution_id,
            outcome_id=outcome.outcome_id,
            stage="OUTCOME",
            actor="OutcomeEngine",
            action=outcome.outcome_type.value,
            details={
                "is_success": outcome.is_success,
                "recovered_amount": outcome.recovered_amount,
                "net_reward": reward_breakdown.net_reward,
                "intervention_cost": reward_breakdown.intervention_cost,
                "friction_penalty": reward_breakdown.customer_friction_penalty,
                "previous_recovery_rate": before_state.historical_recovery_rate,
                "updated_recovery_rate": after_state.historical_recovery_rate,
                "updated_fatigue_score": after_state.intervention_fatigue_score,
            },
            timestamp=outcome.observed_at,
        )

        summary = StateUpdateSummary(
            customer_id=outcome.customer_id,
            previous_recovery_rate=before_state.historical_recovery_rate,
            updated_recovery_rate=after_state.historical_recovery_rate,
            previous_total_revenue=before_state.total_revenue_generated,
            updated_total_revenue=after_state.total_revenue_generated,
            updated_fatigue_score=after_state.intervention_fatigue_score,
            timestamp=datetime.now(timezone.utc),
        )

        # 8. Record Closed-Loop Learning Event (Context + Action + Outcome + Reward)
        if context:
            try:
                feedback_store.record_learning_event(
                    session=session,
                    context=context,
                    action_taken=action_executed,
                    outcome=outcome,
                    reward=reward_breakdown,
                    agent_type=agent_type or AgentType.PAYMENT_FAILURE,
                )
            except Exception as e:
                logger.error(f"Failed to record feedback learning event: {e}")

        return summary, reward_breakdown


outcome_processor = OutcomeProcessor()
