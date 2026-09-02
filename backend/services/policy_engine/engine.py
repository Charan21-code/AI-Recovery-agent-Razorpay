import uuid
from typing import List

from backend.core.constants import PolicyVerdictStatus, RecoveryActionType
from backend.core.logging import get_logger
from backend.schemas.agent import ActionProposal
from backend.schemas.context import DecisionContext
from backend.schemas.policy import PolicyRuleCheck, PolicyVerdict

logger = get_logger("policy_engine")


class PolicyEngine:
    """
    Enforces merchant-specific limits, constraints, and business rules on agent-proposed actions.
    """

    def evaluate_proposal(self, proposal: ActionProposal, context: DecisionContext) -> PolicyVerdict:
        """
        Evaluate an ActionProposal against the MerchantPolicyContext and CustomerHistorySummary.
        """
        policy = context.policy_context
        history = context.history_summary
        
        checks: List[PolicyRuleCheck] = []
        status = PolicyVerdictStatus.APPROVED
        approved_action = proposal.selected_action
        modification_reason = None
        requires_escalation = proposal.requires_human_review

        logger.info(f"PolicyEngine evaluating proposal {proposal.proposal_id} for event {proposal.event_id}")

        # Rule 1: Opt-Out Check
        opted_out = context.customer_profile.opted_out_of_outreach
        checks.append(
            PolicyRuleCheck(
                rule_name="Communication Opt-Out",
                passed=not opted_out,
                details="Customer has opted out of all recovery communications." if opted_out else "Customer is opted in.",
                evaluated_value=str(opted_out),
                threshold_value="False",
            )
        )
        if opted_out and proposal.communication is not None:
            status = PolicyVerdictStatus.BLOCKED
            modification_reason = "Customer has opted out of communications."

        # Rule 2: Max Retries (Automated Interventions)
        attempts = history.previous_recovery_attempts
        max_attempts = policy.max_automated_interventions
        passed_attempts = attempts < max_attempts
        checks.append(
            PolicyRuleCheck(
                rule_name="Max Automated Interventions",
                passed=passed_attempts,
                details=f"Checking if previous attempts ({attempts}) < max ({max_attempts})",
                evaluated_value=str(attempts),
                threshold_value=str(max_attempts),
            )
        )
        if not passed_attempts and status != PolicyVerdictStatus.BLOCKED:
            status = PolicyVerdictStatus.BLOCKED
            modification_reason = "Exceeded maximum automated interventions limit."

        # Rule 3: Confidence Threshold
        confidence = proposal.confidence
        min_confidence = policy.min_confidence_threshold
        passed_confidence = confidence >= min_confidence
        checks.append(
            PolicyRuleCheck(
                rule_name="Minimum Confidence Threshold",
                passed=passed_confidence,
                details=f"Agent confidence ({confidence:.2f}) vs required ({min_confidence:.2f})",
                evaluated_value=f"{confidence:.2f}",
                threshold_value=f"{min_confidence:.2f}",
            )
        )
        if not passed_confidence and status != PolicyVerdictStatus.BLOCKED:
            # Low confidence doesn't necessarily mean blocked, but we escalate it
            status = PolicyVerdictStatus.ESCALATED
            requires_escalation = True
            approved_action = RecoveryActionType.ESCALATE_TO_HUMAN
            modification_reason = "Confidence score below merchant threshold. Escalating to human."

        # Rule 4: System Degradation override
        if context.is_merchant_system_degraded and approved_action == RecoveryActionType.IMMEDIATE_RETRY:
            checks.append(
                PolicyRuleCheck(
                    rule_name="System Degradation Prevention",
                    passed=False,
                    details="Preventing immediate retry during systemic degradation.",
                    evaluated_value="True",
                    threshold_value="False",
                )
            )
            status = PolicyVerdictStatus.MODIFIED
            approved_action = RecoveryActionType.DELAYED_RETRY
            modification_reason = "System degraded. Modified IMMEDIATE_RETRY to DELAYED_RETRY."

        # Rule 5: Human Escalation limits
        if attempts >= policy.human_escalation_after_attempts and not requires_escalation:
            status = PolicyVerdictStatus.MODIFIED
            approved_action = RecoveryActionType.ESCALATE_TO_HUMAN
            requires_escalation = True
            modification_reason = f"Forced escalation. Attempts ({attempts}) >= threshold ({policy.human_escalation_after_attempts})."

        # If it was already marked for escalation by the agent, make sure status reflects it
        if requires_escalation and status == PolicyVerdictStatus.APPROVED:
            status = PolicyVerdictStatus.ESCALATED
            approved_action = RecoveryActionType.ESCALATE_TO_HUMAN

        verdict = PolicyVerdict(
            verdict_id=f"vrd_{uuid.uuid4().hex[:12]}",
            proposal_id=proposal.proposal_id,
            status=status,
            original_action=proposal.selected_action,
            approved_action=approved_action,
            rules_checked=checks,
            modification_reason=modification_reason,
            requires_escalation=requires_escalation,
        )

        logger.info(f"PolicyEngine verdict: {status.value} - Action: {approved_action.value}")
        return verdict


policy_engine = PolicyEngine()
