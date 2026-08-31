"""
Unit and Integration tests for Ingestion Layer, Normalizer, and Razorpay Adapter.
"""

import json
import pytest
from backend.core.constants import Environment, EventType, FailureCategory
from backend.db.init_db import drop_sync_db, init_sync_db
from backend.db.session import SyncSessionLocal
from backend.services.execution.razorpay_adapter import RazorpayAdapter
from backend.services.ingestion.idempotency import IdempotencyGuard
from backend.services.ingestion.receiver import ingest_raw_event
from backend.services.ingestion.security import (
    generate_razorpay_signature,
    verify_razorpay_signature,
)
from backend.services.normalization.normalizer import (
    classify_failure_category,
    normalize_razorpay_event,
)


@pytest.fixture(autouse=True)
def setup_db():
    init_sync_db()
    yield
    drop_sync_db()


def test_hmac_signature_verification():
    """Verify HMAC SHA256 signature generation and validation."""
    secret = "secret_webhook_key_123"
    payload = b'{"event":"payment.failed","amount":249900}'

    sig = generate_razorpay_signature(payload, secret=secret)
    assert sig is not None
    assert len(sig) == 64

    # Valid signature check
    assert verify_razorpay_signature(payload, sig, secret=secret)

    # Tampered payload check
    tampered_payload = b'{"event":"payment.failed","amount":999900}'
    assert not verify_razorpay_signature(tampered_payload, sig, secret=secret)

    # Empty signature check
    assert not verify_razorpay_signature(payload, "", secret=secret)


def test_idempotency_guard():
    """Verify duplicate event prevention in memory and DB."""
    guard = IdempotencyGuard()
    with SyncSessionLocal() as session:
        # First check -> New event
        assert guard.check_and_register(session, "evt_test_unique_1")
        # Immediate second check -> Duplicate
        assert not guard.check_and_register(session, "evt_test_unique_1")


def test_event_normalization_payment_failed():
    """Verify normalization of a Razorpay payment.failed payload."""
    rzp_payload = {
        "event": "payment.failed",
        "account_id": "acc_mer_123",
        "created_at": 1756543200,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_test_failed_999",
                    "amount": 499900,  # 4999.00 INR
                    "currency": "INR",
                    "status": "failed",
                    "order_id": "order_test_999",
                    "method": "upi",
                    "error_code": "BAD_REQUEST_ERROR",
                    "error_description": "Bank system timed out during authorization",
                    "email": "customer@example.com",
                    "contact": "+919876543210",
                }
            }
        },
    }

    normalized = normalize_razorpay_event(rzp_payload, environment=Environment.TEST)
    assert normalized.event_type == EventType.PAYMENT_FAILED
    assert normalized.amount == 4999.0
    assert normalized.payment_id == "pay_test_failed_999"
    assert normalized.order_id == "order_test_999"
    assert normalized.customer_id == "customer@example.com"
    assert normalized.failure_category == FailureCategory.TRANSIENT_BANK_TIMEOUT
    assert normalized.is_actionable


def test_event_normalization_subscription_halted():
    """Verify normalization of subscription failure."""
    rzp_payload = {
        "event": "subscription.halted",
        "payload": {
            "subscription": {
                "entity": {
                    "id": "sub_test_halted_123",
                    "amount": 99900,
                    "currency": "INR",
                    "status": "halted",
                    "customer_id": "cust_sub_123",
                }
            }
        },
    }

    normalized = normalize_razorpay_event(rzp_payload, environment=Environment.TEST)
    assert normalized.event_type == EventType.SUBSCRIPTION_PAYMENT_FAILED
    assert normalized.amount == 999.0
    assert normalized.subscription_id == "sub_test_halted_123"
    assert normalized.is_actionable


@pytest.mark.asyncio
async def test_razorpay_adapter_mock_operations():
    """Verify Razorpay Adapter methods in test/mock mode."""
    adapter = RazorpayAdapter(key_id="rzp_test_mock", key_secret="mock_secret")

    # Create Order
    order = await adapter.create_order(amount_inr=1500.0, receipt="rcpt_101")
    assert order["entity"] == "order"
    assert order["amount"] == 150000

    # Fetch Payment
    payment = await adapter.fetch_payment(payment_id="pay_123")
    assert payment["id"] == "pay_123"
    assert payment["amount"] == 249900

    # Create Payment Link
    link = await adapter.create_payment_link(
        amount_inr=1500.0,
        customer_name="Rahul",
        description="Recovery Link",
    )
    assert "https://rzp.io" in link["short_url"]
    assert link["status"] == "created"
