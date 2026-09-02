import pytest
from backend.core.constants import PolicyVerdictStatus, RecoveryActionType, AgentType
from backend.schemas.agent import ActionProposal, MultiStepPlan, PlanStep
from backend.schemas.policy import PolicyVerdict
from backend.services.execution.executor import ActionExecutor
from backend.services.execution.scheduler import PlanScheduler

@pytest.fixture
def executor():
    return ActionExecutor()

@pytest.fixture
def scheduler():
    return PlanScheduler()

@pytest.fixture
def approved_verdict():
    return PolicyVerdict(
        verdict_id="vrd_test",
        proposal_id="prop_test",
        status=PolicyVerdictStatus.APPROVED,
        original_action=RecoveryActionType.DELAYED_RETRY,
        approved_action=RecoveryActionType.DELAYED_RETRY
    )

@pytest.fixture
def blocked_verdict():
    return PolicyVerdict(
        verdict_id="vrd_test",
        proposal_id="prop_test",
        status=PolicyVerdictStatus.BLOCKED,
        original_action=RecoveryActionType.DELAYED_RETRY,
        approved_action=RecoveryActionType.DELAYED_RETRY,
        modification_reason="Blocked by policy"
    )

@pytest.fixture
def proposal():
    return ActionProposal(
        proposal_id="prop_test",
        event_id="evt_test",
        customer_id="cust_test",
        agent_type=AgentType.PAYMENT_FAILURE,
        selected_action=RecoveryActionType.DELAYED_RETRY,
        confidence=0.85,
        reasoning="Good chance to recover",
        delay_minutes=60,
        multi_step_plan=MultiStepPlan(
            plan_id="plan_test",
            event_id="evt_test",
            target_event_id="evt_test",
            customer_id="cust_test",
            total_steps=2,
            steps=[
                PlanStep(step_number=1, action=RecoveryActionType.DELAYED_RETRY, delay_minutes=0, description="Retry 1"),
                PlanStep(step_number=2, action=RecoveryActionType.SEND_PAYMENT_REMINDER, delay_minutes=4320, description="Email warning")
            ]
        )
    )

def test_executor_skips_blocked(executor, blocked_verdict, proposal):
    result = executor.execute(blocked_verdict, proposal)
    assert result is False

def test_executor_runs_approved(executor, approved_verdict, proposal):
    result = executor.execute(approved_verdict, proposal)
    assert result is True

def test_scheduler_skips_blocked(scheduler, blocked_verdict, proposal):
    result = scheduler.schedule_plan(blocked_verdict, proposal)
    assert result is False

def test_scheduler_persists_plan(scheduler, approved_verdict, proposal):
    result = scheduler.schedule_plan(approved_verdict, proposal)
    assert result is True

def test_scheduler_skips_no_plan(scheduler, approved_verdict, proposal):
    proposal.multi_step_plan = None
    result = scheduler.schedule_plan(approved_verdict, proposal)
    assert result is False
