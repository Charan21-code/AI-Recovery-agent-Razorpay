"""
Revenue and Intervention Cost Calculator for Outcome Processing and Reward Modeling.
"""

from typing import Optional
from backend.core.constants import CommunicationChannel, RecoveryActionType
from backend.schemas.feedback import RewardBreakdown


class RevenueCalculator:
    """
    Computes gross recovered revenue, intervention costs per communication channel,
    friction penalties, and net financial impact for every recovery outcome.
    """

    # Base operational/vendor cost matrix in INR per action type
    ACTION_COST_MATRIX = {
        RecoveryActionType.IMMEDIATE_RETRY: 0.00,
        RecoveryActionType.DELAYED_RETRY: 0.00,
        RecoveryActionType.SEND_PAYMENT_REMINDER: 0.05,
        RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE: 0.50,
        RecoveryActionType.SEND_CHECKOUT_RECOVERY: 0.50,
        RecoveryActionType.GENERATE_PAYMENT_LINK: 0.50,
        RecoveryActionType.SEND_PERSONALIZED_MESSAGE: 0.50,
        RecoveryActionType.START_VOICE_RECOVERY: 2.00,
        RecoveryActionType.ESCALATE_TO_HUMAN: 15.00,
        RecoveryActionType.SCHEDULE_DUNNING_STEP: 0.55,
        RecoveryActionType.PROGRESSIVE_FOLLOWUP: 2.55,
        RecoveryActionType.WAIT: 0.00,
        RecoveryActionType.STOP: 0.00,
    }

    # Channel cost overrides if channel is explicitly known
    CHANNEL_COST_MATRIX = {
        CommunicationChannel.EMAIL: 0.05,
        CommunicationChannel.SMS: 0.15,
        CommunicationChannel.WHATSAPP: 0.50,
        CommunicationChannel.VOICE: 2.00,
        CommunicationChannel.IN_APP: 0.01,
        CommunicationChannel.NONE: 0.00,
    }

    def get_intervention_cost(
        self,
        action: RecoveryActionType,
        channel: Optional[CommunicationChannel] = None,
    ) -> float:
        """Determines the baseline monetary cost of executing an intervention."""
        if channel and channel != CommunicationChannel.NONE:
            return self.CHANNEL_COST_MATRIX.get(channel, self.ACTION_COST_MATRIX.get(action, 0.0))
        return self.ACTION_COST_MATRIX.get(action, 0.0)

    def calculate_reward(
        self,
        recovered_amount: float,
        is_success: bool,
        action: RecoveryActionType,
        channel: Optional[CommunicationChannel] = None,
        intervention_fatigue_score: float = 0.0,
        was_unnecessary: bool = False,
    ) -> RewardBreakdown:
        """
        Computes the complete reward and financial breakdown for an outcome.
        Formula:
          Net = Recovered_Revenue - Intervention_Cost - Friction_Penalty - Unnecessary_Action_Penalty
        """
        gross_rev = round(float(recovered_amount if is_success else 0.0), 2)
        cost = round(float(self.get_intervention_cost(action, channel)), 2)
        
        # Friction penalty scales with existing customer fatigue (only applied on outreach actions)
        friction_penalty = 0.0
        if cost > 0.0:
            friction_penalty = round(float(intervention_fatigue_score * 5.0), 2)

        # Unnecessary action penalty (e.g. intervening when high organic recovery propensity)
        unnecessary_penalty = 0.0
        if was_unnecessary:
            unnecessary_penalty = round(min(50.0, gross_rev * 0.05), 2)

        return RewardBreakdown.calculate(
            recovered_revenue=gross_rev,
            intervention_cost=cost,
            customer_friction_penalty=friction_penalty,
            unnecessary_action_penalty=unnecessary_penalty,
        )

    def calculate_recovery_efficiency(self, breakdown: RewardBreakdown, revenue_at_risk: float) -> float:
        """
        Calculates recovery efficiency percentage (Net Recovered / Revenue at Risk).
        Returns 0.0 if revenue_at_risk <= 0.
        """
        if revenue_at_risk <= 0.0:
            return 0.0
        return round(float((breakdown.net_reward / revenue_at_risk) * 100.0), 2)


revenue_calculator = RevenueCalculator()
