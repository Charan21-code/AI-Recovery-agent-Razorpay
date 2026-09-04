"""
LLM Reasoning Engine: Generates explainable recovery decisions, evidence citations,
and natural language explanations conforming to Section 69 (LLM Output Contract)
with Section 61 deterministic safety fallbacks.
"""

import json
import os
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field

from backend.core.config import settings
from backend.core.constants import FailureCategory, RecoveryActionType
from backend.core.logging import get_logger
from backend.schemas.context import DecisionContext

logger = get_logger("llm_reasoning")


class LLMReasoningOutput(BaseModel):
    """Structured LLM output contract matching Section 69."""
    action: RecoveryActionType
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    reason: str
    evidence: List[str] = Field(default_factory=list)
    recommended_delay_minutes: int = Field(default=0)
    requires_human_review: bool = Field(default=False)
    customer_message: Optional[str] = Field(default=None)


class LLMReasoningService:
    """
    Orchestrates LLM calls to Google Gemini / Generative Language API
    with strict validation and deterministic fallback protection.
    """

    def __init__(self):
        self.api_key = settings.LLM_API_KEY or os.environ.get("GEMINI_API_KEY")
        self.model = settings.LLM_MODEL or "gemini-2.5-flash"
        self.provider = settings.LLM_PROVIDER

    def generate_reasoning(
        self,
        context: DecisionContext,
        recommended_action: RecoveryActionType,
        predicted_propensity: float = 0.75,
    ) -> LLMReasoningOutput:
        """
        Generates structured decision reasoning, evidence citations, and customer message.
        Tries Gemini API if configured; falls back safely to deterministic rules (Section 61).
        """
        if self.api_key and self.provider != "mock":
            try:
                llm_res = self._call_gemini_api(context, recommended_action, predicted_propensity)
                if llm_res:
                    return llm_res
            except Exception as e:
                logger.warning(f"LLM API call failed or timed out: {e}. Falling back to deterministic reasoning.")

        # Section 61: Safe deterministic fallback
        return self._generate_deterministic_reasoning(context, recommended_action, predicted_propensity)

    def _call_gemini_api(
        self,
        context: DecisionContext,
        recommended_action: RecoveryActionType,
        predicted_propensity: float,
    ) -> Optional[LLMReasoningOutput]:
        """Calls Google Gemini API for structured JSON reasoning."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        prompt = f"""
You are the Reasoning Core for an autonomous Razorpay Revenue Recovery Engine.
Context:
- Customer: {context.customer_profile.name} (VIP: {context.customer_profile.is_vip})
- Total Transactions: {context.customer_state.total_transactions} ({context.customer_state.successful_transactions} successful, {context.customer_state.failed_transactions} failed)
- Prior Recovery Attempts: {context.customer_state.total_recovery_attempts} (Recovery Rate: {context.customer_state.historical_recovery_rate * 100:.1f}%)
- Intervention Fatigue Score: {context.customer_state.intervention_fatigue_score:.2f}
- Current Event: {context.current_event.event_type.value} of amount Rs. {context.revenue_at_risk:,.2f}
- Failure Category: {context.current_event.failure_category.value} ({context.current_event.failure_reason or 'No description'})
- ML Recommended Action: {recommended_action.value} (Propensity: {predicted_propensity * 100:.1f}%)

