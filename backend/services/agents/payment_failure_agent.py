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
    Handles TRANSIENT_BANK_TIMEOUT, INSUFFICIENT_FUNDS, EXPIRED_OR_BLOCKED_CARD, MANDATE_REJECTED, AUTHENTICATION_FAILED.
    Implements attempt-tiered decision logic adapting across attempts 0, 1-2, and 3+.
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
        amount = context.revenue_at_risk
        attempts = int(max(context.customer_state.total_recovery_attempts, context.history_summary.previous_recovery_attempts))
        is_vip = context.customer_profile.is_vip

        # 1. Systemic Degradation Check - Postpone retry to protect banking rails
        if context.is_merchant_system_degraded:
            return self._create_proposal(
                context=context,
                selected_action=RecoveryActionType.DELAYED_RETRY,
                confidence=0.9,
                reasoning="Merchant system degradation detected. Postponing retry to allow banking rails recovery.",
                communication=None,
                requires_human_review=False,
            )

        # 2. Hard Declines (Card expired, blocked, or mandate rejected) - cannot be retried silently
        if failure_cat in [FailureCategory.EXPIRED_OR_BLOCKED_CARD, FailureCategory.MANDATE_REJECTED]:
            best_action = RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE

        # 3. High-Value / VIP Attempt Exhaustion Escalation
        elif attempts >= 3 and (amount >= 10000.0 or is_vip):
            best_action = RecoveryActionType.ESCALATE_TO_HUMAN
        elif attempts == 2 and best_action in [RecoveryActionType.IMMEDIATE_RETRY, RecoveryActionType.DELAYED_RETRY]:
            best_action = RecoveryActionType.SEND_PERSONALIZED_MESSAGE

        # Communication Payload Generation based on ML's best_action
        comm = None
        
        if best_action == RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE:
            comm = CommunicationPayload(
                channel=CommunicationChannel.WHATSAPP if context.customer_profile.phone else CommunicationChannel.EMAIL,
                subject="Action Required: Update your payment method",
                message_body=f"Hi {context.customer_profile.name}, your payment of {amount:,.2f} {context.current_event.currency} could not be completed because your payment method is invalid or blocked. Please tap here to update your payment details.",
                payment_link_url="https://rzp.io/i/update_method"
            )
        elif best_action == RecoveryActionType.START_VOICE_RECOVERY:
            comm = CommunicationPayload(
                channel=CommunicationChannel.VOICE,
                message_body=f"Hello {context.customer_profile.name}, this is an automated call regarding your recent payment of {amount:,.2f} {context.current_event.currency}. Press 1 to receive a secure instant payment link.",
                payment_link_url="https://rzp.io/i/instant_pay"
            )
        elif best_action == RecoveryActionType.GENERATE_PAYMENT_LINK:
            comm = CommunicationPayload(
                channel=CommunicationChannel.WHATSAPP,
                message_body=f"Hi {context.customer_profile.name}, your payment of {amount:,.2f} failed. You can complete the payment using UPI, Credit Card, or NetBanking here:",
                payment_link_url="https://rzp.io/i/alt_methods"
            )
        elif best_action == RecoveryActionType.SEND_PERSONALIZED_MESSAGE:
            comm = CommunicationPayload(
                channel=CommunicationChannel.WHATSAPP,
                message_body=f"Namaste {context.customer_profile.name}, your bank servers timed out during your recent transaction of {amount:,.2f}. Click here to retry securely:",
                payment_link_url="https://rzp.io/i/quick_retry"
            )
        elif best_action == RecoveryActionType.DELAYED_RETRY and failure_cat == FailureCategory.INSUFFICIENT_FUNDS:
            comm = CommunicationPayload(
                channel=CommunicationChannel.SMS,
                message_body=f"Hi {context.customer_profile.name}, your payment of {amount:,.2f} failed due to insufficient funds. We will retry your payment in {predictions.optimal_delay_minutes // 60} hours."
            )
            
        return self._create_proposal(
            context=context,
            selected_action=best_action,
            confidence=confidence,
            reasoning=f"Optimal action {best_action.value} selected by ML inference engine for attempt {attempts}.",
            communication=comm,
            requires_human_review=(best_action == RecoveryActionType.ESCALATE_TO_HUMAN)
        )
