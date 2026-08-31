"""
Chronological State Store: Maintains live and historical state across customers, orders, and recovery lifecycles.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from backend.core.constants import EventType
from backend.core.logging import get_logger
from backend.db.models.customer import CustomerRecord, CustomerStateSnapshotRecord
from backend.db.models.events import NormalizedEventRecord
from backend.db.models.transactions import (
    InvoiceRecord,
    OrderRecord,
    PaymentAttemptRecord,
    SubscriptionRecord,
)
from backend.schemas.customer import CustomerProfile, CustomerState
from backend.schemas.events import NormalizedEvent

logger = get_logger("state_store")


class StateStore:
    """Manages rolling state for customers, transactions, and recovery lifecycles."""

    def get_or_create_customer_profile(
        self,
        session: Session,
        customer_id: str,
        merchant_id: str = "mer_default",
        name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> CustomerProfile:
        """Retrieves or creates a CustomerProfile."""
        stmt = select(CustomerRecord).where(CustomerRecord.customer_id == customer_id)
        record = session.execute(stmt).scalar_one_or_none()

        if not record:
            record = CustomerRecord(
                customer_id=customer_id,
                merchant_id=merchant_id,
                name=name or "Valued Customer",
                email=email,
                phone=phone,
            )
            session.add(record)
            session.commit()
            session.refresh(record)

        return CustomerProfile(
            customer_id=record.customer_id,
            merchant_id=record.merchant_id,
            name=record.name,
            email=record.email,
            phone=record.phone,
            preferred_language=record.preferred_language,
            is_vip=record.is_vip,
            opted_out_of_outreach=record.opted_out_of_outreach,
            created_at=record.created_at,
        )

    def get_customer_state_as_of(
        self,
        session: Session,
        customer_id: str,
        as_of_timestamp: datetime,
    ) -> CustomerState:
        """
        Computes the rolling CustomerState strictly from events occurring AT OR BEFORE as_of_timestamp.
        Guarantees NO FUTURE DATA LEAKAGE.
        """
        # Query all normalized events for this customer up to as_of_timestamp
        stmt = (
            select(NormalizedEventRecord)
            .where(
                NormalizedEventRecord.customer_id == customer_id,
                NormalizedEventRecord.timestamp <= as_of_timestamp,
            )
            .order_by(NormalizedEventRecord.timestamp.asc())
        )
        events = session.execute(stmt).scalars().all()

        total_tx = 0
        successful_tx = 0
        failed_tx = 0
        total_rev = 0.0
        recovery_attempts = 0
        successful_recoveries = 0
        failed_recoveries = 0
        recovery_times = []

        last_tx_at = None
        last_fail_at = None
        last_intervention_at = None
        recent_interventions = 0
        consecutive_failures = 0

        method_counts: Dict[str, int] = {}

        for ev in events:
            ev_type = ev.event_type
            last_tx_at = ev.timestamp

            if ev.payment_method:
                method_counts[ev.payment_method] = method_counts.get(ev.payment_method, 0) + 1

            if ev_type in [EventType.PAYMENT_SUCCESS.value, EventType.INVOICE_PAID.value]:
                total_tx += 1
                successful_tx += 1
                total_rev += ev.amount
                consecutive_failures = 0
            elif ev_type in [
                EventType.PAYMENT_FAILED.value,
                EventType.CHECKOUT_ABANDONED.value,
                EventType.SUBSCRIPTION_PAYMENT_FAILED.value,
                EventType.INVOICE_OVERDUE.value,
                EventType.MANDATE_FAILED.value,
            ]:
                total_tx += 1
                failed_tx += 1
                last_fail_at = ev.timestamp
                consecutive_failures += 1
            elif ev_type == EventType.RECOVERY_ATTEMPTED.value:
                recovery_attempts += 1
                recent_interventions += 1
                last_intervention_at = ev.timestamp
            elif ev_type == EventType.RECOVERY_SUCCESS.value:
                successful_recoveries += 1
                total_rev += ev.amount
                consecutive_failures = 0
                if "time_to_recovery_minutes" in ev.metadata_json:
                    recovery_times.append(float(ev.metadata_json["time_to_recovery_minutes"]))
            elif ev_type == EventType.RECOVERY_FAILED.value:
                failed_recoveries += 1

        success_rate = (successful_tx / total_tx) if total_tx > 0 else 0.0
        avg_tx_val = (total_rev / successful_tx) if successful_tx > 0 else 0.0
        rec_rate = (successful_recoveries / recovery_attempts) if recovery_attempts > 0 else 0.0
        avg_rec_time = (sum(recovery_times) / len(recovery_times)) if recovery_times else 0.0

        # Compute intervention fatigue score (increases with recent interventions, decays with time)
        fatigue_score = min(1.0, (recent_interventions * 0.25) + (consecutive_failures * 0.15))

        pref_method = max(method_counts, key=method_counts.get) if method_counts else None

        return CustomerState(
            customer_id=customer_id,
            total_transactions=total_tx,
            successful_transactions=successful_tx,
            failed_transactions=failed_tx,
            success_rate=round(success_rate, 4),
            total_revenue_generated=round(total_rev, 2),
            average_transaction_value=round(avg_tx_val, 2),
            total_recovery_attempts=recovery_attempts,
            successful_recoveries=successful_recoveries,
            failed_recoveries=failed_recoveries,
            historical_recovery_rate=round(rec_rate, 4),
            average_recovery_time_minutes=round(avg_rec_time, 2),
            last_transaction_at=last_tx_at,
            last_failure_at=last_fail_at,
            last_intervention_at=last_intervention_at,
            recent_intervention_count=recent_interventions,
            consecutive_failures_count=consecutive_failures,
            intervention_fatigue_score=round(fatigue_score, 4),
            preferred_payment_method=pref_method,
            estimated_clv=round(total_rev * 1.5, 2),
            last_updated_at=as_of_timestamp,
        )

    def record_normalized_event(
        self,
        session: Session,
        event: NormalizedEvent,
    ) -> NormalizedEventRecord:
        """Saves a normalized event and updates transaction/order lifecycles."""
        record = NormalizedEventRecord(
            event_id=event.event_id,
            source=event.source,
            environment=event.environment.value,
            event_type=event.event_type.value,
            timestamp=event.timestamp,
            merchant_id=event.merchant_id,
            customer_id=event.customer_id,
            order_id=event.order_id,
            payment_id=event.payment_id,
            subscription_id=event.subscription_id,
            invoice_id=event.invoice_id,
            amount=event.amount,
            currency=event.currency,
            payment_method=event.payment_method,
            failure_code=event.failure_code,
            failure_reason=event.failure_reason,
            failure_category=event.failure_category.value,
            checkout_stage=event.checkout_stage,
            attempt_count=event.attempt_count,
            is_actionable=event.is_actionable,
            metadata_json=event.metadata,
        )
        session.add(record)

        # Update or create OrderRecord if order_id present
        if event.order_id:
            stmt = select(OrderRecord).where(OrderRecord.order_id == event.order_id)
            order = session.execute(stmt).scalar_one_or_none()
            if not order:
                order = OrderRecord(
                    order_id=event.order_id,
                    customer_id=event.customer_id,
                    merchant_id=event.merchant_id,
                    amount=event.amount,
                    currency=event.currency,
                    status="created",
                    attempts_count=1,
                )
                session.add(order)
            else:
                order.attempts_count += 1
                if event.event_type in [EventType.PAYMENT_SUCCESS, EventType.RECOVERY_SUCCESS]:
                    order.status = "paid"
                    order.is_recovered = True
                elif event.event_type == EventType.PAYMENT_FAILED:
                    order.status = "attempted_failed"

        # Record PaymentAttempt if payment_id present
        if event.payment_id:
            pay_stmt = select(PaymentAttemptRecord).where(PaymentAttemptRecord.payment_id == event.payment_id)
            pay_record = session.execute(pay_stmt).scalar_one_or_none()
            if not pay_record:
                pay_record = PaymentAttemptRecord(
                    payment_id=event.payment_id,
                    order_id=event.order_id,
                    customer_id=event.customer_id,
                    merchant_id=event.merchant_id,
                    amount=event.amount,
                    currency=event.currency,
                    status="captured" if event.event_type == EventType.PAYMENT_SUCCESS else "failed",
                    payment_method=event.payment_method,
                    failure_code=event.failure_code,
                    failure_reason=event.failure_reason,
                    attempt_number=event.attempt_count,
                )
                session.add(pay_record)

        session.commit()
        session.refresh(record)
        return record


state_store = StateStore()