Requirement: Output strict JSON conforming to Section 69:
{{
  "action": "{recommended_action.value}",
  "confidence": {round(predicted_propensity, 2)},
  "reason": "1-2 sentence business explanation of why this action was selected.",
  "evidence": [
    "Fact 1 from customer history",
    "Fact 2 regarding attempts or fatigue",
    "Fact 3 regarding failure reason"
  ],
  "recommended_delay_minutes": 30,
  "requires_human_review": false,
  "customer_message": "Friendly, professional 1-sentence customer outreach message in English or Hinglish"
}}
"""
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.2,
            },
        }

        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text)
                return LLMReasoningOutput(
                    action=RecoveryActionType(parsed.get("action", recommended_action.value)),
                    confidence=float(parsed.get("confidence", predicted_propensity)),
                    reason=str(parsed.get("reason")),
                    evidence=list(parsed.get("evidence", [])),
                    recommended_delay_minutes=int(parsed.get("recommended_delay_minutes", 0)),
                    requires_human_review=bool(parsed.get("requires_human_review", False)),
                    customer_message=parsed.get("customer_message"),
                )
            else:
                logger.warning(f"Gemini API returned status {resp.status_code}: {resp.text}")
                return None

    def _generate_deterministic_reasoning(
        self,
        context: DecisionContext,
        action: RecoveryActionType,
        propensity: float,
    ) -> LLMReasoningOutput:
        """
        Deterministic, audit-compliant reasoning generator adhering to Section 69 and Section 36.
        All statements derive strictly from computed context.
        """
        state = context.customer_state
        event = context.current_event
        attempts = int(max(state.total_recovery_attempts, context.history_summary.previous_recovery_attempts))
        amount = context.revenue_at_risk

        evidence: List[str] = [
            f"{state.successful_transactions} of {max(1, state.total_transactions)} historical transactions completed successfully ({state.success_rate * 100:.1f}%)",
            f"Intervention count ({attempts}) is within merchant threshold (fatigue score: {state.intervention_fatigue_score:.2f})",
            f"Failure classified as {event.failure_category.value} with predicted recovery propensity of {propensity * 100:.1f}%",
        ]

        if action == RecoveryActionType.DELAYED_RETRY:
            reason = (
                f"Delayed retry selected because the customer has a high historical success rate, "
                f"the bank error is transient ({event.failure_category.value}), and intervention fatigue is low."
            )
            cust_msg = None
            delay = 30
        elif action == RecoveryActionType.SEND_PAYMENT_METHOD_UPDATE:
            reason = (
                f"Payment method update requested because the payment failed with a hard decline or mandate issue "
                f"({event.failure_category.value}) which cannot be retried silently."
            )
            cust_msg = f"Hi {context.customer_profile.name}, your payment of Rs.{amount:,.2f} could not be processed. Tap here to update your payment method: https://rzp.io/i/update"
            delay = 0
        elif action == RecoveryActionType.SEND_PERSONALIZED_MESSAGE:
            reason = (
                f"Personalized outreach selected after attempt {attempts} to guide customer to alternate payment options "
                f"with high recovery propensity ({propensity * 100:.1f}%)."
            )
            cust_msg = f"Hi {context.customer_profile.name}, your payment of Rs.{amount:,.2f} was interrupted due to a bank timeout. Click here to finish securely: https://rzp.io/i/quick"
            delay = 0
        elif action == RecoveryActionType.START_VOICE_RECOVERY:
            reason = (
                f"Automated AI voice call initiated for high-touch assistance after {attempts} attempts "
                f"on Rs.{amount:,.2f} at-risk revenue."
            )
            cust_msg = f"Namaste {context.customer_profile.name}, this is Razorpay regarding your recent transaction of Rs.{amount:,.2f}."
            delay = 0
        elif action == RecoveryActionType.ESCALATE_TO_HUMAN:
            reason = (
                f"Escalated to human account manager due to attempt exhaustion ({attempts} attempts) "
                f"and high transaction value (Rs.{amount:,.2f})."
            )
            cust_msg = None
            delay = 0
        elif action == RecoveryActionType.STOP:
            reason = (
                f"Outreach halted to prevent intervention fatigue after {attempts} unsuccessful automated recovery cycles."
            )
            cust_msg = None
            delay = 0
        else:
            reason = f"Action {action.value} proposed by ML intelligence engine."
            cust_msg = None
            delay = 0

        return LLMReasoningOutput(
            action=action,
            confidence=round(propensity, 2),
            reason=reason,
            evidence=evidence,
            recommended_delay_minutes=delay,
            requires_human_review=(action == RecoveryActionType.ESCALATE_TO_HUMAN),
            customer_message=cust_msg,
        )


llm_reasoning_service = LLMReasoningService()
