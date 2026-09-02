from backend.core.constants import (
    AgentType,
    CommunicationChannel,
    RecoveryActionType,
)
from backend.schemas.agent import ActionProposal, CommunicationPayload, MultiStepPlan, PlanStep
from backend.schemas.predictions import OpportunityScore
from backend.schemas.context import DecisionContext
from backend.schemas.predictions import ModelPredictions
from backend.services.agents.base import BaseRecoveryAgent


class OverdueReceivableAgent(BaseRecoveryAgent):
    """
    Agent responsible for recovering B2B and overdue invoices.
    Handles larger amounts, progressive follow-ups, and escalation to human agents.
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.OVERDUE_RECEIVABLE

    def handle_event(
        self,
        context: DecisionContext,
        predictions: ModelPredictions,
        opportunity: OpportunityScore,
    ) -> ActionProposal:
        best_action = opportunity.recommended_action
        confidence = opportunity.recovery_propensity
        amount_at_risk = context.revenue_at_risk

        # For very high value invoices, we might want to escalate to human early
        if amount_at_risk > 100000:  # e.g. Rs 1 Lakh
            return self._create_proposal(
                context=context,
                selected_action=RecoveryActionType.ESCALATE_TO_HUMAN,
                confidence=0.95,
                reasoning=f"High value overdue invoice (Rs.{amount_at_risk:,.2f}). Escalating to human agent immediately.",
                requires_human_review=True,
            )

        # For normal overdue invoices, we use progressive follow-up
        action = RecoveryActionType.PROGRESSIVE_FOLLOWUP
        
        # Create a progressive follow-up plan
        plan = MultiStepPlan(
            plan_id=f"followup_{context.current_event.event_id[-6:]}",
            target_event_id=context.current_event.event_id,
            customer_id=context.customer_profile.customer_id,
            total_steps=3,
            steps=[
                PlanStep(step_number=1, action=RecoveryActionType.SEND_PAYMENT_REMINDER, channel=CommunicationChannel.EMAIL, delay_minutes=0, description="Gentle email reminder"),
                PlanStep(step_number=2, action=RecoveryActionType.SEND_PERSONALIZED_MESSAGE, channel=CommunicationChannel.WHATSAPP, delay_minutes=2880, description="WhatsApp personalized message on day 3"),
                PlanStep(step_number=3, action=RecoveryActionType.START_VOICE_RECOVERY, channel=CommunicationChannel.VOICE, delay_minutes=7200, description="Automated voice call on day 5"),
            ]
        )

        # Start with the first communication step
        comm = CommunicationPayload(
            channel=CommunicationChannel.EMAIL,
            subject="Reminder: Overdue Invoice",
            message_body=f"Dear {context.customer_profile.name}, this is a gentle reminder that your invoice for {context.current_event.amount} {context.current_event.currency} is currently overdue. Please find the payment link attached.",
            payment_link_url="https://rzp.io/i/invoice_pay"
        )

        return self._create_proposal(
            context=context,
            selected_action=action,
            confidence=confidence,
            reasoning=f"Standard overdue invoice. Initiating progressive follow-up starting with an email reminder.",
            multi_step_plan=plan,
            communication=comm,
        )
