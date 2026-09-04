from backend.core.constants import (
    AgentType,
    CommunicationChannel,
    RecoveryActionType,
)
from backend.schemas.agent import ActionProposal, CommunicationPayload
from backend.schemas.predictions import OpportunityScore
from backend.schemas.context import DecisionContext
from backend.schemas.predictions import ModelPredictions
from backend.services.agents.base import BaseRecoveryAgent


class CheckoutAbandonmentAgent(BaseRecoveryAgent):
    """
    Agent responsible for recovering checkout abandonment and inactivity dropoffs.
    Focuses on messaging, payment links, and capturing intent before cooldown.
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.CHECKOUT_ABANDONMENT

    def handle_event(
        self,
        context: DecisionContext,
        predictions: ModelPredictions,
        opportunity: OpportunityScore,
    ) -> ActionProposal:
        best_action = opportunity.recommended_action
        confidence = opportunity.recovery_propensity
        amount = context.revenue_at_risk
        attempts = int(max(context.customer_state.total_recovery_attempts, context.history_summary.previous_recovery_attempts))
        channel = CommunicationChannel.WHATSAPP if context.customer_profile.phone else CommunicationChannel.EMAIL

        # Anti-fatigue rule: halt outreach after 2 attempts
        if attempts >= 2 or best_action == RecoveryActionType.STOP:
            return self._create_proposal(
                context=context,
                selected_action=RecoveryActionType.STOP,
                confidence=confidence,
                reasoning=f"Customer has received {attempts} prior checkout reminders without conversion. Halting automated outreach to prevent fatigue.",
                communication=None,
            )

        if best_action not in [RecoveryActionType.GENERATE_PAYMENT_LINK, RecoveryActionType.SEND_CHECKOUT_RECOVERY]:
            best_action = RecoveryActionType.SEND_CHECKOUT_RECOVERY

        comm = None
        
        if best_action == RecoveryActionType.GENERATE_PAYMENT_LINK:
            policy = context.policy_context
            discount_text = f" Use code SAVE{int(policy.max_discount_percent)} for {int(policy.max_discount_percent)}% off!" if policy.allow_discount else ""
            comm = CommunicationPayload(
                channel=channel,
                subject="Still thinking it over? Complete your order",
                message_body=f"Hi {context.customer_profile.name}, your cart items totaling {amount:,.2f} {context.current_event.currency} are reserved.{discount_text} Click to finish checkout:",
                payment_link_url=f"https://rzp.io/i/chk_resume_{context.current_event.event_id[-6:]}"
            )
            
        elif best_action == RecoveryActionType.SEND_CHECKOUT_RECOVERY:
            comm = CommunicationPayload(
                channel=channel,
                subject="Complete your purchase",
                message_body=f"Hi {context.customer_profile.name}, it looks like you left something behind. Click here to complete your order of {amount:,.2f} {context.current_event.currency}:",
                payment_link_url=f"https://rzp.io/i/checkout_{context.current_event.event_id[-6:]}"
            )

        return self._create_proposal(
            context=context,
            selected_action=best_action,
            confidence=confidence,
            reasoning=f"Optimal action {best_action.value} selected by ML inference engine for attempt {attempts}.",
            communication=comm,
            requires_human_review=(best_action == RecoveryActionType.ESCALATE_TO_HUMAN)
        )
