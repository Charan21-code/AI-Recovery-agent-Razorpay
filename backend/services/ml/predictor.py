"""
Predictive Intelligence Layer: Estimates P(recovery | context, action), expected recovery value, and confidence.
"""

from datetime import datetime, timezone
import math
import uuid
from typing import Dict, List, Optional
import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import GradientBoostingClassifier
from backend.core.constants import EventType, FailureCategory, RecoveryActionType
from backend.core.logging import get_logger
from backend.schemas.context import DecisionContext
from backend.schemas.predictions import (
    ActionPrediction,
    ModelPredictions,
    OpportunityScore,
)
from backend.services.features.feature_engine import feature_engine
from backend.services.ml.timing_optimizer import timing_optimizer

logger = get_logger("ml_predictor")

# Estimated cost of each intervention channel in INR
INTERVENTION_COSTS: Dict[RecoveryActionType, float] = {
    RecoveryActionType.IMMEDIATE_RETRY: 0.00,  # Zero direct cost
    RecoveryActionType.DELAYED_RETRY: 0.00,    # Zero direct cost
    RecoveryActionType.SEND_PAYMENT_REMINDER: 0.20,  # SMS cost ~0.20 INR
    RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE: 0.40,  # WhatsApp / Email
    RecoveryActionType.SEND_CHECKOUT_RECOVERY: 0.40,
    RecoveryActionType.GENERATE_PAYMENT_LINK: 0.40,
    RecoveryActionType.SEND_PERSONALIZED_MESSAGE: 0.50,
    RecoveryActionType.START_VOICE_RECOVERY: 2.50,  # Voice AI call cost
    RecoveryActionType.ESCALATE_TO_HUMAN: 15.00,    # Human agent time cost
    RecoveryActionType.SCHEDULE_DUNNING_STEP: 0.30,
    RecoveryActionType.PROGRESSIVE_FOLLOWUP: 0.50,
    RecoveryActionType.WAIT: 0.00,
    RecoveryActionType.STOP: 0.00,
}


