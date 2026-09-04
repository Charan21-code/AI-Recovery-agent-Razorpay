from typing import Dict, Type

from backend.core.constants import EventType, AgentType
from backend.core.logging import get_logger
from backend.schemas.agent import ActionProposal
from backend.schemas.predictions import OpportunityScore
from backend.schemas.context import DecisionContext
from backend.schemas.predictions import ModelPredictions

from backend.services.agents.base import BaseRecoveryAgent
from backend.services.agents.checkout_abandonment_agent import CheckoutAbandonmentAgent
from backend.services.agents.overdue_receivable_agent import OverdueReceivableAgent
from backend.services.agents.payment_failure_agent import PaymentFailureAgent
from backend.services.agents.subscription_recovery_agent import SubscriptionRecoveryAgent

logger = get_logger("orchestrator")


class RecoveryOrchestrator:
    """
    Central router that receives evaluated events (Context + ML Predictions + Opportunity Score)
    and dispatches them to the correct specialized agent to formulate a final ActionProposal.
    """

    def __init__(self):
        # Map event types to specific agent classes
        self._routing_table: Dict[EventType, Type[BaseRecoveryAgent]] = {
            EventType.PAYMENT_FAILED: PaymentFailureAgent,
            EventType.CHECKOUT_ABANDONED: CheckoutAbandonmentAgent,
            EventType.CHECKOUT_STARTED: CheckoutAbandonmentAgent,
            EventType.SUBSCRIPTION_PAYMENT_FAILED: SubscriptionRecoveryAgent,
            EventType.MANDATE_FAILED: SubscriptionRecoveryAgent,
            EventType.SUBSCRIPTION_CANCELLED: SubscriptionRecoveryAgent,
            EventType.SUBSCRIPTION_EXPIRED: SubscriptionRecoveryAgent,
            EventType.INVOICE_OVERDUE: OverdueReceivableAgent,
        }
        
        # Instantiate agents (they are stateless so we can reuse them)
        self._agents: Dict[AgentType, BaseRecoveryAgent] = {
            AgentType.PAYMENT_FAILURE: PaymentFailureAgent(),
            AgentType.CHECKOUT_ABANDONMENT: CheckoutAbandonmentAgent(),
            AgentType.SUBSCRIPTION_RECOVERY: SubscriptionRecoveryAgent(),
            AgentType.OVERDUE_RECEIVABLE: OverdueReceivableAgent(),
        }

    def dispatch(
        self,
        context: DecisionContext,
        predictions: ModelPredictions,
        opportunity: OpportunityScore,
    ) -> ActionProposal:
        """
        Route the event to the appropriate specialized agent and return the proposal.
        """
        event = context.current_event
        event_type = event.event_type
        
        agent_class = self._routing_table.get(event_type)
        if not agent_class:
            # Contextual fallback: detect if subscription, invoice, or checkout entity is present
            if event.subscription_id or "sub" in event.event_id:
                agent_class = SubscriptionRecoveryAgent
            elif event.invoice_id or "inv" in event.event_id:
                agent_class = OverdueReceivableAgent
            elif event.checkout_stage or "chk" in event.event_id:
                agent_class = CheckoutAbandonmentAgent
            else:
                logger.warning(f"No specialized agent mapped for event type: {event_type.value}. Using PaymentFailureAgent as fallback.")
                agent_class = PaymentFailureAgent
            
        # Get the instantiated agent
        # We can find the instance by instantiating the class to get its type, or just instantiate directly
        agent = agent_class()
        
        logger.info(
            f"Orchestrator routing event {context.current_event.event_id} "
            f"to {agent.agent_type.value}"
        )
        
        proposal = agent.handle_event(context, predictions, opportunity)
        
        logger.debug(
            f"Agent {agent.agent_type.value} proposed action: {proposal.selected_action.value} "
            f"(Confidence: {proposal.confidence:.2f})"
        )
        
        return proposal


# Singleton orchestrator for dependency injection
orchestrator = RecoveryOrchestrator()
