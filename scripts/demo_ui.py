import sys
import os
from datetime import datetime, timezone
import json
import pandas as pd
import streamlit as st

# Add the root directory to PYTHONPATH so backend imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.core.constants import EventType, PolicyVerdictStatus
from backend.services.normalization.normalizer import normalize_razorpay_event
from backend.schemas.context import CustomerHistorySummary, DecisionContext, MerchantPolicyContext
from backend.schemas.customer import CustomerProfile, CustomerState
from backend.services.ml.predictor import recovery_predictor
from backend.services.ml.opportunity_scorer import opportunity_scorer
from backend.services.agents.orchestrator import orchestrator
from backend.services.policy_engine.engine import policy_engine
import importlib
from backend.services.execution.executor import executor
from backend.services.execution.scheduler import scheduler
from backend.db.base import Base
from backend.db.session import SyncSessionLocal, sync_engine
from backend.schemas.outcomes import RecoveryOutcome
from backend.services.outcomes.outcome_processor import outcome_processor
from backend.services.outcomes.audit_trail import audit_trail_service
from backend.services.outcomes.revenue_calculator import revenue_calculator
from backend.services.feedback import feedback_store, bandit_learner
from backend.services.features.feature_engine import feature_engine

# Ensure SQLite tables exist for live audit logs and state
Base.metadata.create_all(bind=sync_engine)

# Streamlit Page Config
st.set_page_config(page_title="AI Recovery Engine", layout="wide", page_icon="⚡")

st.title("⚡ AI Revenue Recovery Engine")
st.markdown("End-to-end simulation of the intelligent recovery pipeline (Phases 1-10: Ingestion → Context → ML → Agents → Policy → Execution → Outcome & Audit → Feedback & Learning).")

# Sidebar: Simulation Controls
st.sidebar.header("🔧 Simulation Controls")

event_type_selection = st.sidebar.selectbox(
    "Simulated Event Scenario",
    [
        "Payment Failed - Transient Bank Timeout",
        "Payment Failed - Insufficient Funds",
        "Payment Failed - Card Expired / Declined",
        "Payment Failed - 3DS / Authentication Failure",
        "Checkout Abandoned (Cart Drop-off)",
        "Subscription Payment Failed (Mandate Halted)",
        "Invoice Overdue (High Value B2B)",
    ]
)

previous_attempts = st.sidebar.slider(
    "Previous Recovery Attempts",
    min_value=0,
    max_value=5,
    value=0,
    help="Simulates how many automated recovery cycles have already been attempted for this customer."
)

customer_opt_out = st.sidebar.checkbox("Customer Opted-Out of Comms?", value=False)
is_vip_customer = st.sidebar.checkbox("Customer VIP Status?", value=False)
system_degradation = st.sidebar.checkbox("Trigger Gateway System Degradation?", value=False)

simulated_outcome_choice = st.sidebar.selectbox(
    "Phase 9: Simulated Outcome",
    [
        "Success: Payment Recovered (Customer Paid in Full)",
        "Failure: Customer Unresponsive / Retry Failed",
    ],
    help="Simulates the real-world outcome observed after the action is executed."
)

