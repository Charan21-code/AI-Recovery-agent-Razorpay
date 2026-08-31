"""
Webhook security utilities and HMAC signature verification for Razorpay.
"""

import hashlib
import hmac
from typing import Optional
from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger("webhook_security")


def generate_razorpay_signature(payload_bytes: bytes, secret: Optional[str] = None) -> str:
    """Generates an HMAC-SHA256 hex digest for testing or payload verification."""
    key = (secret or settings.RAZORPAY_WEBHOOK_SECRET).encode("utf-8")
    return hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()


def verify_razorpay_signature(
    payload_bytes: bytes,
    signature: str,
    secret: Optional[str] = None,
) -> bool:
    """
    Verifies Razorpay HMAC-SHA256 signature against webhook raw payload bytes.
    Uses constant-time comparison to prevent timing attacks.
    """
    if not signature:
        logger.warning("Webhook signature verification failed: signature is empty")
        return False

    key = (secret or settings.RAZORPAY_WEBHOOK_SECRET).encode("utf-8")
    expected_signature = hmac.new(key, payload_bytes, hashlib.sha256).hexdigest()

    is_valid = hmac.compare_digest(expected_signature, signature)
    if not is_valid:
        logger.warning("Webhook signature mismatch", signature=signature)
    return is_valid
