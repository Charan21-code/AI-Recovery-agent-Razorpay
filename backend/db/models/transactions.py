"""
SQLAlchemy models for Orders, Payment Attempts, Subscriptions, and Invoices.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.db.base import Base, IDMixin, TimestampMixin


class OrderRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "orders"

    order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(64), default="mer_default", index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False)
    attempts_count: Mapped[int] = mapped_column(Integer, default=0)
    is_recovered: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    payment_attempts: Mapped[list["PaymentAttemptRecord"]] = relationship(
        "PaymentAttemptRecord",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class PaymentAttemptRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "payment_attempts"

    payment_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    order_id: Mapped[Optional[str]] = mapped_column(String(128), ForeignKey("orders.order_id"), index=True, nullable=True)
    customer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(64), default="mer_default", index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="created", nullable=False)
    payment_method: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    failure_code: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)

    order: Mapped[Optional["OrderRecord"]] = relationship("OrderRecord", back_populates="payment_attempts")


class SubscriptionRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "subscriptions"

    subscription_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(64), default="mer_default", index=True, nullable=False)
    plan_name: Mapped[Optional[str]] = mapped_column(String(128), default="Standard Plan")
    recurring_amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    grace_period_days: Mapped[int] = mapped_column(Integer, default=7)
    dunning_attempt_count: Mapped[int] = mapped_column(Integer, default=0)


class InvoiceRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "invoices"

    invoice_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    customer_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    merchant_id: Mapped[str] = mapped_column(String(64), default="mer_default", index=True, nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="issued", nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    aging_days: Mapped[int] = mapped_column(Integer, default=0)
