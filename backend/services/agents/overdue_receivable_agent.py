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
        attempts = int(max(context.customer_state.total_recovery_attempts, context.history_summary.previous_recovery_attempts))
        is_vip = context.customer_profile.is_vip

        comm = None
        plan = None
        
        if amount_at_risk >= 100000.0 or best_action == RecoveryActionType.ESCALATE_TO_HUMAN:
            best_action = RecoveryActionType.ESCALATE_TO_HUMAN
        elif best_action == RecoveryActionType.START_VOICE_RECOVERY:
            comm = CommunicationPayload(
                channel=CommunicationChannel.VOICE,
                message_body=f"Greetings from Accounts. Invoice #{context.current_event.event_id[-6:]} for Rs.{amount_at_risk:,.2f} is past due. Press 1 to speak with billing or receive a direct payment link.",
                payment_link_url="https://rzp.io/i/invoice_pay"
            )
        elif best_action == RecoveryActionType.SEND_PERSONALIZED_MESSAGE:
            comm = CommunicationPayload(
                channel=CommunicationChannel.WHATSAPP,
                subject="Follow-up: Overdue Invoice",
                message_body=f"Dear {context.customer_profile.name}, your invoice of Rs.{amount_at_risk:,.2f} remains unpaid. Please settle via our instant payment portal here: https://rzp.io/i/invoice_pay",
                payment_link_url="https://rzp.io/i/invoice_pay"
            )
        else:
            best_action = RecoveryActionType.PROGRESSIVE_FOLLOWUP
            
            plan = MultiStepPlan(
                plan_id=f"followup_{context.current_event.event_id[-6:]}",
                target_event_id=context.current_event.event_id,
                customer_id=context.customer_profile.customer_id,
                total_steps=3,
                steps=[
                    PlanStep(step_number=1, action=RecoveryActionType.SEND_PAYMENT_REMINDER, channel=CommunicationChannel.EMAIL, delay_minutes=0, description="Gentle email reminder with PDF invoice"),
                    PlanStep(step_number=2, action=RecoveryActionType.SEND_PERSONALIZED_MESSAGE, channel=CommunicationChannel.WHATSAPP, delay_minutes=2880, description="WhatsApp personalized message on day 3"),
                    PlanStep(step_number=3, action=RecoveryActionType.START_VOICE_RECOVERY, channel=CommunicationChannel.VOICE, delay_minutes=7200, description="Automated voice call on day 5"),
                ]
            )

            comm = CommunicationPayload(
                channel=CommunicationChannel.EMAIL,
                subject="Reminder: Overdue Invoice",
                message_body=f"Dear {context.customer_profile.name}, this is a gentle reminder that invoice #{context.current_event.event_id[-6:]} for {amount_at_risk:,.2f} {context.current_event.currency} is currently overdue. Please find the payment link attached.",
                payment_link_url="https://rzp.io/i/invoice_pay"
            )

        return self._create_proposal(
            context=context,
            selected_action=best_action,
            confidence=confidence,
            reasoning=f"Optimal action {best_action.value} selected by ML inference engine for attempt {attempts}.",
            multi_step_plan=plan,
            communication=comm,
            requires_human_review=(best_action == RecoveryActionType.ESCALATE_TO_HUMAN)
        )
