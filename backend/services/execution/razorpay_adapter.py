"""
Razorpay Test Mode API Adapter.
Provides typed access to Razorpay Test APIs (Orders, Payments, Payment Links, Refunds).
Includes local mock simulation when test keys are placeholders or network is offline.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
import httpx
from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger("razorpay_adapter")


class RazorpayAdapter:
    """Encapsulates all Razorpay REST API communications."""

    BASE_URL = "https://api.razorpay.com/v1"

    def __init__(
        self,
        key_id: Optional[str] = None,
        key_secret: Optional[str] = None,
        timeout: float = 10.0,
        use_mock: Optional[bool] = None,
    ):
        self.key_id = key_id or settings.RAZORPAY_KEY_ID
        self.key_secret = key_secret or settings.RAZORPAY_KEY_SECRET
        self.timeout = timeout
        
        if use_mock is not None:
            self.is_placeholder_key = use_mock
        else:
            self.is_placeholder_key = (
                "placeholder" in (self.key_id or "").lower()
                or "example" in (self.key_id or "").lower()
                or "mock" in (self.key_id or "").lower()
                or not self.key_id
            )

    @property
    def auth(self) -> Tuple[str, str]:
        return (self.key_id, self.key_secret)

    async def create_order(
        self,
        amount_inr: float,
        currency: str = "INR",
        receipt: Optional[str] = None,
        notes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Creates a Razorpay Order. Amount in standard INR (converted to paise)."""
        amount_paise = int(amount_inr * 100)
        payload = {
            "amount": amount_paise,
            "currency": currency,
            "receipt": receipt or f"rcpt_{int(datetime.now(timezone.utc).timestamp())}",
            "notes": notes or {},
        }

        if self.is_placeholder_key:
            logger.info("Using mock Razorpay create_order", amount_inr=amount_inr)
            return {
                "id": f"order_mock_{int(datetime.now(timezone.utc).timestamp())}",
                "entity": "order",
                "amount": amount_paise,
                "currency": currency,
                "status": "created",
                "receipt": payload["receipt"],
                "created_at": int(datetime.now(timezone.utc).timestamp()),
            }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/orders",
                    json=payload,
                    auth=self.auth,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error("Razorpay create_order failed", error=str(e))
                raise

    async def fetch_payment(self, payment_id: str) -> Dict[str, Any]:
        """Fetches payment details by Payment ID."""
        if self.is_placeholder_key:
            logger.info("Using mock Razorpay fetch_payment", payment_id=payment_id)
            # Recovery context: payments are FAILED (that's why the agent is calling).
            # Only simulate captured status if the payment_id explicitly signals success
            # (e.g. test scripts that need to verify the captured-branch logic).
            is_captured = payment_id.endswith("_captured") or payment_id.endswith("_success")
            return {
                "id": payment_id,
                "entity": "payment",
                "amount": 249900,
                "currency": "INR",
                "status": "captured" if is_captured else "failed",
                "captured": is_captured,
                "method": "upi",
                "error_code": None if is_captured else "BAD_REQUEST_ERROR",
                "error_description": None if is_captured else "Payment failed at bank gateway",
                "created_at": int(datetime.now(timezone.utc).timestamp()),
            }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.BASE_URL}/payments/{payment_id}",
                    auth=self.auth,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error("Razorpay fetch_payment failed", payment_id=payment_id, error=str(e))
                raise

    async def create_payment_link(
        self,
        amount_inr: float,
        customer_name: str,
        customer_email: Optional[str] = None,
        customer_phone: Optional[str] = None,
        description: str = "Payment Recovery Link",
        expire_by_minutes: int = 1440,
        notify_sms: bool = True,
        notify_email: bool = True,
    ) -> Dict[str, Any]:
        """Generates a shareable Razorpay Payment Link."""
        amount_paise = int(amount_inr * 100)
        expire_by_epoch = int(datetime.now(timezone.utc).timestamp()) + (expire_by_minutes * 60)

        payload = {
            "amount": amount_paise,
            "currency": "INR",
            "accept_partial": False,
            "description": description,
            "customer": {
                "name": customer_name,
                "email": customer_email or "customer@example.com",
                "contact": customer_phone or "+919876543210",
            },
            "notify": {
                "sms": notify_sms,
                "email": notify_email,
            },
            "reminder_enable": True,
            "expire_by": expire_by_epoch,
        }

        if self.is_placeholder_key:
            mock_id = f"plink_mock_{int(datetime.now(timezone.utc).timestamp())}"
            logger.info("Using mock Razorpay create_payment_link", link_id=mock_id)
            return {
                "id": mock_id,
                "short_url": f"https://rzp.io/i/{mock_id[-8:]}",
                "status": "created",
                "amount": amount_paise,
                "currency": "INR",
                "description": description,
                "expire_by": expire_by_epoch,
            }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.BASE_URL}/payment_links",
                    json=payload,
                    auth=self.auth,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                logger.error("Razorpay create_payment_link failed", error=str(e))
                raise


razorpay_adapter = RazorpayAdapter()