class RecoveryPredictor:
    """Estimates recovery probability per candidate action and opportunity priority."""

    def __init__(self, model_version: str = "v2.0.0-calibrated-gbm"):
        self.model_version = model_version
        self._model = None
        self._initialize_base_model()

    def _initialize_base_model(self):
        """Initializes a calibrated gradient boosting model trained across all 20 features."""
        np.random.seed(42)
        n_samples = 1500
        n_features = len(feature_engine.FEATURE_NAMES)
        X = np.zeros((n_samples, n_features), dtype=np.float32)

        # Feature 0: historical_success_rate [0.0 - 1.0]
        X[:, 0] = np.random.beta(5, 2, size=n_samples)
        # Feature 1: total_transactions
        X[:, 1] = np.random.poisson(8, size=n_samples) + 1
        # Feature 2: total_revenue_generated
        X[:, 2] = X[:, 1] * np.random.uniform(1500, 3500, size=n_samples)
        # Feature 3: average_transaction_value
        X[:, 3] = X[:, 2] / X[:, 1]
        # Feature 4: historical_recovery_rate [0.0 - 1.0]
        X[:, 4] = np.random.beta(4, 2, size=n_samples)
        # Feature 5: total_recovery_attempts [0 to 5]
        X[:, 5] = np.random.choice([0, 1, 2, 3, 4, 5], size=n_samples, p=[0.35, 0.25, 0.18, 0.12, 0.06, 0.04])
        # Feature 6: consecutive_failures_count
        X[:, 6] = X[:, 5] + np.random.choice([0, 1], size=n_samples, p=[0.7, 0.3])
        # Feature 7: intervention_fatigue_score [0.0 - 1.0]
        X[:, 7] = np.clip(X[:, 5] * 0.22 + np.random.normal(0, 0.04, size=n_samples), 0.0, 1.0)
        # Feature 8: recent_intervention_count
        X[:, 8] = X[:, 5]
        # Feature 9: revenue_at_risk
        X[:, 9] = np.random.exponential(3500, size=n_samples) + 500
        # Feature 10: estimated_clv_at_risk
        X[:, 10] = X[:, 9] * np.random.uniform(4, 12, size=n_samples)
        # Feature 11: amount_to_avg_ratio
        X[:, 11] = np.clip(np.random.normal(1.0, 0.3, size=n_samples), 0.2, 4.0)
        # Feature 12: failure_category_code (0 to 7)
        X[:, 12] = np.random.choice([0, 1, 2, 3, 4, 5, 6, 7], size=n_samples, p=[0.05, 0.35, 0.20, 0.15, 0.10, 0.05, 0.05, 0.05])
        # Feature 13: payment_method_code (0 to 5)
        X[:, 13] = np.random.choice([0, 1, 2, 3, 4, 5], size=n_samples, p=[0.05, 0.45, 0.30, 0.10, 0.05, 0.05])
        # Feature 14: attempt_count
        X[:, 14] = X[:, 5] + 1
        # Feature 15: hour_of_day
        X[:, 15] = np.random.uniform(0, 24, size=n_samples)
        # Feature 16: day_of_week
        X[:, 16] = np.random.uniform(0, 7, size=n_samples)
        # Feature 17: is_merchant_system_degraded
        X[:, 17] = np.random.choice([0, 1], size=n_samples, p=[0.90, 0.10])
        # Feature 18: is_vip_customer
        X[:, 18] = np.random.choice([0, 1], size=n_samples, p=[0.85, 0.15])
        # Feature 19: is_opted_out
        X[:, 19] = np.random.choice([0, 1], size=n_samples, p=[0.95, 0.05])

        # Realistic Domain Probability Formula with Causal Sensitivity:
        # Base recovery potential: 0.60
        # Success and recovery history lift: +0.20, +0.15
        # Transient timeout lift: +0.20
        # Recovery attempts decay: -0.14 per attempt (strongly penalizes repeated attempts)
        # Fatigue penalty: -0.22
        # System degradation penalty: -0.25
        # Hard declines penalty: -0.20
        is_transient = (X[:, 12] == 1).astype(float)
        is_hard_decline = np.isin(X[:, 12], [4, 5]).astype(float)

        probs = (
            0.60
            + 0.20 * X[:, 0]
            + 0.15 * X[:, 4]
            + 0.20 * is_transient
            - 0.14 * X[:, 5]
            - 0.22 * X[:, 7]
            - 0.08 * np.clip(X[:, 6] - 1, 0, 5)
            - 0.25 * X[:, 17]
            - 0.20 * is_hard_decline
        )
        y = (np.random.uniform(0.0, 1.0, size=n_samples) < np.clip(probs, 0.05, 0.95)).astype(int)

        base_gb = GradientBoostingClassifier(n_estimators=45, max_depth=4, learning_rate=0.08, random_state=42)
        self._model = CalibratedClassifierCV(estimator=base_gb, cv=3)
        self._model.fit(X, y)

    def predict_actions(self, context: DecisionContext) -> ModelPredictions:
        """
        Estimates P(recovery | context, action) for all candidate recovery actions.
        Sensitively reacts to previous recovery attempts, failure categories, and customer context.
        """
        feat_vector = feature_engine.extract_feature_vector(context).reshape(1, -1)
        base_prob = float(self._model.predict_proba(feat_vector)[0, 1])

        state = context.customer_state
        hist = context.history_summary
        event = context.current_event
        cat = event.failure_category
        risk_val = context.revenue_at_risk
        optimal_delay = timing_optimizer.predict_optimal_delay(context)

        # Synchronize attempts and fatigue from state and history summary
        attempts = int(max(state.total_recovery_attempts, hist.previous_recovery_attempts))
        fatigue = float(max(state.intervention_fatigue_score, hist.intervention_fatigue_score))
        if fatigue == 0.0 and attempts > 0:
            fatigue = float(min(1.0, attempts * 0.22))
        consecutive = int(max(state.consecutive_failures_count, hist.consecutive_failures_count, attempts))

        # Overall Propensity formulation:
        # For first-time recovery (attempts == 0), customer historical success rate elevates propensity
        # As attempts increase, propensity drops monotonically due to non-responsiveness / exhaustion
        if attempts == 0:
            if state.success_rate > 0:
                overall_propensity = (base_prob * 0.5) + (state.success_rate * 0.5)
            else:
                overall_propensity = base_prob
        else:
            attempt_decay = max(0.05, 1.0 - (attempts * 0.16))
            overall_propensity = base_prob * (0.35 + 0.65 * attempt_decay)
            if state.historical_recovery_rate > 0:
                overall_propensity = (overall_propensity * 0.7) + (state.historical_recovery_rate * 0.3)
            # Additional penalty for intervention fatigue and consecutive failures
            overall_propensity -= (fatigue * 0.18) + (min(0.30, max(0, consecutive - 1) * 0.08))

        overall_propensity = float(np.clip(overall_propensity, 0.05, 0.95))

        action_predictions: Dict[str, ActionPrediction] = {}
        candidate_actions = [
            RecoveryActionType.IMMEDIATE_RETRY,
            RecoveryActionType.DELAYED_RETRY,
            RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE,
            RecoveryActionType.SEND_PAYMENT_REMINDER,
            RecoveryActionType.SEND_CHECKOUT_RECOVERY,
            RecoveryActionType.GENERATE_PAYMENT_LINK,
            RecoveryActionType.SEND_PERSONALIZED_MESSAGE,
            RecoveryActionType.START_VOICE_RECOVERY,
            RecoveryActionType.ESCALATE_TO_HUMAN,
        ]

        best_action = RecoveryActionType.DELAYED_RETRY
        best_expected_val = -100.0

        for action in candidate_actions:
            prob = overall_propensity
            cost = INTERVENTION_COSTS.get(action, 0.0)

            # --- DYNAMIC ATTEMPT-BASED SCORING MATRIX ---
            
            # Base logic: penalize all actions slightly initially
            prob = prob * 0.50

            if attempts == 0:
                if action == RecoveryActionType.IMMEDIATE_RETRY:
                    prob = overall_propensity * 1.15 if cat == FailureCategory.TRANSIENT_BANK_TIMEOUT and not context.is_merchant_system_degraded else 0.05
                elif action == RecoveryActionType.DELAYED_RETRY:
                    prob = overall_propensity * 1.35 if cat == FailureCategory.TRANSIENT_BANK_TIMEOUT else overall_propensity * 1.10
                elif action == RecoveryActionType.SEND_PAYMENT_REMINDER:
                    prob = overall_propensity * 0.90
                elif action == RecoveryActionType.SEND_CHECKOUT_RECOVERY:
                    prob = overall_propensity * 1.30 if event.event_type == EventType.CHECKOUT_ABANDONED else 0.10

            elif attempts == 1:
                if action == RecoveryActionType.GENERATE_PAYMENT_LINK:
                    prob = overall_propensity * 1.40
                elif action == RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE:
                    prob = overall_propensity * 1.35
                elif action == RecoveryActionType.SEND_PAYMENT_REMINDER:
                    prob = overall_propensity * 1.20
                elif action == RecoveryActionType.DELAYED_RETRY:
                    prob = overall_propensity * 0.70

            elif attempts == 2:
                if action == RecoveryActionType.SEND_PERSONALIZED_MESSAGE:
                    prob = overall_propensity * 1.45
                elif action == RecoveryActionType.START_VOICE_RECOVERY:
                    prob = overall_propensity * 1.30 if risk_val >= 1000.0 else 0.40
                elif action == RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE:
                    prob = overall_propensity * 1.20

            else:  # attempts >= 3
                if action == RecoveryActionType.ESCALATE_TO_HUMAN:
                    if risk_val >= 10000.0 or context.customer_profile.is_vip:
                        prob = overall_propensity * 1.80
                    else:
                        prob = overall_propensity * 1.40
                elif action == RecoveryActionType.START_VOICE_RECOVERY:
                    prob = overall_propensity * 1.50
                elif action == RecoveryActionType.STOP:
                    prob = 0.95  # Safe stop action
                
                # Disallow silent retries explicitly
                if action in [RecoveryActionType.IMMEDIATE_RETRY, RecoveryActionType.DELAYED_RETRY]:
                    prob = 0.01

            # Hard Declines Exception
            if cat in [FailureCategory.EXPIRED_OR_BLOCKED_CARD, FailureCategory.MANDATE_REJECTED]:
                if action in [RecoveryActionType.IMMEDIATE_RETRY, RecoveryActionType.DELAYED_RETRY]:
                    prob = 0.01
                if action == RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE and attempts < 3:
                    prob = overall_propensity * 1.60

            prob = round(float(np.clip(prob, 0.02, 0.98)), 4)
            
            # Recalibrate Expected Value 
            # (Use a scaled expected value so high costs don't completely bury valid actions)
            # We treat cost as a penalty on the raw expected value
            expected_val = round(risk_val * prob, 2)
            
            # To ensure the logic works even for low amounts where expected_val < 15,
            # we scale the net expected value logic based on base amounts
            net_exp_val = round(expected_val - (cost * 100.0 if risk_val < 5000 else cost * 10.0), 2)
            
            # Confidence decays directly with attempts and fatigue
            confidence = round(float(np.clip(1.0 - (fatigue * 0.35) - (attempts * 0.06), 0.40, 0.98)), 2)

            act_pred = ActionPrediction(
                action=action,
                recovery_probability=prob,
                expected_recovery_value=expected_val,
                estimated_intervention_cost=cost,
                net_expected_value=net_exp_val,
                recommended_delay_minutes=optimal_delay if action == RecoveryActionType.DELAYED_RETRY else 0,
                confidence_score=confidence,
            )
            action_predictions[action.value] = act_pred

            # Select best candidate action:
            is_disallowed_retry = (attempts >= 3 and action in [RecoveryActionType.IMMEDIATE_RETRY, RecoveryActionType.DELAYED_RETRY])
            if net_exp_val > best_expected_val and not is_disallowed_retry:
                best_expected_val = net_exp_val
                best_action = action

        # Opportunity Score calculation: E[V] * Efficiency Multiplier
        eff_mult = max(0.1, 1.0 - (fatigue * 0.45))
        opp_score = round(max(0.0, best_expected_val * eff_mult), 2)

        return ModelPredictions(
            prediction_id=f"pred_{uuid.uuid4().hex[:12]}",
            context_id=context.context_id,
            overall_recovery_propensity=round(overall_propensity, 4),
            action_predictions=action_predictions,
            best_candidate_action=best_action,
            best_expected_value=best_expected_val,
            opportunity_score=opp_score,
            optimal_delay_minutes=optimal_delay,
            model_version=self.model_version,
            created_at=datetime.now(timezone.utc),
        )


recovery_predictor = RecoveryPredictor()
