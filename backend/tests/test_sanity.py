"""
Sanity and baseline configuration tests for Phase 0.
"""

import pytest
from backend.core.config import get_settings
from backend.core.constants import (
    AgentType,
    Environment,
    EventType,
    PolicyVerdictStatus,
    RecoveryActionType,
)
from backend.core.logging import get_logger, setup_logging


def test_settings_load():
    """Verify settings load from environment with defaults."""
    settings = get_settings()
    assert settings.APP_NAME == "RevenueRecoveryIntelligenceEngine"
    assert settings.MAX_PAYMENT_RETRIES == 3
    assert settings.MIN_CONFIDENCE_THRESHOLD == 0.70
    assert settings.RAZORPAY_MODE == "test"
    assert not settings.is_production


def test_constants_enums():
    """Verify all domain constants and enums are properly defined."""
    # 4 Specialized Agents
    assert AgentType.PAYMENT_FAILURE.value == "PaymentFailureAgent"
    assert AgentType.CHECKOUT_ABANDONMENT.value == "CheckoutAbandonmentAgent"
    assert AgentType.SUBSCRIPTION_RECOVERY.value == "SubscriptionRecoveryAgent"
    assert AgentType.OVERDUE_RECEIVABLE.value == "OverdueReceivableAgent"
    assert AgentType.ORCHESTRATOR.value == "RecoveryOrchestrator"

    # Core Event Types
    assert EventType.PAYMENT_FAILED.value == "PAYMENT_FAILED"
    assert EventType.CHECKOUT_ABANDONED.value == "CHECKOUT_ABANDONED"
    assert EventType.SUBSCRIPTION_PAYMENT_FAILED.value == "SUBSCRIPTION_PAYMENT_FAILED"
    assert EventType.INVOICE_OVERDUE.value == "INVOICE_OVERDUE"

    # Actions & Policy
    assert RecoveryActionType.IMMEDIATE_RETRY.value == "IMMEDIATE_RETRY"
    assert PolicyVerdictStatus.APPROVED.value == "APPROVED"
    assert Environment.TEST.value == "test"


def test_logging_setup():
    """Verify logger initializes and logs structured output without throwing exceptions."""
    setup_logging(log_level="DEBUG")
    logger = get_logger("sanity_test")
    logger.info("Sanity test message", phase=0, status="passed")
    assert logger is not None
