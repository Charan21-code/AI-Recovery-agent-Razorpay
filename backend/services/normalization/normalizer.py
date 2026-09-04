"""
Event Normalization Service: Maps external provider payloads into the unified internal taxonomy.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from backend.core.constants import Environment, EventType, FailureCategory
from backend.core.logging import get_logger
from backend.schemas.events import NormalizedEvent, RawEventPayload

logger = get_logger("event_normalizer")


def classify_failure_category(error_code: Optional[str], description: Optional[str]) -> FailureCategory:
    """Categorizes granular gateway and bank error codes into structured FailureCategory."""
    if not error_code and not description:
        return FailureCategory.UNKNOWN

    combined = f"{error_code or ''} {description or ''}".upper()

    # Prioritize Transient Bank / Gateway Timeouts
    if any(k in combined for k in ["TIMEOUT", "GATEWAY_ERROR", "BANK_ERROR", "SERVER_ERROR", "TEMPORARY", "TRY_AGAIN", "TIMED OUT"]):
        return FailureCategory.TRANSIENT_BANK_TIMEOUT
    if any(k in combined for k in ["MANDATE", "AUTO_DEBIT", "RECURRING_CANCELLED", "RECURRING_FAILED"]):
        return FailureCategory.MANDATE_REJECTED
    if any(k in combined for k in ["INSUFFICIENT", "LOW_BALANCE", "LIMIT_EXCEEDED", "FUNDS"]):
        return FailureCategory.INSUFFICIENT_FUNDS
    if any(k in combined for k in ["EXPIRED", "BLOCKED", "CARD_DECLINED", "INVALID_CARD", "RESTRICTED"]):
        return FailureCategory.EXPIRED_OR_BLOCKED_CARD
    if any(k in combined for k in ["OTP", "AUTHENTICATION", "PASSWORD", "PIN", "3DS", "AUTH_FAILED"]):
        return FailureCategory.AUTHENTICATION_FAILED
    if any(k in combined for k in ["CANCELLED", "USER_DROPPED", "DISMISSED"]):
        return FailureCategory.USER_CANCELLED
    if any(k in combined for k in ["INACTIVE", "ABANDONED", "SESSION_EXPIRED"]):
        return FailureCategory.INACTIVITY_DROPOFF

    return FailureCategory.UNKNOWN


def normalize_razorpay_event(
    raw_payload: Dict[str, Any],
    environment: Environment = Environment.TEST,
) -> NormalizedEvent:
    """
    Normalizes a Razorpay webhook payload or REST response into our unified NormalizedEvent schema.
    Converts paise to standard currency units (INR).
    """
    event_str = raw_payload.get("event", "")
    payload_section = raw_payload.get("payload", {})

    # Extract entities if available
    payment_entity = payload_section.get("payment", {}).get("entity", {})
    order_entity = payload_section.get("order", {}).get("entity", {})
    sub_entity = payload_section.get("subscription", {}).get("entity", {})
    invoice_entity = payload_section.get("invoice", {}).get("entity", {})
    checkout_entity = payload_section.get("checkout", {}).get("entity", {})

    # Determine event type
    event_type = EventType.UNKNOWN
    if event_str in ["payment.captured", "payment.authorized"]:
        event_type = EventType.PAYMENT_SUCCESS
    elif event_str == "payment.failed":
        event_type = EventType.PAYMENT_FAILED
    elif event_str == "order.paid":
        event_type = EventType.PAYMENT_SUCCESS
    elif event_str in ["subscription.charged", "subscription.activated"]:
        event_type = EventType.SUBSCRIPTION_ACTIVE
    elif event_str in [
        "subscription.halted",
        "subscription.pending",
        "subscription.charged.failed",
        "subscription.charged_failed",
        "subscription.payment_failed",
    ]:
        event_type = EventType.SUBSCRIPTION_PAYMENT_FAILED
    elif event_str == "subscription.cancelled":
        event_type = EventType.SUBSCRIPTION_CANCELLED
    elif event_str == "invoice.paid":
        event_type = EventType.INVOICE_PAID
    elif event_str in ["invoice.expired", "invoice.overdue"]:
        event_type = EventType.INVOICE_OVERDUE
    elif event_str in ["checkout.abandoned", "checkout.started"]:
        event_type = EventType.CHECKOUT_ABANDONED if "abandoned" in event_str else EventType.CHECKOUT_STARTED
    elif event_str in ["mandate.failed", "subscription.mandate_failed"]:
        event_type = EventType.MANDATE_FAILED

    # Extract fields with safe fallbacks
    event_id = (
        raw_payload.get("event_id")
        or raw_payload.get("id")
        or payment_entity.get("id")
        or checkout_entity.get("id")
        or f"evt_{int(datetime.now(timezone.utc).timestamp())}"
    )
    
    # Amount in standard currency units (Razorpay provides amount in paise)
    amount_raw = (
        payment_entity.get("amount")
        or order_entity.get("amount")
        or sub_entity.get("amount")
        or sub_entity.get("total_amount")
        or invoice_entity.get("amount")
        or checkout_entity.get("amount")
        or 0
    )
    amount = float(amount_raw) / 100.0 if amount_raw > 0 else float(raw_payload.get("amount", 0.0))

    currency = (
        payment_entity.get("currency")
        or order_entity.get("currency")
        or checkout_entity.get("currency")
        or invoice_entity.get("currency")
        or "INR"
    )
    customer_id = (
        payment_entity.get("customer_id")
        or payment_entity.get("email")
        or payment_entity.get("contact")
        or sub_entity.get("customer_id")
        or invoice_entity.get("customer_id")
        or checkout_entity.get("customer_id")
        or checkout_entity.get("email")
        or checkout_entity.get("contact")
        or raw_payload.get("customer_id")
        or "cust_anonymous"
    )

    payment_method = payment_entity.get("method") or raw_payload.get("payment_method")
    error_code = (
        payment_entity.get("error_code")
        or sub_entity.get("error_code")
        or raw_payload.get("error_code")
    )
    error_desc = (
        payment_entity.get("error_description")
        or payment_entity.get("error_reason")
        or sub_entity.get("error_description")
        or raw_payload.get("error_description")
    )
    failure_cat = classify_failure_category(error_code, error_desc)

    # Contextual failure category defaults if error details are not explicitly provided in webhook
    if failure_cat == FailureCategory.UNKNOWN:
        if event_type == EventType.CHECKOUT_ABANDONED:
            failure_cat = FailureCategory.INACTIVITY_DROPOFF
        elif event_type in [EventType.SUBSCRIPTION_PAYMENT_FAILED, EventType.MANDATE_FAILED]:
            failure_cat = FailureCategory.MANDATE_REJECTED

    order_id = payment_entity.get("order_id") or order_entity.get("id") or raw_payload.get("order_id")
    payment_id = payment_entity.get("id") or raw_payload.get("payment_id")
    subscription_id = sub_entity.get("id") or raw_payload.get("subscription_id")
    invoice_id = invoice_entity.get("id") or raw_payload.get("invoice_id")

    # Timestamp conversion (epoch seconds -> datetime)
    created_at_epoch = raw_payload.get("created_at") or payment_entity.get("created_at")
    if created_at_epoch and isinstance(created_at_epoch, (int, float)):
        ts = datetime.fromtimestamp(created_at_epoch, tz=timezone.utc)
    else:
        ts = datetime.now(timezone.utc)

    normalized = NormalizedEvent(
        event_id=event_id,
        source="razorpay",
        environment=environment,
        event_type=event_type,
        timestamp=ts,
        merchant_id=raw_payload.get("account_id", "mer_default"),
        customer_id=customer_id,
        order_id=order_id,
        payment_id=payment_id,
        subscription_id=subscription_id,
        invoice_id=invoice_id,
        amount=round(amount, 2),
        currency=currency,
        payment_method=payment_method,
        failure_code=error_code,
        failure_reason=error_desc,
        failure_category=failure_cat,
        checkout_stage=raw_payload.get("checkout_stage"),
        attempt_count=raw_payload.get("attempt_count", 1),
        metadata=raw_payload.get("metadata", {}),
    )

    logger.debug(
        "Event normalized successfully",
        event_id=normalized.event_id,
        event_type=normalized.event_type.value,
        amount=normalized.amount,
    )
    return normalized
