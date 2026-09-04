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
from backend.services.execution.executor import executor
from backend.services.execution.scheduler import scheduler


# Streamlit Page Config
st.set_page_config(page_title="AI Recovery Engine", layout="wide", page_icon="⚡")

st.title("⚡ AI Revenue Recovery Engine")
st.markdown("End-to-end simulation of the intelligent recovery pipeline (Phases 1-7).")

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

st.markdown("---")
st.caption("AI Recovery Engine Demo - Internal Tooling")
