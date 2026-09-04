"""
Feedback Store: Manages closed-loop learning tuples (Context + Action + Outcome + Reward)
and produces training datasets for offline model retraining.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import uuid
import numpy as np
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.core.constants import AgentType, EventType, RecoveryActionType
from backend.core.logging import get_logger
from backend.db.models.feedback import FeedbackRecord
from backend.schemas.agent import ActionProposal
from backend.schemas.context import DecisionContext
from backend.schemas.feedback import RewardBreakdown
from backend.schemas.outcomes import RecoveryOutcome
from backend.services.features.feature_engine import FeatureEngine, feature_engine

logger = get_logger("feedback_store")


class FeedbackStore:
    """
    Persists closed-loop feedback events and exports structured feature datasets for ML retraining.
    """

    def record_learning_event(
        self,
        session: Session,
        context: DecisionContext,
        action_taken: RecoveryActionType,
        outcome: RecoveryOutcome,
        reward: RewardBreakdown,
        agent_type: AgentType = AgentType.PAYMENT_FAILURE,
        model_version: str = "v1.0",
        policy_version: str = "v1.0",
    ) -> FeedbackRecord:
        """
        Persists an immutable learning record: Context + Action + Outcome + Reward.
        """
        # Extract features at decision time with zero future leakage
        context_features = feature_engine.extract_features(context)

        feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
        record = FeedbackRecord(
            feedback_id=feedback_id,
            event_id=outcome.event_id,
            customer_id=outcome.customer_id,
            agent_type=agent_type.value if hasattr(agent_type, "value") else str(agent_type),
            action_taken=action_taken.value if hasattr(action_taken, "value") else str(action_taken),
            context_vector_json=context_features,
            outcome_status=outcome.outcome_type.value if hasattr(outcome.outcome_type, "value") else str(outcome.outcome_type),
            recovered_revenue=outcome.recovered_amount,
            intervention_cost=reward.intervention_cost,
            customer_friction_penalty=reward.customer_friction_penalty,
            unnecessary_action_penalty=reward.unnecessary_action_penalty,
            net_reward=reward.net_reward,
            model_version=model_version,
            policy_version=policy_version,
        )

        session.add(record)
        session.commit()
        session.refresh(record)

        logger.info(
            f"Learning event stored: feedback_id={feedback_id} action={record.action_taken} "
            f"status={record.outcome_status} net_reward=Rs.{reward.net_reward:,.2f}"
        )
        return record

    def get_feedback_records(
        self,
        session: Session,
        limit: int = 100,
        offset: int = 0,
        action_filter: Optional[str] = None,
    ) -> List[FeedbackRecord]:
        """Queries stored feedback records."""
        stmt = select(FeedbackRecord).order_by(desc(FeedbackRecord.created_at)).offset(offset).limit(limit)
        if action_filter:
            stmt = stmt.where(FeedbackRecord.action_taken == action_filter)
        return list(session.execute(stmt).scalars().all())

    def get_training_dataset(
        self,
        session: Session,
        min_samples: int = 1,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Constructs (X, y, rewards) arrays from historical feedback records.
        X: (N, num_features) aligned context feature matrix
        y: (N,) binary success indicator (1 for RECOVERY_SUCCESS, 0 otherwise)
        rewards: (N,) net economic reward
        """
        stmt = select(FeedbackRecord).order_by(FeedbackRecord.created_at.asc())
        records = list(session.execute(stmt).scalars().all())

        if len(records) < min_samples:
            return np.empty((0, len(FeatureEngine.FEATURE_NAMES))), np.empty((0,)), np.empty((0,))

        feature_names = FeatureEngine.FEATURE_NAMES
        X_list: List[List[float]] = []
        y_list: List[int] = []
        rewards_list: List[float] = []

        for rec in records:
            ctx_dict = rec.context_vector_json or {}
            row = [float(ctx_dict.get(fname, 0.0)) for fname in feature_names]
            X_list.append(row)

            # Success label: 1 if RECOVERY_SUCCESS, else 0
            is_success = 1 if rec.outcome_status == EventType.RECOVERY_SUCCESS.value else 0
            y_list.append(is_success)
            rewards_list.append(rec.net_reward)

        return (
            np.array(X_list, dtype=np.float32),
            np.array(y_list, dtype=np.int32),
            np.array(rewards_list, dtype=np.float32),
        )

    def get_feedback_summary(self, session: Session) -> Dict[str, Any]:
        """Returns high-level learning aggregates across all recorded feedback events."""
        stmt = select(FeedbackRecord)
        records = list(session.execute(stmt).scalars().all())

        total_events = len(records)
        if total_events == 0:
            return {
                "total_events": 0,
                "total_recovered_revenue": 0.0,
                "total_net_reward": 0.0,
                "overall_conversion_rate": 0.0,
                "action_counts": {},
            }

        total_rev = sum(r.recovered_revenue for r in records)
        total_net = sum(r.net_reward for r in records)
        successes = sum(1 for r in records if r.outcome_status == EventType.RECOVERY_SUCCESS.value)

        action_counts: Dict[str, int] = {}
        for r in records:
            action_counts[r.action_taken] = action_counts.get(r.action_taken, 0) + 1

        return {
            "total_events": total_events,
            "total_recovered_revenue": round(float(total_rev), 2),
            "total_net_reward": round(float(total_net), 2),
            "overall_conversion_rate": round(float(successes / total_events), 4),
            "action_counts": action_counts,
        }


feedback_store = FeedbackStore()
