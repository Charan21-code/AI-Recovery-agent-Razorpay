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

        # Checkout abandonment generally warrants sending a recovery link
        # If the ML model recommends something else, we still prefer generating a link
        action = best_action
        if action not in [RecoveryActionType.SEND_CHECKOUT_RECOVERY, RecoveryActionType.GENERATE_PAYMENT_LINK]:
            action = RecoveryActionType.SEND_CHECKOUT_RECOVERY

        channel = CommunicationChannel.WHATSAPP if context.customer_profile.phone else CommunicationChannel.EMAIL

        comm = CommunicationPayload(
            channel=channel,
            subject="Complete your purchase",
            message_body=f"Hi {context.customer_profile.name}, it looks like you left something behind. Click here to complete your payment of {context.current_event.amount} {context.current_event.currency}.",
            payment_link_url=f"https://rzp.io/i/checkout_{context.current_event.event_id[-6:]}"
        )

        return self._create_proposal(
            context=context,
            selected_action=action,
            confidence=confidence,
            reasoning=f"Customer abandoned checkout. Best action is to send a recovery link via {channel.value}.",
            communication=comm,
        )
