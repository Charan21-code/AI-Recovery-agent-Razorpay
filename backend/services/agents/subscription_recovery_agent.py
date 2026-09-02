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

        # If it's early in the dunning cycle (e.g. consecutive_failures <= 2), we can just schedule a dunning step
        if context.customer_state.consecutive_failures_count <= 2:
            action = RecoveryActionType.SCHEDULE_DUNNING_STEP
            delay = predictions.optimal_delay_minutes or 1440  # 1 day by default
            
            # Create a multi-step dunning plan
            plan = MultiStepPlan(
                plan_id=f"dunning_{context.current_event.event_id[-6:]}",
                target_event_id=context.current_event.event_id,
                customer_id=context.customer_profile.customer_id,
                total_steps=3,
                steps=[
                    PlanStep(step_number=1, action=RecoveryActionType.DELAYED_RETRY, delay_minutes=delay, description="First retry attempt"),
                    PlanStep(step_number=2, action=RecoveryActionType.SEND_PAYMENT_REMINDER, channel=CommunicationChannel.EMAIL, delay_minutes=2880, description="Email reminder on day 3"),
                    PlanStep(step_number=3, action=RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE, channel=CommunicationChannel.WHATSAPP, delay_minutes=4320, description="Final warning on day 5"),
                ]
            )

            return self._create_proposal(
                context=context,
                selected_action=action,
                confidence=confidence,
                reasoning=f"Early stage subscription failure. Scheduling a dunning cycle starting with {delay}m delay.",
                multi_step_plan=plan,
            )
        
        # If consecutive failures are high, we escalate or require hard update
        comm = CommunicationPayload(
            channel=CommunicationChannel.EMAIL,
            subject="Action Required: Your subscription is paused",
            message_body=f"Hi {context.customer_profile.name}, your subscription payment has failed multiple times. Please update your payment method to avoid cancellation.",
            payment_link_url="https://rzp.io/i/sub_update"
        )
        return self._create_proposal(
            context=context,
            selected_action=RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE,
            confidence=max(confidence, 0.7),
            reasoning="High consecutive failures. Customer must update their payment method.",
            communication=comm,
        )
