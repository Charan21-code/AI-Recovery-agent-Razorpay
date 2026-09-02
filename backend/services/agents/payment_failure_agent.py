from backend.core.constants import (
    AgentType,
    CommunicationChannel,
    FailureCategory,
    RecoveryActionType,
)
from backend.schemas.agent import ActionProposal, CommunicationPayload
from backend.schemas.predictions import OpportunityScore
from backend.schemas.context import DecisionContext
from backend.schemas.predictions import ModelPredictions
from backend.services.agents.base import BaseRecoveryAgent


class PaymentFailureAgent(BaseRecoveryAgent):
    """
    Agent responsible for recovering active transaction failures.
    Handles TRANSIENT_BANK_TIMEOUT, INSUFFICIENT_FUNDS, EXPIRED_OR_BLOCKED_CARD, MANDATE_REJECTED.
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.PAYMENT_FAILURE

    def handle_event(
        self,
        context: DecisionContext,
        predictions: ModelPredictions,
        opportunity: OpportunityScore,
    ) -> ActionProposal:
        failure_cat = context.current_event.failure_category
        best_action = opportunity.recommended_action
        confidence = opportunity.recovery_propensity

        # 1. Systemic Degradation Check
        if context.is_merchant_system_degraded:
            return self._create_proposal(
                context=context,
                selected_action=RecoveryActionType.DELAYED_RETRY,
                confidence=0.9,
                reasoning="Merchant system degradation detected. Postponing retry to allow recovery.",
                communication=None,
                requires_human_review=False,
            )

        # 2. Hard Declines / Non-recoverable without user action
        if failure_cat in [FailureCategory.EXPIRED_OR_BLOCKED_CARD, FailureCategory.MANDATE_REJECTED]:
            comm = CommunicationPayload(
                channel=CommunicationChannel.EMAIL,
                subject="Action Required: Update your payment method",
                message_body=f"Hi {context.customer_profile.name}, your payment of {context.current_event.amount} {context.current_event.currency} failed because the payment method is invalid. Please update it.",
                payment_link_url="https://rzp.io/i/update_method"
            )
            return self._create_proposal(
                context=context,
                selected_action=RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE,
                confidence=confidence,
                reasoning="Hard decline. Customer must update their payment method.",
                communication=comm,
            )

        # 3. Soft Declines (Insufficient Funds, Transient Timeouts)
        if failure_cat == FailureCategory.TRANSIENT_BANK_TIMEOUT:
            # Usually delayed retry is best. We use the ML recommendation if it aligns.
            action = best_action if best_action in [RecoveryActionType.IMMEDIATE_RETRY, RecoveryActionType.DELAYED_RETRY] else RecoveryActionType.DELAYED_RETRY
            return self._create_proposal(
                context=context,
                selected_action=action,
                confidence=confidence,
                reasoning=f"Transient timeout. Selected {action.value} based on ML predictions with {predictions.optimal_delay_minutes}min delay.",
            )

        if failure_cat == FailureCategory.INSUFFICIENT_FUNDS:
            comm = CommunicationPayload(
                channel=CommunicationChannel.SMS,
                message_body=f"Hi {context.customer_profile.name}, your payment failed due to insufficient funds. Please ensure your account has balance, and we will retry soon."
            )
            return self._create_proposal(
                context=context,
                selected_action=RecoveryActionType.DELAYED_RETRY,
                confidence=confidence,
                reasoning="Insufficient funds. Delaying retry and notifying customer.",
                communication=comm,
            )

        # Fallback to ML recommendation
        return self._create_proposal(
            context=context,
            selected_action=best_action,
            confidence=confidence,
            reasoning="Fallback to ML recommended action.",
        )
