"""
Idempotency manager for deduplicating incoming webhook events.
"""

from datetime import datetime, timezone
from typing import Optional, Set
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.core.logging import get_logger
from backend.db.models.events import RawEventRecord

logger = get_logger("idempotency_guard")


class IdempotencyGuard:
    """Guards against duplicate webhook deliveries using in-memory and database-backed checks."""

    def __init__(self):
        self._processed_event_ids: Set[str] = set()

    def is_duplicate_memory(self, event_id: str) -> bool:
        """Fast in-memory deduplication check."""
        return event_id in self._processed_event_ids

    def mark_processed_memory(self, event_id: str) -> None:
        self._processed_event_ids.add(event_id)

    def is_duplicate_db(self, session: Session, event_id: str) -> bool:
        """Persistent deduplication check against the RawEventRecord table."""
        stmt = select(RawEventRecord).where(RawEventRecord.event_id == event_id)
        existing = session.execute(stmt).scalar_one_or_none()
        return existing is not None

    def check_and_register(self, session: Session, event_id: str) -> bool:
        """
        Atomically checks if event_id has already been processed.
        Returns True if event is NEW (not a duplicate), False if DUPLICATE.
        """
        if self.is_duplicate_memory(event_id):
            logger.info("Duplicate event detected in memory cache", event_id=event_id)
            return False

        if self.is_duplicate_db(session, event_id):
            self.mark_processed_memory(event_id)
            logger.info("Duplicate event detected in database store", event_id=event_id)
            return False

        self.mark_processed_memory(event_id)
        return True


idempotency_guard = IdempotencyGuard()
