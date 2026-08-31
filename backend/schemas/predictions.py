"""
ML model prediction and opportunity scoring schemas.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from pydantic import BaseModel, Field
from backend.core.constants import RecoveryActionType


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ActionPrediction(BaseModel):
    action: RecoveryActionType
    recovery_probability: float = Field(..., ge=0.0, le=1.0)
    expected_recovery_value: float = Field(..., ge=0.0)
    estimated_intervention_cost: float = Field(default=0.0, ge=0.0)
    net_expected_value: float = Field(...)
    recommended_delay_minutes: int = Field(default=0, ge=0)
    confidence_score: float = Field(..., ge=0.0, le=1.0)


class ModelPredictions(BaseModel):
    prediction_id: str = Field(...)
    context_id: str = Field(...)
    overall_recovery_propensity: float = Field(..., ge=0.0, le=1.0)
    action_predictions: Dict[str, ActionPrediction] = Field(default_factory=dict)
    best_candidate_action: RecoveryActionType
    best_expected_value: float = Field(..., ge=0.0)
    opportunity_score: float = Field(..., ge=0.0)
    optimal_delay_minutes: int = Field(default=0, ge=0)
    model_version: str = Field(default="v1.0.0-calibrated-gbm")
    created_at: datetime = Field(default_factory=utc_now)


class OpportunityScore(BaseModel):
    opportunity_id: str
    event_id: str
    customer_id: str
    customer_name: Optional[str]
    amount: float
    event_type: str
    priority_level: str = Field(default="MEDIUM", description="CRITICAL, HIGH, MEDIUM, LOW")
    recovery_propensity: float
    expected_recovery_value: float
    recommended_action: RecoveryActionType
    score: float
    timestamp: datetime = Field(default_factory=utc_now)
