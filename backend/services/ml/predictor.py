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
from backend.core.constants import FailureCategory, RecoveryActionType
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

    def __init__(self, model_version: str = "v1.0.0-calibrated-gbm"):
        self.model_version = model_version
        self._model = None
        self._initialize_base_model()

    def _initialize_base_model(self):
        """Initializes a calibrated gradient boosting model with realistic domain priors."""
        np.random.seed(42)
        n_samples = 400
        n_features = len(feature_engine.FEATURE_NAMES)
        X = np.zeros((n_samples, n_features), dtype=np.float32)

        # Feature 0: historical_success_rate [0.0 - 1.0]
        X[:, 0] = np.random.beta(5, 2, size=n_samples)
        # Feature 1: total_transactions
        X[:, 1] = np.random.poisson(8, size=n_samples)
        # Feature 4: historical_recovery_rate [0.0 - 1.0]
        X[:, 4] = np.random.beta(6, 2, size=n_samples)
        # Feature 7: intervention_fatigue_score [0.0 - 1.0]
        X[:, 7] = np.random.beta(1.5, 4, size=n_samples)
        # Feature 9: revenue_at_risk
        X[:, 9] = np.random.exponential(3000, size=n_samples) + 500
        # Feature 12: failure_category_code (0 to 7)
        X[:, 12] = np.random.choice([0, 1, 2, 3, 4, 5, 6, 7], size=n_samples, p=[0.05, 0.35, 0.20, 0.15, 0.10, 0.05, 0.05, 0.05])
        # Feature 13: payment_method_code (0 to 5)
        X[:, 13] = np.random.choice([0, 1, 2, 3, 4, 5], size=n_samples, p=[0.05, 0.45, 0.30, 0.10, 0.05, 0.05])

        # Realistic Target Probability formula
        # Base recovery: 0.60, high success rate: +0.25, transient timeout (code 1): +0.20, fatigue: -0.35
        is_transient = (X[:, 12] == 1).astype(float)
        is_auth_or_funds = np.isin(X[:, 12], [2, 3]).astype(float)
        probs = 0.50 + 0.30 * X[:, 0] + 0.25 * is_transient - 0.20 * is_auth_or_funds - 0.40 * X[:, 7]
        y = (np.random.uniform(0.0, 1.0, size=n_samples) < np.clip(probs, 0.08, 0.95)).astype(int)

        base_gb = GradientBoostingClassifier(n_estimators=35, max_depth=3, random_state=42)
        self._model = CalibratedClassifierCV(estimator=base_gb, cv=3)
        self._model.fit(X, y)

    def predict_actions(self, context: DecisionContext) -> ModelPredictions:
        """
        Estimates P(recovery | context, action) for all applicable candidate recovery actions.
        """
        feat_vector = feature_engine.extract_feature_vector(context).reshape(1, -1)
        base_prob = float(self._model.predict_proba(feat_vector)[0, 1])

        state = context.customer_state
        event = context.current_event
        cat = event.failure_category
        risk_val = context.revenue_at_risk
        optimal_delay = timing_optimizer.predict_optimal_delay(context)

        # Baseline adjustments based on historical context
        if state.total_recovery_attempts > 0:
            hist_rec = state.historical_recovery_rate
            overall_propensity = (base_prob * 0.4) + (hist_rec * 0.6)
        elif state.successful_transactions > 0:
            overall_propensity = (base_prob * 0.4) + (state.success_rate * 0.6)
        else:
            # First-time customer or single failure so far: rely on ML prior
            overall_propensity = base_prob

        # Penalize for severe intervention fatigue or repeated consecutive failures (beyond first attempt)
        fatigue_penalty = state.intervention_fatigue_score * 0.30
        consecutive_penalty = min(0.40, max(0, state.consecutive_failures_count - 1) * 0.10)
        overall_propensity = float(np.clip(overall_propensity - fatigue_penalty - consecutive_penalty, 0.10, 0.95))

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
        best_expected_val = -1.0

        for action in candidate_actions:
            prob = overall_propensity
            cost = INTERVENTION_COSTS.get(action, 0.0)

            # Action-specific adjustments based on domain intelligence
            if action == RecoveryActionType.IMMEDIATE_RETRY:
                if cat == FailureCategory.TRANSIENT_BANK_TIMEOUT and not context.is_merchant_system_degraded:
                    prob = min(0.85, prob * 1.1)
                elif cat in [FailureCategory.INSUFFICIENT_FUNDS, FailureCategory.EXPIRED_OR_BLOCKED_CARD]:
                    prob = max(0.05, prob * 0.2)  # Immediate retry almost always fails for expired card / low funds
                else:
                    prob = prob * 0.7

            elif action == RecoveryActionType.DELAYED_RETRY:
                if cat == FailureCategory.TRANSIENT_BANK_TIMEOUT:
                    prob = min(0.92, prob * 1.35)
                elif cat == FailureCategory.INSUFFICIENT_FUNDS:
                    prob = min(0.75, prob * 1.2)
                else:
                    prob = prob * 0.9

            elif action == RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE:
                if cat in [FailureCategory.EXPIRED_OR_BLOCKED_CARD, FailureCategory.MANDATE_REJECTED, FailureCategory.INSUFFICIENT_FUNDS]:
                    prob = min(0.88, prob * 1.4)
                else:
                    prob = prob * 0.8

            elif action == RecoveryActionType.SEND_CHECKOUT_RECOVERY:
                if event.event_type.value == "CHECKOUT_ABANDONED":
                    prob = min(0.78, prob * 1.3)
                else:
                    prob = prob * 0.5

            elif action == RecoveryActionType.SEND_PERSONALIZED_MESSAGE:
                # Personalized Hinglish message provides solid lift across most categories
                prob = min(0.86, prob * 1.15)

            elif action == RecoveryActionType.START_VOICE_RECOVERY:
                # Voice works especially well for high-ticket transactions or older customers
                if risk_val >= 5000.0 and state.consecutive_failures_count <= 2:
                    prob = min(0.89, prob * 1.25)
                else:
                    prob = prob * 0.8

            elif action == RecoveryActionType.ESCALATE_TO_HUMAN:
                # High cost, but reliable for VIPs or high-value overdue invoices
                if risk_val >= 20000.0 or context.customer_profile.is_vip:
                    prob = min(0.95, prob * 1.3)
                else:
                    prob = prob * 0.6

            prob = round(float(np.clip(prob, 0.02, 0.98)), 4)
            expected_val = round(risk_val * prob, 2)
            net_exp_val = round(expected_val - cost, 2)
            confidence = round(min(0.99, max(0.50, 1.0 - (state.intervention_fatigue_score * 0.3))), 2)

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

            if net_exp_val > best_expected_val:
                best_expected_val = net_exp_val
                best_action = action

        # Opportunity Score calculation: E[V] * Efficiency Multiplier
        eff_mult = 1.0 - (state.intervention_fatigue_score * 0.4)
        opp_score = round(best_expected_val * eff_mult, 2)

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
