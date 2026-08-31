"""
Webhook receiver and raw event ingestion handler.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from backend.core.constants import Environment
from backend.core.logging import get_logger
from backend.db.models.events import RawEventRecord
from backend.schemas.events import RawEventPayload
from backend.services.ingestion.idempotency import idempotency_guard
from backend.services.ingestion.security import verify_razorpay_signature

logger = get_logger("webhook_receiver")


def ingest_raw_event(
    session: Session,
    payload_dict: Dict[str, Any],
    payload_bytes: bytes,
    signature: Optional[str],
    source: str = "razorpay",
    environment: Environment = Environment.TEST,
    verify_sig: bool = True,
    webhook_secret: Optional[str] = None,
) -> Tuple[bool, str, Optional[RawEventPayload]]:
    """
    Ingests, validates, verifies signature, deduplicates, and persists a raw event.
    Returns: (is_success, message, RawEventPayload)
    """
    # 1. Extract Event ID
    event_id = payload_dict.get("event_id") or payload_dict.get("id")
    if not event_id:
        # Fallback to payload payment ID or entity ID if event ID is missing
        contains = payload_dict.get("payload", {})
        payment_entity = contains.get("payment", {}).get("entity", {})
        event_id = payment_entity.get("id") or f"evt_gen_{datetime.now(timezone.utc).timestamp()}"

    # 2. Verify Signature if required
    if verify_sig and signature:
        if not verify_razorpay_signature(payload_bytes, signature, secret=webhook_secret):
            logger.warning("Invalid webhook signature rejected", event_id=event_id)
            return False, "Invalid signature", None

    # 3. Idempotency Check
    if not idempotency_guard.check_and_register(session, event_id):
        logger.info("Ignoring duplicate webhook event", event_id=event_id)
        return True, "Duplicate event ignored", None

    # 4. Create and persist RawEventRecord
    raw_payload_model = RawEventPayload(
        event_id=event_id,
        source=source,
        environment=environment,
        raw_payload=payload_dict,
        headers={"X-Razorpay-Signature": signature or ""},
        received_at=datetime.now(timezone.utc),
    )

    db_record = RawEventRecord(
        event_id=raw_payload_model.event_id,
        source=raw_payload_model.source,
        environment=raw_payload_model.environment.value,
        headers=raw_payload_model.headers,
        raw_payload=raw_payload_model.raw_payload,
        is_processed=False,
        received_at=raw_payload_model.received_at,
    )
    session.add(db_record)
    session.commit()

    logger.info("Raw event successfully ingested", event_id=event_id, source=source)
    return True, "Event ingested successfully", raw_payload_model
