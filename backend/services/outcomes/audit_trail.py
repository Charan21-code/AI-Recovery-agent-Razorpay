"""
Audit Trail Service: Provides an immutable, chronologically ordered trace of every pipeline stage.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.core.logging import get_logger
from backend.db.models.feedback import AuditTrailRecord

logger = get_logger("audit_trail")


class AuditTrailService:
    """
    Maintains a full audit trail of each event's progression:
    Event Ingestion -> Classification -> Context -> Inference -> Proposal -> Policy -> Execution -> Outcome.
    """

    def record_entry(
        self,
        session: Session,
        event_id: str,
        stage: str,
        actor: str,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        decision_id: Optional[str] = None,
        verdict_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        outcome_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> AuditTrailRecord:
        """Appends a new chronological trace record to the audit trail."""
        record = AuditTrailRecord(
            audit_id=f"aud_{uuid.uuid4().hex[:12]}",
            event_id=event_id,
            decision_id=decision_id,
            verdict_id=verdict_id,
            execution_id=execution_id,
            outcome_id=outcome_id,
            stage=stage,
            actor=actor,
            action=action,
            details_json=details or {},
            timestamp=timestamp or datetime.now(timezone.utc),
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        
        logger.info(
            f"Audit log: stage={stage} actor={actor} action={action} event_id={event_id}"
        )
        return record

    def get_trail_for_event(self, session: Session, event_id: str) -> List[AuditTrailRecord]:
        """Retrieves all audit entries for a given event in chronological order."""
        stmt = (
            select(AuditTrailRecord)
            .where(AuditTrailRecord.event_id == event_id)
            .order_by(AuditTrailRecord.timestamp.asc())
        )
        return list(session.execute(stmt).scalars().all())

    def format_readable_timeline(self, session: Session, event_id: str) -> List[Dict[str, Any]]:
        """
        Formats audit trail records into user-friendly timeline cards
        conforming to Section 35 of the product specification.
        """
        records = self.get_trail_for_event(session, event_id)
        timeline = []
        for r in records:
            time_str = r.timestamp.strftime("%H:%M:%S") if r.timestamp else "--:--:--"
            timeline.append({
                "time": time_str,
                "stage": r.stage,
                "actor": r.actor,
                "action": r.action,
                "details": r.details_json,
                "audit_id": r.audit_id,
            })
        return timeline


audit_trail_service = AuditTrailService()
