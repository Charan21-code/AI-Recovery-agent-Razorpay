"""
====================================================================
  Revenue Recovery Intelligence Engine -- Live Pipeline Demo
  Simulates a realistic Razorpay payment failure -> recovery flow
====================================================================
"""

import sys
import os
import io
import time
from datetime import datetime, timezone, timedelta

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db.init_db import init_sync_db, drop_sync_db
from backend.db.session import SyncSessionLocal
from backend.schemas.events import NormalizedEvent
from backend.core.constants import EventType, FailureCategory, RecoveryActionType
from backend.services.state.state_store import state_store
from backend.services.context.context_builder import context_builder
from backend.services.features.feature_engine import feature_engine
from backend.services.features.degradation_detector import degradation_detector
from backend.services.ml.predictor import recovery_predictor
from backend.services.ml.opportunity_scorer import opportunity_scorer
from backend.services.ml.timing_optimizer import timing_optimizer


# -- Helpers ---------------------------------------------------------------

CYAN    = "\033[96m"
GREEN   = "\033[92m"
YELLOW  = "\033[93m"
RED     = "\033[91m"
MAGENTA = "\033[95m"
BOLD    = "\033[1m"
DIM     = "\033[2m"
RESET   = "\033[0m"

def banner(text):
    width = 72
    print(f"\n{CYAN}{'=' * width}")
    print(f"  {BOLD}{text}{RESET}{CYAN}")
    print(f"{'=' * width}{RESET}\n")

def section(text):
    dashes = '-' * max(1, 55 - len(text))
    print(f"\n{YELLOW}-- {BOLD}{text}{RESET}{YELLOW} {dashes}{RESET}\n")

def kv(key, value, indent=2):
    print(f"{' ' * indent}{DIM}{key}:{RESET} {BOLD}{value}{RESET}")

def pause(msg="Press Enter to continue to next stage..."):
    pass


# -- Main Demo -------------------------------------------------------------

