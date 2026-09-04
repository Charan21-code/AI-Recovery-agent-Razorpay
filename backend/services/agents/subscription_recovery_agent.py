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


class SubscriptionRecoveryAgent(BaseRecoveryAgent):
    """
    Agent responsible for recovering subscription failures.
    Handles dunning schedules, grace periods, and progressive retries.
    """

    @property
    def agent_type(self) -> AgentType:
        return AgentType.SUBSCRIPTION_RECOVERY

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
        is_vip = context.customer_profile.is_vip

        comm = None
        plan = None

        if best_action == RecoveryActionType.ESCALATE_TO_HUMAN:
            pass # No comm needed for internal escalation
        elif best_action == RecoveryActionType.START_VOICE_RECOVERY:
            comm = CommunicationPayload(
                channel=CommunicationChannel.VOICE,
                message_body=f"Hello {context.customer_profile.name}, your recurring subscription payment of {amount:,.2f} {context.current_event.currency} has failed multiple times. Press 1 to renew your billing mandate immediately.",
                payment_link_url="https://rzp.io/i/sub_mandate"
            )
        elif best_action == RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE:
            comm = CommunicationPayload(
                channel=CommunicationChannel.WHATSAPP if context.customer_profile.phone else CommunicationChannel.EMAIL,
                subject="Urgent: Your subscription is about to be paused",
                message_body=f"Hi {context.customer_profile.name}, your subscription payment of {amount:,.2f} failed. Please update your mandate card or payment method today to ensure uninterrupted service:",
                payment_link_url="https://rzp.io/i/sub_update"
            )
        elif best_action == RecoveryActionType.GENERATE_PAYMENT_LINK:
            comm = CommunicationPayload(
                channel=CommunicationChannel.WHATSAPP,
                message_body=f"Hi {context.customer_profile.name}, your subscription payment of {amount:,.2f} failed. You can complete the payment using UPI, Credit Card, or NetBanking here:",
                payment_link_url="https://rzp.io/i/alt_methods"
            )
        else:
            # For immediate/delayed retries and reminders on subscriptions, schedule a dunning plan
            delay = predictions.optimal_delay_minutes or 1440
            best_action = RecoveryActionType.SCHEDULE_DUNNING_STEP
            plan = MultiStepPlan(
                plan_id=f"dunning_{context.current_event.event_id[-6:]}",
                target_event_id=context.current_event.event_id,
                customer_id=context.customer_profile.customer_id,
                total_steps=3,
                steps=[
                    PlanStep(step_number=1, action=RecoveryActionType.DELAYED_RETRY, delay_minutes=delay, description=f"Automated mandate re-try after {delay}m"),
                    PlanStep(step_number=2, action=RecoveryActionType.SEND_PAYMENT_REMINDER, channel=CommunicationChannel.EMAIL, delay_minutes=2880, description="Gentle email notification on day 2"),
                    PlanStep(step_number=3, action=RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE, channel=CommunicationChannel.WHATSAPP, delay_minutes=5760, description="WhatsApp mandate update request on day 4"),
                ]
            )

        return self._create_proposal(
            context=context,
            selected_action=best_action,
            confidence=confidence,
            reasoning=f"Optimal action {best_action.value} selected by ML inference engine for attempt {attempts}.",
            communication=comm,
            multi_step_plan=plan,
            requires_human_review=(best_action == RecoveryActionType.ESCALATE_TO_HUMAN)
        )
