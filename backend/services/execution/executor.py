from backend.core.constants import PolicyVerdictStatus, RecoveryActionType
from backend.core.logging import get_logger
from backend.schemas.agent import ActionProposal
from backend.schemas.policy import PolicyVerdict

logger = get_logger("executor")


class ActionExecutor:
    """
    Executes the approved ActionProposals by interfacing with external systems.
    (Razorpay APIs, Twilio, SendGrid, etc.)
    Mocked for the MVP engine.
    """

    def execute(self, verdict: PolicyVerdict, proposal: ActionProposal) -> bool:
        """
        Execute the action if the verdict is APPROVED or MODIFIED.
        Returns True if execution was successful, False otherwise.
        """
        if verdict.status == PolicyVerdictStatus.BLOCKED:
            logger.info(f"Execution skipped for {proposal.proposal_id} - Verdict BLOCKED.")
            return False

        action_to_execute = verdict.approved_action
        logger.info(f"Executing action: {action_to_execute.value} for event {proposal.event_id}")

        if action_to_execute == RecoveryActionType.IMMEDIATE_RETRY:
            self._execute_payment_retry(proposal)
        
        elif action_to_execute == RecoveryActionType.DELAYED_RETRY:
            delay = proposal.delay_minutes or 0
            self._queue_delayed_retry(proposal, delay)
            
        elif action_to_execute == RecoveryActionType.GENERATE_PAYMENT_LINK:
            self._send_communication(proposal, "PAYMENT_LINK")
            
        elif action_to_execute == RecoveryActionType.SEND_PERSONALIZED_MESSAGE:
            self._send_communication(proposal, "WHATSAPP")
            
        elif action_to_execute == RecoveryActionType.SEND_PAYMENT_REMINDER:
            self._send_communication(proposal, "EMAIL")
            
        elif action_to_execute == RecoveryActionType.ESCALATE_TO_HUMAN:
            self._escalate_to_human(proposal, verdict.modification_reason)
            
        elif action_to_execute in [RecoveryActionType.STOP, RecoveryActionType.WAIT]:
            logger.info("No action required.")
            
        else:
            logger.warning(f"Unknown action type: {action_to_execute}")
            return False

        return True

    def _execute_payment_retry(self, proposal: ActionProposal):
        # Mocking an actual Razorpay API call
        logger.info(f"[MOCK API] Triggering immediate payment retry for customer {proposal.customer_id}")

    def _queue_delayed_retry(self, proposal: ActionProposal, delay_minutes: int):
        # Mocking a message queue push (e.g. SQS, Celery, Redis)
        logger.info(f"[MOCK QUEUE] Queuing retry for customer {proposal.customer_id} in {delay_minutes} minutes")

    def _send_communication(self, proposal: ActionProposal, channel: str):
        # Mocking SendGrid / Twilio
        if proposal.communication:
            msg = proposal.communication.message_body
            lang = proposal.communication.language.value
            logger.info(f"[MOCK {channel}] Sending message to {proposal.customer_id} ({lang}): {msg}")
        else:
            logger.error(f"Cannot send {channel} communication, missing payload.")

    def _escalate_to_human(self, proposal: ActionProposal, reason: str = None):
        # Mocking a ticketing system (e.g. Zendesk, Jira)
        reason_str = reason or proposal.reasoning
        logger.info(f"[MOCK ZENDESK] Creating ticket for customer {proposal.customer_id}. Reason: {reason_str}")


executor = ActionExecutor()
