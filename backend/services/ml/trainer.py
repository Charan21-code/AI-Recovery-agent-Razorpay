"""
Offline Model Training and Evaluation Pipeline.
Evaluates calibration, PR-AUC, ROC-AUC, and baseline metrics.
"""

from typing import Any, Dict, List, Tuple
import numpy as np
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from backend.core.logging import get_logger

logger = get_logger("ml_trainer")


class MLTrainer:
    """Trains and evaluates tabular recovery models on historical feedback datasets."""

    def train_and_evaluate(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
    ) -> Tuple[Any, Dict[str, float]]:
        """
        Trains a calibrated gradient boosting model and computes comprehensive evaluation metrics.
        """
        base_model = GradientBoostingClassifier(
            n_estimators=50,
            max_depth=3,
            learning_rate=0.08,
            random_state=42,
        )
        calibrated = CalibratedClassifierCV(estimator=base_model, cv=3)
        calibrated.fit(X_train, y_train)

        # Predictions on held-out test set
        y_pred_proba = calibrated.predict_proba(X_test)[:, 1]
        y_pred = (y_pred_proba >= 0.50).astype(int)

        # Compute Metrics
        roc_auc = float(roc_auc_score(y_test, y_pred_proba)) if len(np.unique(y_test)) > 1 else 0.5
        pr_auc = float(average_precision_score(y_test, y_pred_proba)) if len(np.unique(y_test)) > 1 else 0.5
        brier = float(brier_score_loss(y_test, y_pred_proba))
        prec = float(precision_score(y_test, y_pred, zero_division=0))
        rec = float(recall_score(y_test, y_pred, zero_division=0))
        f1 = float(f1_score(y_test, y_pred, zero_division=0))

        metrics = {
            "roc_auc": round(roc_auc, 4),
            "pr_auc": round(pr_auc, 4),
            "brier_score": round(brier, 4),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4),
        }

        logger.info("Model training & evaluation complete", **metrics)
        return calibrated, metrics


ml_trainer = MLTrainer()
