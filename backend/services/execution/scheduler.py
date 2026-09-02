import json
from datetime import datetime, timezone
from backend.core.logging import get_logger
from backend.schemas.agent import ActionProposal, MultiStepPlan
from backend.schemas.policy import PolicyVerdict

logger = get_logger("scheduler")


class PlanScheduler:
    """
    Manages multi-step dunning plans and long-term recovery workflows.
    Persists them to the DB so background workers can pick them up later.
    """

    def schedule_plan(self, verdict: PolicyVerdict, proposal: ActionProposal) -> bool:
        """
        Schedules a MultiStepPlan if one was provided and the verdict allows it.
        Returns True if scheduled, False otherwise.
        """
        from backend.core.constants import PolicyVerdictStatus
        
        if verdict.status == PolicyVerdictStatus.BLOCKED:
            return False
            
        if not proposal.multi_step_plan:
            return False

        plan: MultiStepPlan = proposal.multi_step_plan
        
        # Mocking database persistence
        logger.info(f"[MOCK DB] Persisting MultiStepPlan {plan.plan_id} for event {proposal.event_id}")
        logger.debug(f"[MOCK DB] Plan Details: {len(plan.steps)} steps.")
        
        for step in plan.steps:
            logger.info(f"[MOCK DB] -> Scheduled Step {step.step_number} (Delay {step.delay_minutes}m): {step.action.value}")

        return True


scheduler = PlanScheduler()
