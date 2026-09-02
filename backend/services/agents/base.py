"""
Base class for all recovery agents.
"""

from abc import ABC, abstractmethod
import uuid
from typing import Optional

from backend.core.constants import AgentType, RecoveryActionType
from backend.core.logging import get_logger
from backend.schemas.agent import ActionProposal
from backend.schemas.context import DecisionContext
from backend.schemas.predictions import ModelPredictions
from backend.schemas.predictions import OpportunityScore

logger = get_logger("agents")


class BaseRecoveryAgent(ABC):
    """
    Abstract base class defining the standard interface for all specialized recovery agents.
    """

    @property
    @abstractmethod
    def agent_type(self) -> AgentType:
        """The type of this agent."""
        pass

    @abstractmethod
    def handle_event(
        self,
        context: DecisionContext,
        predictions: ModelPredictions,
        opportunity: OpportunityScore,
    ) -> ActionProposal:
        """
        Evaluate the context, predictions, and opportunity to formulate a recovery proposal.
        """
        pass

    def _create_proposal(
        self,
        context: DecisionContext,
        selected_action: RecoveryActionType,
        confidence: float,
        reasoning: str,
        requires_human_review: bool = False,
        **kwargs
    ) -> ActionProposal:
        """
        Helper method to construct a standard ActionProposal.
        """
        return ActionProposal(
            proposal_id=f"prop_{uuid.uuid4().hex[:12]}",
            agent_type=self.agent_type,
            event_id=context.current_event.event_id,
            customer_id=context.current_event.customer_id,
            selected_action=selected_action,
            confidence=confidence,
            reasoning=reasoning,
            requires_human_review=requires_human_review,
            **kwargs
        )
