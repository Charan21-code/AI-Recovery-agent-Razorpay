"""
Opportunity Scorer: Prioritizes and ranks recovery opportunities for merchant dashboards.
"""

from typing import List
from backend.core.constants import RecoveryActionType
from backend.schemas.context import DecisionContext
from backend.schemas.predictions import ModelPredictions, OpportunityScore
from backend.services.ml.predictor import recovery_predictor


class OpportunityScorer:
    """Prioritizes and ranks actionable opportunities based on expected business return."""

    def score_opportunity(
        self,
        context: DecisionContext,
        predictions: ModelPredictions,
    ) -> OpportunityScore:
        """Computes priority level and OpportunityScore for a single context."""
        opp_score = predictions.opportunity_score
        amount = context.revenue_at_risk

        # Priority Level thresholds based on Opportunity Score & Financial Exposure
        if opp_score >= 5000.0 or amount >= 15000.0:
            priority = "CRITICAL"
        elif opp_score >= 2000.0 or amount >= 5000.0:
            priority = "HIGH"
        elif opp_score >= 500.0 or amount >= 1000.0:
            priority = "MEDIUM"
        else:
            priority = "LOW"

        return OpportunityScore(
            opportunity_id=f"opp_{context.context_id}",
            event_id=context.current_event.event_id,
            customer_id=context.customer_profile.customer_id,
            customer_name=context.customer_profile.name,
            amount=amount,
            event_type=context.current_event.event_type.value,
            priority_level=priority,
            recovery_propensity=predictions.overall_recovery_propensity,
            expected_recovery_value=predictions.best_expected_value,
            recommended_action=predictions.best_candidate_action,
            score=opp_score,
            timestamp=context.as_of_timestamp,
        )

    def rank_opportunities(
        self,
        opportunities: List[OpportunityScore],
    ) -> List[OpportunityScore]:
        """Sorts a list of opportunities in descending order of Recovery Opportunity Score."""
        return sorted(opportunities, key=lambda x: x.score, reverse=True)


opportunity_scorer = OpportunityScorer()
