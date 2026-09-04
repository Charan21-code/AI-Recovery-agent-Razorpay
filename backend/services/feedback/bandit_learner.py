"""
Contextual Bandit Tracker: Multi-armed bandit reward tracking and UCB1 action ranking
for adaptive policy experimentation (Sections 40 & 41).
"""

import math
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.constants import EventType, RecoveryActionType
from backend.core.logging import get_logger
from backend.db.models.feedback import FeedbackRecord

logger = get_logger("bandit_learner")


class ContextualBanditTracker:
    """
    Computes empirical action payoffs, conversion rates, and Upper Confidence Bound (UCB1)
    values to guide adaptive action selection while strictly respecting merchant policy safety.
    """

    def __init__(self, exploration_constant: float = 1.414):
        self.exploration_constant = exploration_constant

    def compute_arm_statistics(self, session: Session) -> Dict[str, Dict[str, float]]:
        """
        Computes pull counts, conversion rates, total revenue, average net reward,
        and UCB1 scores for each action arm based on historical feedback records.
        """
        stmt = select(FeedbackRecord)
        records = list(session.execute(stmt).scalars().all())

        total_pulls = len(records)
        arm_data: Dict[str, Dict[str, Any]] = {}

        # Initialize tracking for standard actions
        for act in RecoveryActionType:
            arm_data[act.value] = {
                "pulls": 0,
                "conversions": 0,
                "total_recovered": 0.0,
                "total_cost": 0.0,
                "total_net_reward": 0.0,
            }

        # Accumulate empirical outcomes
        for r in records:
            act_name = r.action_taken
            if act_name not in arm_data:
                arm_data[act_name] = {
                    "pulls": 0,
                    "conversions": 0,
                    "total_recovered": 0.0,
                    "total_cost": 0.0,
                    "total_net_reward": 0.0,
                }
            
            arm_data[act_name]["pulls"] += 1
            if r.outcome_status == EventType.RECOVERY_SUCCESS.value:
                arm_data[act_name]["conversions"] += 1
            arm_data[act_name]["total_recovered"] += r.recovered_revenue
            arm_data[act_name]["total_cost"] += r.intervention_cost
            arm_data[act_name]["total_net_reward"] += r.net_reward

        stats: Dict[str, Dict[str, float]] = {}
        log_total = math.log(max(total_pulls, 1))

        for act_name, data in arm_data.items():
            pulls = data["pulls"]
            conversions = data["conversions"]
            conv_rate = (conversions / pulls) if pulls > 0 else 0.0
            mean_reward = (data["total_net_reward"] / pulls) if pulls > 0 else 0.0

            # UCB1 exploration bonus: c * sqrt(2 * ln(N) / N_a)
            if pulls == 0:
                ucb_score = 9999.0  # High initial value to encourage exploration
            else:
                bonus = self.exploration_constant * math.sqrt((2.0 * log_total) / pulls)
                ucb_score = round(mean_reward + bonus, 2)

            stats[act_name] = {
                "pulls": pulls,
                "conversions": conversions,
                "conversion_rate": round(float(conv_rate), 4),
                "total_recovered": round(float(data["total_recovered"]), 2),
                "total_cost": round(float(data["total_cost"]), 2),
                "total_net_reward": round(float(data["total_net_reward"]), 2),
                "mean_reward": round(float(mean_reward), 2),
                "ucb_score": ucb_score,
            }

        return stats

    def rank_allowed_actions(
        self,
        session: Session,
        allowed_actions: List[RecoveryActionType],
    ) -> List[Dict[str, Any]]:
        """
        Ranks candidate actions permitted by the Policy Engine by their empirical UCB score.
        Guarantees that policy safety constraints are NEVER bypassed by learning.
        """
        stats = self.compute_arm_statistics(session)
        ranked = []
        for act in allowed_actions:
            act_val = act.value if hasattr(act, "value") else str(act)
            info = stats.get(act_val, {
                "pulls": 0,
                "conversions": 0,
                "conversion_rate": 0.0,
                "mean_reward": 0.0,
                "ucb_score": 9999.0,
            })
            ranked.append({
                "action": act_val,
                **info,
            })

        # Sort by UCB score descending
        ranked.sort(key=lambda x: x["ucb_score"], reverse=True)
        return ranked

    def get_action_performance_table(self, session: Session) -> List[Dict[str, Any]]:
        """Returns action performance formatted for UI tables."""
        stats = self.compute_arm_statistics(session)
        # Filter to actions that have been pulled at least once, plus major candidate actions
        table_rows = []
        for act_name, data in stats.items():
            if data["pulls"] > 0:
                table_rows.append({
                    "Action": act_name,
                    "Pulls": data["pulls"],
                    "Conversions": data["conversions"],
                    "Win Rate": f"{data['conversion_rate'] * 100:.1f}%",
                    "Total Recovered (Rs.)": f"Rs.{data['total_recovered']:,.2f}",
                    "Mean Reward (Rs.)": f"Rs.{data['mean_reward']:,.2f}",
                    "UCB Score": f"{data['ucb_score']:.2f}",
                })
        return table_rows


bandit_learner = ContextualBanditTracker()