def main():
    banner("REVENUE RECOVERY INTELLIGENCE ENGINE -- LIVE DEMO")
    print(f"  This demo simulates a customer's journey through the full pipeline:")
    print(f"  {GREEN}1.{RESET} Webhook Event Ingestion & Normalization")
    print(f"  {GREEN}2.{RESET} Chronological State Store (rolling customer metrics)")
    print(f"  {GREEN}3.{RESET} Temporal Context Builder (zero future leakage)")
    print(f"  {GREEN}4.{RESET} Feature Engineering (20-dim vector)")
    print(f"  {GREEN}5.{RESET} Degradation Detection (systemic vs customer failure)")
    print(f"  {GREEN}6.{RESET} ML Prediction (P(recovery|action) for 9 actions)")
    print(f"  {GREEN}7.{RESET} Opportunity Scoring & Priority Ranking")
    print()

    # Initialize fresh DB
    drop_sync_db()
    init_sync_db()
    print(f"  {GREEN}[OK]{RESET} Fresh SQLite database initialized\n")

    # --- Scenario: Customer "Priya Sharma" has 3 events over time ---
    base_time = datetime(2026, 8, 31, 10, 0, 0, tzinfo=timezone(timedelta(hours=5, minutes=30)))

    events = [
        NormalizedEvent(
            event_id="evt_pay_success_001",
            customer_id="cust_priya_sharma",
            customer_name="Priya Sharma",
            customer_email="priya@example.com",
            customer_phone="+919876543210",
            event_type=EventType.PAYMENT_SUCCESS,
            amount=2499.00,
            currency="INR",
            payment_method="upi",
            timestamp=base_time,
        ),
        NormalizedEvent(
            event_id="evt_pay_success_002",
            customer_id="cust_priya_sharma",
            customer_name="Priya Sharma",
            event_type=EventType.PAYMENT_SUCCESS,
            amount=1299.00,
            currency="INR",
            payment_method="card",
            timestamp=base_time + timedelta(days=3),
        ),
        NormalizedEvent(
            event_id="evt_pay_fail_001",
            customer_id="cust_priya_sharma",
            customer_name="Priya Sharma",
            customer_email="priya@example.com",
            customer_phone="+919876543210",
            event_type=EventType.PAYMENT_FAILED,
            amount=4999.00,
            currency="INR",
            payment_method="upi",
            failure_code="BANK_TIMEOUT",
            failure_category=FailureCategory.TRANSIENT_BANK_TIMEOUT,
            timestamp=base_time + timedelta(days=7),
        ),
    ]

    failure_event = events[2]
    as_of = failure_event.timestamp

    pause("Press Enter to start the demo...")

    # ===================================================================
    # STAGE 1: Event Ingestion
    # ===================================================================
    section("STAGE 1: Event Ingestion & Normalization")
    print(f"  Simulating 3 Razorpay webhook events for customer {BOLD}Priya Sharma{RESET}:\n")

    with SyncSessionLocal() as session:
        for i, evt in enumerate(events):
            state_store.record_normalized_event(session, evt)
            icon = f"{GREEN}[OK]{RESET}" if evt.event_type == EventType.PAYMENT_SUCCESS else f"{RED}[FAIL]{RESET}"
            print(f"    {icon}  Event {i+1}: {BOLD}{evt.event_type.value}{RESET}")
            kv("event_id", evt.event_id, indent=8)
            kv("amount", f"Rs.{evt.amount:,.2f}", indent=8)
            kv("method", evt.payment_method or "-", indent=8)
            kv("failure", evt.failure_category.value if evt.failure_category else "-", indent=8)
            kv("timestamp", evt.timestamp.strftime("%Y-%m-%d %H:%M IST"), indent=8)
            print()
            time.sleep(0.3)

    pause("Press Enter to see the Customer State Store...")

    # ===================================================================
    # STAGE 2: State Store
    # ===================================================================
    section("STAGE 2: Chronological State Store")
    print(f"  Rolling metrics computed from {BOLD}all events up to the failure{RESET}:\n")

    with SyncSessionLocal() as session:
        state = state_store.get_customer_state_as_of(session, "cust_priya_sharma", as_of)
        kv("customer_id", state.customer_id)
        kv("total_transactions", state.total_transactions)
        kv("successful_transactions", state.successful_transactions)
        kv("failed_transactions", state.failed_transactions)
        kv("success_rate", f"{state.success_rate:.1%}")
        kv("total_revenue", f"Rs.{state.total_revenue_generated:,.2f}")
        kv("consecutive_failures", state.consecutive_failures_count)
        kv("intervention_fatigue", f"{state.intervention_fatigue_score:.2f}")
        kv("historical_recovery_rate", f"{state.historical_recovery_rate:.2f}")

    pause("Press Enter to see the Decision Context...")

    # ===================================================================
    # STAGE 3: Context Builder
    # ===================================================================
    section("STAGE 3: Temporal Decision Context (Zero Leakage)")
    print(f"  Building context for the {RED}failed payment{RESET} event:\n")

    with SyncSessionLocal() as session:
        ctx = context_builder.build_context(session, failure_event)

        kv("context_id", ctx.context_id)
        kv("as_of_timestamp", ctx.as_of_timestamp.strftime("%Y-%m-%d %H:%M IST"))
        kv("revenue_at_risk", f"Rs.{ctx.revenue_at_risk:,.2f}")
        kv("is_degraded", ctx.is_merchant_system_degraded)
        print()
        print(f"    {MAGENTA}Customer Profile:{RESET}")
        kv("name", ctx.customer_profile.name, indent=6)
        kv("is_vip", ctx.customer_profile.is_vip, indent=6)
        kv("lifetime_value", f"Rs.{ctx.customer_state.estimated_clv:,.2f}", indent=6)

        print()
        print(f"    {MAGENTA}Current Event:{RESET}")
        kv("type", ctx.current_event.event_type.value, indent=6)
        kv("failure_category", ctx.current_event.failure_category.value, indent=6)
        kv("amount", f"Rs.{ctx.current_event.amount:,.2f}", indent=6)

    pause("Press Enter to see Feature Engineering...")

    # ===================================================================
    # STAGE 4: Feature Engineering
    # ===================================================================
    section("STAGE 4: Feature Engineering (20-Dimensional Vector)")

    with SyncSessionLocal() as session:
        ctx = context_builder.build_context(session, failure_event)

        features = feature_engine.extract_features(ctx)
        vector = feature_engine.extract_feature_vector(ctx)

        print(f"  {BOLD}Named Features:{RESET}\n")
        for name, val in sorted(features.items()):
            bar_len = min(40, int(abs(val) * 4)) if abs(val) <= 10 else min(40, int(abs(val) / 100))
            bar = "#" * max(1, bar_len)
            print(f"    {name:.<40s} {val:>10.4f}  {GREEN}{bar}{RESET}")

        print(f"\n  {BOLD}NumPy Vector Shape:{RESET} {vector.shape}")
        print(f"  {BOLD}Vector (first 10):{RESET}  {vector[:10]}")

    pause("Press Enter to see Degradation Detection...")

    # ===================================================================
    # STAGE 5: Degradation Detection
    # ===================================================================
    section("STAGE 5: Merchant System Degradation Detection")

    with SyncSessionLocal() as session:
        ctx = context_builder.build_context(session, failure_event)
        is_degraded = ctx.is_merchant_system_degraded

        if is_degraded:
            print(f"  {RED}!!  DEGRADATION DETECTED{RESET}")
            print(f"  System-wide failure spike detected -- recovery actions may be futile.")
        else:
            print(f"  {GREEN}[OK]  No systemic degradation detected{RESET}")
            print(f"  Failure appears to be customer/bank-specific, not merchant-wide.")

    pause("Press Enter to see ML Predictions...")

    # ===================================================================
    # STAGE 6: ML Recovery Predictions
    # ===================================================================
    section("STAGE 6: ML Recovery Predictions -- P(recovery | action)")

    with SyncSessionLocal() as session:
        ctx = context_builder.build_context(session, failure_event)

        predictions = recovery_predictor.predict_actions(ctx)

        kv("prediction_id", predictions.prediction_id)
        kv("model_version", predictions.model_version)
        kv("overall_propensity", f"{predictions.overall_recovery_propensity:.2%}")
        kv("optimal_delay", f"{predictions.optimal_delay_minutes} minutes")
        print()

        print(f"  {BOLD}Action-by-Action Predictions:{RESET}\n")
        print(f"    {'ACTION':<35s} {'P(rec)':<10s} {'E[V] Rs.':<12s} {'Cost Rs.':<10s} {'Net E[V]':<12s}")
        print(f"    {'-' * 79}")

        sorted_actions = sorted(
            predictions.action_predictions.values(),
            key=lambda a: a.net_expected_value,
            reverse=True,
        )
        for act in sorted_actions:
            is_best = act.action == predictions.best_candidate_action
            prefix = f"{GREEN}*{RESET}" if is_best else " "
            color = GREEN if is_best else ""
            reset = RESET if is_best else ""
            print(
                f"  {prefix} {color}{act.action.value:<34s} "
                f"{act.recovery_probability:>7.2%}   "
                f"Rs.{act.expected_recovery_value:>9,.2f}  "
                f"Rs.{act.estimated_intervention_cost:>7.2f}  "
                f"Rs.{act.net_expected_value:>9,.2f}{reset}"
            )

        print(f"\n  {GREEN}* = Best candidate action: {BOLD}{predictions.best_candidate_action.value}{RESET}")
        print(f"    {BOLD}Best Net Expected Value: Rs.{predictions.best_expected_value:,.2f}{RESET}")

    pause("Press Enter to see Opportunity Scoring...")

    # ===================================================================
    # STAGE 7: Opportunity Scoring
    # ===================================================================
    section("STAGE 7: Opportunity Scoring & Priority Ranking")

    with SyncSessionLocal() as session:
        ctx = context_builder.build_context(session, failure_event)
        predictions = recovery_predictor.predict_actions(ctx)
        opp = opportunity_scorer.score_opportunity(ctx, predictions)

        priority_colors = {
            "CRITICAL": RED,
            "HIGH": YELLOW,
            "MEDIUM": CYAN,
            "LOW": DIM,
        }
        p_color = priority_colors.get(opp.priority_level, "")

        kv("opportunity_id", opp.opportunity_id)
        kv("customer", f"{opp.customer_name} ({opp.customer_id})")
        kv("event_type", opp.event_type)
        kv("amount_at_risk", f"Rs.{opp.amount:,.2f}")
        kv("recovery_propensity", f"{opp.recovery_propensity:.2%}")
        kv("expected_recovery", f"Rs.{opp.expected_recovery_value:,.2f}")
        kv("recommended_action", opp.recommended_action.value)
        kv("opportunity_score", f"{opp.score:,.2f}")
        print(f"\n    {p_color}{BOLD}  +------------------------------+")
        print(f"    |  PRIORITY: {opp.priority_level:^18s} |")
        print(f"    +------------------------------+{RESET}")

    # ===================================================================
    # TIMING OPTIMIZER
    # ===================================================================
    section("BONUS: Timing Optimizer -- Optimal Delay per Failure Type")

    categories = [
        (FailureCategory.TRANSIENT_BANK_TIMEOUT, "Transient Bank Timeout"),
        (FailureCategory.INSUFFICIENT_FUNDS, "Insufficient Funds"),
        (FailureCategory.EXPIRED_OR_BLOCKED_CARD, "Expired/Blocked Card"),
        (FailureCategory.INACTIVITY_DROPOFF, "Checkout Abandonment"),
        (FailureCategory.MANDATE_REJECTED, "Mandate Rejected"),
    ]

    with SyncSessionLocal() as session:
        for cat, label in categories:
            test_evt = NormalizedEvent(
                event_id=f"evt_timing_{cat.value}",
                customer_id="cust_timing_test",
                event_type=EventType.PAYMENT_FAILED,
                amount=1000.0,
                failure_category=cat,
            )
            test_ctx = context_builder.build_context(session, test_evt)
            delay = timing_optimizer.predict_optimal_delay(test_ctx)

            if delay < 60:
                delay_str = f"{delay} min"
            else:
                delay_str = f"{delay // 60}h {delay % 60}m"

            print(f"    {label:<30s} -> {BOLD}{delay_str}{RESET}")

    # ===================================================================
    banner("DEMO COMPLETE")
    print(f"  {GREEN}All 5 completed phases working end-to-end.{RESET}")
    print(f"  Next: Phase 6 -- Multi-Agent Recovery Layer (4 Specialized Agents)\n")

    # Cleanup
    drop_sync_db()


if __name__ == "__main__":
    main()