if st.sidebar.button("🚀 Process Event Pipeline", type="primary"):
    
    st.markdown("---")
    
    # 1. GENERATE RAW PAYLOAD
    with st.expander("Step 1: Event Ingestion & Normalization", expanded=True):
        st.write("Receiving raw webhook payload from Razorpay...")
        
        raw_payload = {
            "id": "evt_sim_" + datetime.now().strftime("%H%M%S"),
            "created_at": int(datetime.now().timestamp()),
            "attempt_count": previous_attempts + 1
        }
        
        if event_type_selection == "Payment Failed - Transient Bank Timeout":
            raw_payload["event"] = "payment.failed"
            raw_payload["payload"] = {
                "payment": {
                    "entity": {
                        "id": "pay_test_" + datetime.now().strftime("%H%M%S"),
                        "amount": 499900,  # Rs. 4,999
                        "currency": "INR",
                        "method": "upi",
                        "error_code": "GATEWAY_TIMEOUT",
                        "error_description": "Bank Timeout / Server Busy",
                        "contact": "+919876543210",
                        "email": "test@example.com"
                    }
                }
            }
        elif event_type_selection == "Payment Failed - Insufficient Funds":
            raw_payload["event"] = "payment.failed"
            raw_payload["payload"] = {
                "payment": {
                    "entity": {
                        "id": "pay_test_" + datetime.now().strftime("%H%M%S"),
                        "amount": 250000,  # Rs. 2,500
                        "currency": "INR",
                        "method": "card",
                        "error_code": "BAD_REQUEST_ERROR",
                        "error_description": "Insufficient Funds in Account",
                        "contact": "+919876543210",
                        "email": "test@example.com"
                    }
                }
            }
        elif event_type_selection == "Payment Failed - Card Expired / Declined":
            raw_payload["event"] = "payment.failed"
            raw_payload["payload"] = {
                "payment": {
                    "entity": {
                        "id": "pay_test_" + datetime.now().strftime("%H%M%S"),
                        "amount": 199900,  # Rs. 1,999
                        "currency": "INR",
                        "method": "card",
                        "error_code": "CARD_DECLINED",
                        "error_description": "Card Expired or Blocked by Issuing Bank",
                        "contact": "+919876543210",
                        "email": "test@example.com"
                    }
                }
            }
        elif event_type_selection == "Payment Failed - 3DS / Authentication Failure":
            raw_payload["event"] = "payment.failed"
            raw_payload["payload"] = {
                "payment": {
                    "entity": {
                        "id": "pay_test_" + datetime.now().strftime("%H%M%S"),
                        "amount": 150000,  # Rs. 1,500
                        "currency": "INR",
                        "method": "card",
                        "error_code": "AUTH_FAILED",
                        "error_description": "OTP Expired or Authentication Failed",
                        "contact": "+919876543210",
                        "email": "test@example.com"
                    }
                }
            }
        elif event_type_selection == "Checkout Abandoned (Cart Drop-off)":
            raw_payload["event"] = "checkout.abandoned"
            raw_payload["payload"] = {
                "checkout": {
                    "entity": {
                        "id": "chk_test_" + datetime.now().strftime("%H%M%S"),
                        "amount": 349900,  # Rs. 3,499
                        "currency": "INR",
                        "contact": "+919876543210",
                        "email": "test@example.com"
                    }
                }
            }
        elif event_type_selection == "Subscription Payment Failed (Mandate Halted)":
            raw_payload["event"] = "subscription.charged.failed"
            raw_payload["payload"] = {
                "subscription": {
                    "entity": {
                        "id": "sub_test_" + datetime.now().strftime("%H%M%S"),
                        "customer_id": "cust_sub_101",
                        "error_code": "MANDATE_REJECTED",
                        "error_description": "Auto-debit recurring mandate rejected"
                    }
                },
                "payment": {
                    "entity": {
                        "amount": 99900,  # Rs. 999
                        "currency": "INR",
                        "method": "card"
                    }
                }
            }
        elif event_type_selection == "Invoice Overdue (High Value B2B)":
            raw_payload["event"] = "invoice.overdue"
            raw_payload["payload"] = {
                "invoice": {
                    "entity": {
                        "id": "inv_test_" + datetime.now().strftime("%H%M%S"),
                        "customer_id": "cust_b2b_enterprise",
                        "amount": 15000000,  # Rs. 1,50,000 (1.5 Lakhs)
                        "currency": "INR",
                        "contact": "+919876543210",
                        "email": "finance@enterprise.com"
                    }
                }
            }
            
        st.json(raw_payload)
        
        normalized_event = normalize_razorpay_event(raw_payload)
        col_norm1, col_norm2, col_norm3 = st.columns(3)
        col_norm1.success(f"**Normalized Event:** `{normalized_event.event_type.value}`")
        col_norm2.info(f"**Failure Category:** `{normalized_event.failure_category.value}`")
        col_norm3.metric("Amount at Risk", f"₹{normalized_event.amount:,.2f}")

    # 2. CONTEXT BUILDING
    with st.expander("Step 2: Context Building & Enrichment"):
        st.write("Querying mock databases for customer state, historical fatigue, and merchant policies...")
        
        fatigue_score = min(1.0, previous_attempts * 0.22)
        
        context = DecisionContext(
            context_id=f"ctx_{normalized_event.event_id}",
            as_of_timestamp=datetime.now(timezone.utc),
            current_event=normalized_event,
            customer_profile=CustomerProfile(
                customer_id=normalized_event.customer_id or "cust_default",
                name="Test Customer",
                is_vip=is_vip_customer,
                opted_out_of_outreach=customer_opt_out
            ),
            customer_state=CustomerState(
                customer_id=normalized_event.customer_id or "cust_default",
                total_transactions=10,
                successful_transactions=8,
                failed_transactions=2 + previous_attempts,
                success_rate=0.8,
                total_recovery_attempts=previous_attempts,
                consecutive_failures_count=previous_attempts,
                recent_intervention_count=previous_attempts,
                intervention_fatigue_score=fatigue_score,
                estimated_clv=50000.0,
            ),
            history_summary=CustomerHistorySummary(
                total_transactions=10,
                successful_transactions=8,
                failed_transactions=2 + previous_attempts,
                success_rate=0.8,
                previous_recovery_attempts=previous_attempts,
                consecutive_failures_count=previous_attempts,
                intervention_fatigue_score=fatigue_score,
                historical_recovery_rate=0.5 if previous_attempts > 0 else 0.0
            ),
            policy_context=MerchantPolicyContext(
                max_automated_interventions=3,
                min_confidence_threshold=0.6,
                human_escalation_after_attempts=3
            ),
            revenue_at_risk=normalized_event.amount,
            is_merchant_system_degraded=system_degradation
        )
        
        st.json(context.model_dump(mode='json'))

    # 3. ML PREDICTIONS
    with st.expander("Step 3: Machine Learning Inference", expanded=True):
        predictions = recovery_predictor.predict_actions(context)
        opportunity = opportunity_scorer.score_opportunity(context, predictions)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Recovery Propensity", f"{predictions.overall_recovery_propensity * 100:.1f}%")
        col2.metric("Optimal Delay", f"{predictions.optimal_delay_minutes} mins")
        col3.metric("Opportunity Score", f"{opportunity.score:.1f}")
        col4.metric("Priority Level", opportunity.priority_level)
        
        st.write("### Candidate Actions & Expected Value Breakdown")
        
        # Build tabular comparison of all candidate actions
        table_rows = []
        for act_name, pred in predictions.action_predictions.items():
            table_rows.append({
                "Candidate Action": act_name,
                "P(Recovery)": f"{pred.recovery_probability * 100:.1f}%",
                "Est. Cost (₹)": f"₹{pred.estimated_intervention_cost:.2f}",
                "E[Recovery] (₹)": f"₹{pred.expected_recovery_value:,.2f}",
                "Net E[V] (₹)": f"₹{pred.net_expected_value:,.2f}",
                "Confidence": f"{pred.confidence_score:.2f}",
                "Delay": f"{pred.recommended_delay_minutes}m"
            })
            
        df = pd.DataFrame(table_rows)
        st.dataframe(df, use_container_width=True)
        st.caption(f"Best Candidate Action Selected: **{predictions.best_candidate_action.value}** (Net E[V]: ₹{predictions.best_expected_value:,.2f})")

    # 4. AGENT ORCHESTRATION
    with st.expander("Step 4: Multi-Agent Orchestration", expanded=True):
        st.write("Routing event to specialized AI agents...")
        
        proposal = orchestrator.dispatch(context, predictions, opportunity)
        
        st.success(f"**Routed to:** `{proposal.agent_type.value}`")
        st.info(f"**Proposed Action:** `{proposal.selected_action.value}` (Confidence: {proposal.confidence:.2f})")
        st.write(f"**Reasoning:** {proposal.reasoning}")
        
        if proposal.communication:
            st.write("**Communication Payload:**")
            st.json(proposal.communication.model_dump(mode='json'))
            
        if proposal.multi_step_plan:
            st.write("**Multi-Step Plan Generated:**")
            for step in proposal.multi_step_plan.steps:
                chan_str = f" via {step.channel.value}" if step.channel else ""
                st.write(f"- **Step {step.step_number}:** `{step.action.value}`{chan_str} (Delay: {step.delay_minutes}m) — {step.description}")

    # 5. POLICY ENGINE
    with st.expander("Step 5: Policy Engine Validation", expanded=True):
        st.write("Enforcing merchant rules, attempt thresholds, and opt-out limits...")
        
        verdict = policy_engine.evaluate_proposal(proposal, context)
        
        if verdict.status == PolicyVerdictStatus.APPROVED:
            st.success(f"Verdict: **{verdict.status.value}**")
        elif verdict.status == PolicyVerdictStatus.BLOCKED:
            st.error(f"Verdict: **{verdict.status.value}**")
        else:
            st.warning(f"Verdict: **{verdict.status.value}**")
            
        st.write(f"**Final Approved Action:** `{verdict.approved_action.value}`")
        if verdict.modification_reason:
            st.write(f"**Modification Reason:** {verdict.modification_reason}")
            
        st.write("### Rules Evaluated")
        for rule in verdict.rules_checked:
            if rule.passed:
                st.write(f"✅ **{rule.rule_name}**: {rule.details}")
            else:
                st.write(f"❌ **{rule.rule_name}**: {rule.details}")

    # 6. EXECUTION LAYER
    with st.expander("Step 6: Execution Layer"):
        st.write("Executing final approved actions (Mock API calls)...")
        
        exec_success = executor.execute(verdict, proposal)
        if exec_success:
            st.success("Action Executor: Execution logic triggered successfully (see console logs for MOCK API calls).")
        else:
            st.warning("Action Executor: Execution skipped or blocked.")
            
        if proposal.multi_step_plan:
            plan_success = scheduler.schedule_plan(verdict, proposal)
            if plan_success:
                st.success("Plan Scheduler: Multi-step plan persisted to DB successfully.")
            else:
                st.warning("Plan Scheduler: Plan scheduling skipped or blocked.")

    # 7. OUTCOME PROCESSING & AUDIT TRAIL (PHASE 9)
    with st.expander("Step 7: Outcome Processing & Audit Trail (Phase 9)", expanded=True):
        st.write("Observing recovery outcome, updating live customer state, and compiling immutable audit trail...")

        db_session = SyncSessionLocal()
        try:
            # Record audit steps for this run
            audit_trail_service.record_entry(
                session=db_session,
                event_id=normalized_event.event_id,
                stage="INGESTION",
                actor="EventIngestion",
                action="NORMALIZE_EVENT",
                details={
                    "event_type": normalized_event.event_type.value,
                    "amount": normalized_event.amount,
                    "failure_category": normalized_event.failure_category.value,
                },
            )
            audit_trail_service.record_entry(
                session=db_session,
                event_id=normalized_event.event_id,
                stage="PREDICTION",
                actor="MLInferenceEngine",
                action="PREDICT_ACTIONS",
                details={
                    "best_action": predictions.best_candidate_action.value,
                    "propensity": f"{predictions.overall_recovery_propensity * 100:.1f}%",
                    "optimal_delay": f"{predictions.optimal_delay_minutes}m",
                },
            )
            audit_trail_service.record_entry(
                session=db_session,
                event_id=normalized_event.event_id,
                stage="PROPOSAL",
                actor=proposal.agent_type.value,
                action=proposal.selected_action.value,
                details={"confidence": proposal.confidence, "reasoning": proposal.reasoning},
                decision_id=proposal.proposal_id,
            )
            audit_trail_service.record_entry(
                session=db_session,
                event_id=normalized_event.event_id,
                stage="POLICY_CHECK",
                actor="PolicyEngine",
                action=verdict.status.value,
                details={"approved_action": verdict.approved_action.value},
                verdict_id=verdict.verdict_id,
            )
            audit_trail_service.record_entry(
                session=db_session,
                event_id=normalized_event.event_id,
                stage="EXECUTION",
                actor="ActionExecutor",
                action=verdict.approved_action.value,
                details={"status": "DISPATCHED" if exec_success else "BLOCKED_OR_SKIPPED"},
            )

            is_success_outcome = "Success" in simulated_outcome_choice
            outcome_obj = RecoveryOutcome(
                outcome_id=f"out_{datetime.now().strftime('%H%M%S')}_{context.current_event.event_id[-4:]}",
                execution_id=f"exec_{context.current_event.event_id[-6:]}",
                event_id=context.current_event.event_id,
                customer_id=context.customer_profile.customer_id,
                outcome_type=EventType.RECOVERY_SUCCESS if is_success_outcome else EventType.RECOVERY_FAILED,
                recovered_amount=normalized_event.amount if is_success_outcome else 0.0,
                currency=normalized_event.currency,
                time_to_recovery_seconds=120.0 if is_success_outcome else None,
                is_success=is_success_outcome,
                raw_details={"simulated": True, "scenario": simulated_outcome_choice},
                observed_at=datetime.now(timezone.utc),
            )

            try:
                summary, reward = outcome_processor.process_outcome(
                    session=db_session,
                    outcome=outcome_obj,
                    action_executed=verdict.approved_action,
                    order_id=normalized_event.order_id,
                    payment_id=normalized_event.payment_id,
                    context=context,
                    agent_type=proposal.agent_type,
                )
            except TypeError:
                summary, reward = outcome_processor.process_outcome(
                    session=db_session,
                    outcome=outcome_obj,
                    action_executed=verdict.approved_action,
                    order_id=normalized_event.order_id,
                    payment_id=normalized_event.payment_id,
                )
                feedback_store.record_learning_event(
                    session=db_session,
                    context=context,
                    action_taken=verdict.approved_action,
                    outcome=outcome_obj,
                    reward=reward,
                    agent_type=proposal.agent_type,
                )

            # Display Financial Summary
            st.subheader("💰 Revenue & Reward Accounting")
            col_rev1, col_rev2, col_rev3, col_rev4 = st.columns(4)
            col_rev1.metric("Outcome Status", "✅ RECOVERED" if is_success_outcome else "❌ FAILED")
            col_rev2.metric("Gross Recovered", f"₹{reward.recovered_revenue:,.2f}")
            col_rev3.metric("Intervention Cost", f"₹{reward.intervention_cost:,.2f}")
            col_rev4.metric("Net Recovered Value", f"₹{reward.net_reward:,.2f}")

            # Display State Evolution
            st.subheader("🔄 Chronological Customer State Update")
            state_df = pd.DataFrame([
                {
                    "Metric": "Total Revenue Generated",
                    "Before Outcome": f"₹{summary.previous_total_revenue:,.2f}",
                    "After Outcome": f"₹{summary.updated_total_revenue:,.2f}",
                },
                {
                    "Metric": "Historical Recovery Rate",
                    "Before Outcome": f"{summary.previous_recovery_rate * 100:.1f}%",
                    "After Outcome": f"{summary.updated_recovery_rate * 100:.1f}%",
                },
                {
                    "Metric": "Intervention Fatigue Score",
                    "Before Outcome": f"{context.customer_state.intervention_fatigue_score:.2f}",
                    "After Outcome": f"{summary.updated_fatigue_score:.2f}",
                },
            ])
            st.table(state_df)

            # Display Chronological Audit Trail
            st.subheader("📜 Complete Chronological Audit Trail")
            timeline = audit_trail_service.format_readable_timeline(db_session, normalized_event.event_id)
            for item in timeline:
                st.markdown(
                    f"**`{item['time']}`** — **[{item['stage']}]** `{item['actor']}`: "
                    f"**{item['action']}**  \n"
                    f"&nbsp;&nbsp;&nbsp;&nbsp;↳ *Details:* `{json.dumps(item['details'])}`"
                )
        finally:
            db_session.close()

    # 8. CLOSED-LOOP FEEDBACK & LEARNING (PHASE 10)
    with st.expander("Step 8: Closed-Loop Feedback & Learning System (Phase 10)", expanded=True):
        st.write("Capturing learning tuple ⟨Context, Action, Outcome, Reward⟩ and updating contextual bandit payoffs...")

        db_session = SyncSessionLocal()
        try:
            # Query recent feedback events summary
            fb_summary = feedback_store.get_feedback_summary(db_session)
            col_fb1, col_fb2, col_fb3, col_fb4 = st.columns(4)
            col_fb1.metric("Total Learning Events", fb_summary["total_events"])
            col_fb2.metric("Total Revenue Logged", f"₹{fb_summary['total_recovered_revenue']:,.2f}")
            col_fb3.metric("Cumulative Net Reward", f"₹{fb_summary['total_net_reward']:,.2f}")
            col_fb4.metric("Avg Conversion Rate", f"{fb_summary['overall_conversion_rate'] * 100:.1f}%")

            st.write("#### 🧩 Current Learning Tuple Stored")
            tuple_col1, tuple_col2 = st.columns([1, 1])
            with tuple_col1:
                st.info(
                    f"**Action Taken:** `{verdict.approved_action.value}`  \n"
                    f"**Outcome Status:** `{outcome_obj.outcome_type.value}`  \n"
                    f"**Net Economic Reward:** `₹{reward.net_reward:,.2f}`  \n"
                    f"**Model / Policy Version:** `v1.0` / `v1.0`"
                )
            with tuple_col2:
                with st.expander("Inspected Context Vector (20 signals)"):
                    st.json(feature_engine.extract_features(context))

            st.write("#### 🎰 Contextual Bandit Exploration / Exploitation Payoffs (Section 41)")
            bandit_stats = bandit_learner.get_action_performance_table(db_session)
            if bandit_stats:
                st.dataframe(pd.DataFrame(bandit_stats), use_container_width=True)
            else:
                st.caption("No historical pulls recorded yet. Process multiple simulated events to build bandit profiles.")

            st.caption("🛡️ **Safety Guarantee (Section 40):** The learning system evaluates candidate action payoffs and policy versions; hard merchant policy constraints and opt-outs are strictly non-negotiable and cannot be bypassed.")
        finally:
            db_session.close()

st.markdown("---")
st.caption("AI Recovery Engine Demo - Internal Tooling")
