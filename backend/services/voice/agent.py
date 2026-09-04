"""
Voice Recovery Agent: Multi-turn, multilingual conversational agent for payment recovery.
Adheres to strict security invariants (no OTP/CVV collection, verified capture checks, tool calling).
Handles 14 distinct customer intents with proper context tracking across turns.
"""

import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.services.voice.tools import voice_recovery_tools

logger = get_logger("voice_agent")


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    result: Dict[str, Any]


class VoiceTurn(BaseModel):
    turn_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    language: str = "en"
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)


class VoiceSession(BaseModel):
    session_id: str
    customer_id: str
    payment_id: str
    customer_name: str = "Customer"
    customer_phone: str = "+919876543210"
    amount: float = 2499.00
    currency: str = "INR"
    failure_reason: str = "Bank timeout"
    status: str = "active"  # "active"|"completed"|"escalated"|"scheduled"|"refused"|"disputed"
    language_preference: str = "hinglish"
    turns: List[VoiceTurn] = Field(default_factory=list)
    recorded_intent: Optional[str] = None
    # ── Multi-turn context flags ──────────────────────────────────────────────
    payment_link_sent: bool = False
    status_checked: bool = False
    dispute_filed: bool = False
    refund_requested: bool = False


class VoiceRecoveryAgent:
    """
    Autonomous AI Voice Recovery Agent.
    Priority-ordered intent detection (14 intents), strict security invariants,
    dynamic failure-reason-aware greeting, and full conversation history for LLM fallback.
    """

    def __init__(self):
        self._sessions: Dict[str, VoiceSession] = {}
        self.api_key = settings.LLM_API_KEY or os.environ.get("GEMINI_API_KEY")
        self.model = settings.LLM_MODEL or "gemini-2.5-flash"
        self.provider = settings.LLM_PROVIDER

    # ── Public API ────────────────────────────────────────────────────────────

    def start_session(
        self,
        customer_id: str,
        payment_id: str,
        language: str = "hinglish",
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        amount: Optional[float] = None,
        failure_reason: Optional[str] = None,
    ) -> VoiceSession:
        """Initializes a voice recovery session and generates the personalized greeting."""
        details = voice_recovery_tools.get_payment_details(payment_id, customer_id)
        session_id = f"vcall_{str(uuid.uuid4())[:8]}"

        name = customer_name or details.get("customer_name") or "Valued Customer"
        phone = customer_phone or details.get("customer_phone") or "+919876543210"
        amt = amount if amount is not None else details.get("amount", 2499.00)
        reason = failure_reason or details.get("failure_reason") or "Bank timeout"

        session = VoiceSession(
            session_id=session_id,
            customer_id=customer_id,
            payment_id=payment_id,
            customer_name=name,
            customer_phone=phone,
            amount=amt,
            currency=details.get("currency", "INR"),
            failure_reason=reason,
            language_preference=language,
        )

        greeting = self._generate_greeting(session)
        turn = VoiceTurn(role="assistant", content=greeting, language=session.language_preference)
        session.turns.append(turn)
        self._sessions[session_id] = session

        logger.info(
            f"Started voice session {session_id} for {session.customer_name} "
            f"(Rs.{session.amount:,.2f}, reason: {session.failure_reason})"
        )
        return session

    def get_session(self, session_id: str) -> Optional[VoiceSession]:
        return self._sessions.get(session_id)

    def process_turn(self, session_id: str, user_speech: str) -> VoiceTurn:
        """
        Processes a single conversational turn. Priority-ordered intent detection:
        1. Security violation   8. Discount negotiation
        2. Session ended guard  9. Payment link request
        3. Wrong number         10. Retry payment
        4. Hard refusal         11. Schedule callback
        5. Already paid (other) 12. Human escalation
        6. Money deducted       13. Follow-up on prior actions
        7. Refund request       14. LLM / contextual fallback
        """
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Voice session '{session_id}' not found.")

        # ── Guard: session already terminated ────────────────────────────────
        if session.status in ("completed", "refused"):
            lang = session.language_preference
            if lang in ("hi", "hinglish"):
                msg = (
                    f"Dhanyawad {session.customer_name} ji! "
                    f"Hamari conversation pehle hi close ho chuki hai. "
                    f"Aur madad ke liye 1800-XXX-XXXX par call karein."
                )
            else:
                msg = (
                    f"Thank you, {session.customer_name}. "
                    f"This conversation has already ended. "
                    f"For further help, please call 1800-XXX-XXXX."
                )
            turn = VoiceTurn(role="assistant", content=msg, language=lang)
            session.turns.append(turn)
            return turn

        # ── Detect language and record user turn ──────────────────────────────
        detected_lang = self._detect_language(user_speech, session.language_preference)
        session.language_preference = detected_lang
        user_turn = VoiceTurn(role="user", content=user_speech, language=detected_lang)
        session.turns.append(user_turn)

        speech_lower = user_speech.lower().strip()
        tool_records: List[ToolCallRecord] = []
        assistant_reply = ""

        # ══ PRIORITY 1: Security Invariant — Zero Credential Collection ══════
        security_intervention = self._check_security_violations(user_speech, detected_lang)
        if security_intervention:
            agent_turn = VoiceTurn(role="assistant", content=security_intervention, language=detected_lang)
            session.turns.append(agent_turn)
            return agent_turn

        # ══ PRIORITY 2: Wrong Number ══════════════════════════════════════════
        if self._hit(speech_lower, [
            "wrong number", "galat number", "wrong person", "galat aadmi",
            "i am not", "main nahi hoon", "yeh number galat", "who are you calling",
            "not the right person", "aap galat jagah", "i don't know about this payment",
            "koi aur hoga", "mujhe nahi pata razorpay"
        ]) and not self._hit(speech_lower, ["link", "payment", "paise", "retry", "help"]):
            session.status = "completed"
            session.recorded_intent = "WRONG_NUMBER"
            voice_recovery_tools.record_customer_intent(
                session.customer_id, session.payment_id, "WRONG_NUMBER", "NEUTRAL", "Wrong number reached"
            )
            if detected_lang in ("hi", "hinglish"):
                assistant_reply = (
                    f"Arre, bahut maafi chahta hoon! Lagta hai humne galat number par call kar diya. "
                    f"Aapko disturb karne ke liye genuinely sorry. "
                    f"Aapka din bilkul achha rahe!"
                )
            else:
                assistant_reply = (
                    f"Oh, I sincerely apologize! It seems we've reached the wrong number. "
                    f"We are very sorry to have disturbed you. "
                    f"Have a wonderful day!"
                )

        # ══ PRIORITY 3: Hard Refusal / Opt-Out ════════════════════════════════
        elif self._hit(speech_lower, [
            "not interested", "nahi chahiye", "mujhe nahi chahiye", "don't call me",
            "mat karo call", "stop calling", "remove my number", "mera number hata",
            "do not disturb", "dnd", "leave me alone", "go away", "don't want",
            "no thank", "band karo", "mere peeche se hato", "harass", "spam"
        ]) and not self._hit(speech_lower, [
            "link", "payment link", "whatsapp", "retry", "schedule callback"
        ]):
            session.status = "refused"
            session.recorded_intent = "REFUSAL"
            voice_recovery_tools.record_customer_intent(
                session.customer_id, session.payment_id, "REFUSAL", "NEGATIVE",
                f"Customer refused: {user_speech[:100]}"
            )
            if detected_lang in ("hi", "hinglish"):
                assistant_reply = (
                    f"Ji zaroor {session.customer_name} ji. Aapki preference main note kar raha hoon. "
                    f"Aapko is payment ke baare mein dobara contact nahi kiya jayega. "
                    f"Agar kabhi bhi razorpay se help chahiye, 1800-XXX-XXXX par call karein. "
                    f"Aapka din shubh ho!"
                )
            else:
                assistant_reply = (
                    f"Absolutely understood, {session.customer_name}. "
                    f"I've noted your preference — you will not be contacted again regarding this payment. "
                    f"If you ever need help from Razorpay, please call 1800-XXX-XXXX. "
                    f"Have a great day!"
                )

        # ══ PRIORITY 4: Claimed Already Paid via a Different Method ═══════════
        # Distinct from "paise kat gaye" — this is an explicit "I already paid separately"
        elif self._hit(speech_lower, [
            "already paid", "paid already", "already done", "dusre se pay", "different method",
            "by card paid", "net banking se diya", "by gpay", "by phonepe", "ne pay kar diya",
            "done kar diya", "completed already", "pay kar chuka hoon", "pehle se pay kar diya",
            "maine pay kar diya", "payment kar di"
        ]) and not self._hit(speech_lower, [
            "paise kat", "kat gaye", "debit ho gaye", "bank se kat", "cut ho gaya"
        ]):
            status_res = voice_recovery_tools.get_payment_status(session.payment_id)
            tool_records.append(ToolCallRecord(
                tool_name="get_payment_status",
                arguments={"payment_id": session.payment_id},
                result=status_res,
            ))
            session.status_checked = True

            if status_res.get("captured"):
                session.status = "completed"
                session.recorded_intent = "ALREADY_PAID_CONFIRMED"
                voice_recovery_tools.record_customer_intent(
                    session.customer_id, session.payment_id, "ALREADY_PAID", "POSITIVE",
                    "Payment captured verified after customer claim"
                )
                if detected_lang in ("hi", "hinglish"):
                    assistant_reply = (
                        f"Bilkul sahi kaha {session.customer_name} ji! Maine abhi gateway par verify kiya — "
                        f"aapka Rs. {session.amount:,.2f} ka payment successfully capture ho chuka hai. "
                        f"Koi aur action ki zaroorat nahi. Bahut shukriya aur aapka din shubh ho!"
                    )
                else:
                    assistant_reply = (
                        f"That's confirmed, {session.customer_name}! I've just verified with our gateway — "
                        f"your payment of Rs. {session.amount:,.2f} has been successfully captured. "
                        f"No further action needed. Thank you so much and have a wonderful day!"
                    )
            else:
                # Customer claims paid but our system doesn't show it — ask for clarification
                session.recorded_intent = "CLAIMED_PAID_NOT_CONFIRMED"
                if detected_lang in ("hi", "hinglish"):
                    assistant_reply = (
                        f"Samjha {session.customer_name} ji. Lekin maine abhi check kiya — "
                        f"humare system mein aapka payment abhi bhi pending dikha raha hai. "
                        f"Agar aapne koi doosri method se pay kiya hai, toh bank mein reflect hone mein "
                        f"thodi der lag sakti hai. "
                        f"Kya aap bata sakte hain — UPI se kiya, card se, ya netbanking se? "
                        f"Main us method se confirm karne ki koshish karta hoon."
                    )
                else:
                    assistant_reply = (
                        f"I understand, {session.customer_name}. However, I've just checked — "
                        f"our system still shows the payment as pending. "
                        f"If you've paid via another method, it may take a few moments to reflect. "
                        f"Could you tell me which method you used — UPI, card, or netbanking? "
                        f"I can help track it down."
                    )

        # ══ PRIORITY 5: Money Deducted Dispute ════════════════════════════════
        # Customer says money was taken from their bank but our system shows failed
        elif self._hit(speech_lower, [
            "paise kat gaye", "paise kat gaya", "money deducted", "bank se kat gaya",
            "account se kat gaya", "debit ho gaya", "debit ho gaye", "cut from bank",
            "cut ho gaya", "already deducted", "balance kat gaya", "paisa gaya",
            "mere paise gaye", "kat liye", "paise chale gaye", "transaction hua",
            "money cut", "money gone", "bank ne le liya", "bank cut money"
        ]):
            status_res = voice_recovery_tools.get_payment_status(session.payment_id)
            tool_records.append(ToolCallRecord(
                tool_name="get_payment_status",
                arguments={"payment_id": session.payment_id},
                result=status_res,
            ))
            session.status_checked = True

            if status_res.get("captured"):
                # Edge case: somehow it IS captured — deduction is legitimate
                session.status = "completed"
                session.recorded_intent = "PAYMENT_CAPTURED_CONFIRMED"
                if detected_lang in ("hi", "hinglish"):
                    assistant_reply = (
                        f"Aapki baat sunne ke liye shukriya {session.customer_name} ji. "
                        f"Maine gateway par check kiya — aapka Rs. {session.amount:,.2f} ka payment "
                        f"successfully capture ho chuka hai. "
                        f"Jo paise deduct hue hain woh legitimate transaction hai, aapka order confirm hai. "
                        f"Kya aapko koi transaction reference ID chahiye confirmation ke liye?"
                    )
                else:
                    assistant_reply = (
                        f"Thank you for reaching out, {session.customer_name}. "
                        f"I've checked with our gateway — your payment of Rs. {session.amount:,.2f} "
                        f"has been successfully captured. "
                        f"The amount debited from your account is for this transaction, and your order is confirmed. "
                        f"Would you like a transaction reference ID for your records?"
                    )
            else:
                # ── TRUE DISPUTE: Money debited from bank but payment gateway shows failed ──
                # This is a bank settlement timing issue. File a dispute ticket immediately.
                if not session.dispute_filed:
                    dispute_res = voice_recovery_tools.file_dispute_complaint(
                        customer_id=session.customer_id,
                        payment_id=session.payment_id,
                        claim_amount=session.amount,
                        description=f"Customer reports deduction: {user_speech[:200]}",
                    )
                    tool_records.append(ToolCallRecord(
                        tool_name="file_dispute_complaint",
                        arguments={
                            "customer_id": session.customer_id,
                            "payment_id": session.payment_id,
                            "claim_amount": session.amount,
                        },
                        result=dispute_res,
                    ))
                    session.dispute_filed = True
                    ticket_id = dispute_res.get("ticket_id", "DISP-XXXX")
                else:
                    ticket_id = "DISP-already-filed"

                session.recorded_intent = "DISPUTE_DEBITED"
                session.status = "disputed"
                voice_recovery_tools.record_customer_intent(
                    session.customer_id, session.payment_id, "DISPUTE_DEBITED", "FRUSTRATED",
                    f"Dispute filed #{ticket_id}. Customer claims deduction."
                )

                if detected_lang in ("hi", "hinglish"):
                    assistant_reply = (
                        f"Main poori tarah samajh raha hoon {session.customer_name} ji, "
                        f"aur aapki ye chinta bilkul valid hai. "
                        f"Maine abhi check kiya — humare gateway par is payment ka status 'failed' hai. "
                        f"Iska matlab yeh hai ki bank aur gateway ke beech settlement pending hai. "
                        f"Ghabrane ki bilkul zaroorat nahi — agar aapke account se "
                        f"Rs. {session.amount:,.2f} debit hue hain, "
                        f"toh aapka bank automatically 3 se 5 working days mein "
                        f"yeh amount reverse kar dega bina kisi action ke. "
                        f"Aur maine aapke liye dispute ticket #{ticket_id} create kar diya hai "
                        f"jisse hum monitor kar saken. "
                        f"Kya aap tab tak ek fresh payment link chahenge taaki aapka order delay na ho, "
                        f"ya aap bank reversal ka wait karna chahte hain?"
                    )
                else:
                    assistant_reply = (
                        f"I completely understand your concern, {session.customer_name}, "
                        f"and you are absolutely right to flag this. "
                        f"I've just checked — our payment gateway shows this transaction as 'failed'. "
                        f"This means there is a pending bank-gateway settlement. "
                        f"Please do NOT worry — if Rs. {session.amount:,.2f} was debited from your account, "
                        f"your bank will automatically reverse the amount within 3 to 5 working days "
                        f"with no action required from you. "
                        f"I've also raised dispute ticket #{ticket_id} on your behalf so we can monitor it. "
                        f"Would you like a fresh payment link to avoid order delays, "
                        f"or would you prefer to wait for the bank reversal?"
                    )

        # ══ PRIORITY 6: Refund Request ════════════════════════════════════════
        elif self._hit(speech_lower, [
            "refund", "money back", "wapas karo", "paise wapas", "return my money",
            "cancel order", "order cancel karo", "don't want the order",
            "order nahi chahiye", "paisa wapas chahiye", "want refund",
            "give me back my money", "mujhe refund do"
        ]):
            if not session.refund_requested:
                refund_res = voice_recovery_tools.send_refund_request(
                    payment_id=session.payment_id,
                    customer_id=session.customer_id,
                    reason=f"Customer requested refund: {user_speech[:100]}",
                    amount=session.amount,
                )
                tool_records.append(ToolCallRecord(
                    tool_name="send_refund_request",
                    arguments={"payment_id": session.payment_id, "customer_id": session.customer_id},
                    result=refund_res,
                ))
                session.refund_requested = True
                refund_ticket = refund_res.get("refund_ticket_id", "REF-XXXX")
            else:
                refund_ticket = "REF-already-submitted"

            session.recorded_intent = "REFUND_REQUESTED"
            voice_recovery_tools.record_customer_intent(
                session.customer_id, session.payment_id, "REFUND_REQUESTED", "NEGATIVE",
                "Refund requested during voice interaction"
            )

            if detected_lang in ("hi", "hinglish"):
                assistant_reply = (
                    f"Ji bilkul samajha {session.customer_name} ji. "
                    f"Maine aapka refund request #{refund_ticket} submit kar diya hai. "
                    f"Refund 5 se 7 working days mein aapke original payment source "
                    f"(bank/card) mein credit ho jayega. "
                    f"Aapke registered mobile par confirmation SMS milega. "
                    f"Kya main kuch aur help kar sakta hoon?"
                )
            else:
                assistant_reply = (
                    f"Understood, {session.customer_name}. "
                    f"I've submitted your refund request #{refund_ticket}. "
                    f"The amount will be credited to your original payment source within 5 to 7 business days. "
                    f"You'll receive a confirmation SMS on your registered mobile. "
                    f"Is there anything else I can help you with?"
                )

        # ══ PRIORITY 7: Technical Inquiry (Why did it fail?) ═════════════════
        elif self._hit(speech_lower, [
            "why fail", "kyun fail", "kya hua", "kya problem thi", "what happened",
            "why failed", "failure reason", "kya galat hua", "error kya tha",
            "issue kya tha", "problem kya hai", "reason batao", "tell me why",
            "bank ne kyun", "what went wrong", "kaise fail", "samjhao",
            "explain karo", "kya issue tha"
        ]):
            reason_explanation = self._explain_failure_reason(
                session.failure_reason, detected_lang, session.amount
            )
            if detected_lang in ("hi", "hinglish"):
                assistant_reply = (
                    f"Zaroor {session.customer_name} ji, main explain karta hoon. "
                    f"{reason_explanation} "
                    f"Yeh aapki koi galti nahi thi. "
                    f"Kya main abhi aapko ek fresh secure payment link bhejun?"
                )
            else:
                assistant_reply = (
                    f"Of course, {session.customer_name}. {reason_explanation} "
                    f"This was absolutely not your fault. "
                    f"Shall I send you a fresh secure payment link right now?"
                )

        # ══ PRIORITY 8: Discount Negotiation ══════════════════════════════════
        elif self._hit(speech_lower, [
            "discount", "offer de do", "less amount", "kuch kam karo", "thoda kam",
            "bargain", "reduce amount", "cashback chahiye", "coupon hai", "concession",
            "kuch toh milega", "waiver", "price kam karo", "negotiate"
        ]):
            if detected_lang in ("hi", "hinglish"):
                assistant_reply = (
                    f"Haha, main aapki baat samajhta hoon {session.customer_name} ji! "
                    f"Is particular transaction par main discount authorize nahi kar sakta, "
                    f"yeh policy-bound hai. "
                    f"Lekin aapka account note kar diya gaya hai — merchant ke future offers "
                    f"aur cashback aapko milenge. "
                    f"Abhi ke liye, kya main Rs. {session.amount:,.2f} ka ek secure payment link bhejun?"
                )
            else:
                assistant_reply = (
                    f"I appreciate your ask, {session.customer_name}! "
                    f"I'm unable to authorize a discount on this transaction — it's policy-bound. "
                    f"However, your account has been flagged for future merchant offers and cashback benefits. "
                    f"For now, may I send you a secure payment link for Rs. {session.amount:,.2f}?"
                )

        # ══ PRIORITY 9: Payment Link Request ══════════════════════════════════
        elif self._hit(speech_lower, [
            "send link", "link bhej", "link bhejdo", "bhej do", "whatsapp link",
            "pay now", "how to pay", "payment link do", "send payment link",
            "link send karo", "mujhe link bhejo", "share link", "online pay karna hai",
            "link chahiye", "payment karna hai"
        ]):
            if session.payment_link_sent:
                # Already sent — ask if received
                if detected_lang in ("hi", "hinglish"):
                    assistant_reply = (
                        f"Maine pehle hi {session.customer_phone} par link bhej diya tha "
                        f"{session.customer_name} ji! "
                        f"Kya aapko WhatsApp ya SMS notification mili? "
                        f"Agar nahi mili, main dobara bhej sakta hoon — chahiye?"
                    )
                else:
                    assistant_reply = (
                        f"I already sent the link to {session.customer_phone}, {session.customer_name}! "
                        f"Did you receive the WhatsApp or SMS notification? "
                        f"If not, I can resend it — would you like that?"
                    )
            else:
                link_res = voice_recovery_tools.create_payment_link(
                    customer_id=session.customer_id,
                    amount=session.amount,
                    customer_name=session.customer_name,
                    customer_phone=session.customer_phone,
                )
                tool_records.append(ToolCallRecord(
                    tool_name="create_payment_link",
                    arguments={"customer_id": session.customer_id, "amount": session.amount},
                    result=link_res,
                ))
                session.payment_link_sent = True
                session.recorded_intent = "PROMISE_TO_PAY"
                voice_recovery_tools.record_customer_intent(
                    session.customer_id, session.payment_id, "PROMISE_TO_PAY", "POSITIVE",
                    "Payment link dispatched on customer request"
                )
                if detected_lang in ("hi", "hinglish"):
                    assistant_reply = (
                        f"Ho gaya {session.customer_name} ji! "
                        f"Maine aapke {session.customer_phone} par WhatsApp aur SMS ke zariye "
                        f"ek 1-click secure Razorpay payment link bhej diya hai. "
                        f"UPI, card, ya netbanking — kisi se bhi pay kar sakte hain. "
                        f"Link sirf 24 ghante ke liye valid hai. Kya link aaya?"
                    )
                else:
                    assistant_reply = (
                        f"Done, {session.customer_name}! "
                        f"I've sent a secure 1-click Razorpay payment link to {session.customer_phone} "
                        f"via WhatsApp and SMS. "
                        f"You can pay using UPI, card, or netbanking. The link is valid for 24 hours. "
                        f"Please let me know once you receive it!"
                    )

        # ══ PRIORITY 10: Retry Payment ════════════════════════════════════════
        elif self._hit(speech_lower, [
            "retry", "try again", "phir se try", "koshish karo", "dobara try",
            "please try", "attempt again", "re-initiate", "phir karo", "again karo"
        ]):
            retry_res = voice_recovery_tools.retry_payment(session.payment_id, preferred_method="upi")
            tool_records.append(ToolCallRecord(
                tool_name="retry_payment",
                arguments={"payment_id": session.payment_id, "preferred_method": "upi"},
                result=retry_res,
            ))
            if retry_res.get("status") == "already_captured":
                session.status = "completed"
                session.recorded_intent = "PAYMENT_CAPTURED_CONFIRMED"
                if detected_lang in ("hi", "hinglish"):
                    assistant_reply = (
                        f"Khushkhabri! Aapka payment pehle hi successfully capture ho chuka hai "
                        f"{session.customer_name} ji. Koi retry ki zaroorat nahi."
                    )
                else:
                    assistant_reply = (
                        f"Great news, {session.customer_name}! "
                        f"Your payment has already been successfully captured. No retry needed."
                    )
            else:
                if detected_lang in ("hi", "hinglish"):
                    assistant_reply = (
                        f"Maine UPI retry initiate kar diya hai {session.customer_name} ji. "
                        f"Aapke Google Pay/PhonePe/Paytm app par ek authorization request aayegi — "
                        f"wahan se confirm kar den. "
                        f"Agar UPI mein issue ho toh main WhatsApp payment link bhi bhej sakta hoon."
                    )
                else:
                    assistant_reply = (
                        f"I've initiated a UPI retry for your transaction, {session.customer_name}. "
                        f"Please check your Google Pay/PhonePe/Paytm app for the authorization request. "
                        f"If UPI doesn't work, I can also send a payment link via WhatsApp."
                    )

        # ══ PRIORITY 11: Schedule Callback ════════════════════════════════════
        elif self._hit(speech_lower, [
            "busy", "call later", "kal call", "baad mein call", "later call",
            "evening mein", "tomorrow call", "drive kar raha", "driving", "meeting mein",
            "in a meeting", "not now", "abhi nahi", "ghar pahunch ke", "after some time",
            "thodi der mein", "give me time", "time de do", "remind me later",
            "call back"
        ]):
            sched_time = self._extract_schedule_time(speech_lower)
            sched_res = voice_recovery_tools.schedule_recovery(
                customer_id=session.customer_id,
                payment_id=session.payment_id,
                channel="voice",
                scheduled_time_iso=sched_time,
                notes=f"Customer speech: {user_speech[:100]}",
            )
            tool_records.append(ToolCallRecord(
                tool_name="schedule_recovery",
                arguments={"customer_id": session.customer_id, "channel": "voice", "time": sched_time},
                result=sched_res,
            ))
            session.status = "scheduled"
            session.recorded_intent = "SCHEDULED_CALLBACK"
            voice_recovery_tools.record_customer_intent(
                session.customer_id, session.payment_id, "SCHEDULED_CALLBACK", "NEUTRAL",
                f"Callback scheduled: {sched_time}"
            )
            if detected_lang in ("hi", "hinglish"):
                assistant_reply = (
                    f"Bilkul samajh gaya {session.customer_name} ji, disturb nahi karunga. "
                    f"Maine aapka callback {sched_time} ke liye schedule kar diya hai. "
                    f"Agar khud call karna ho toh 1800-XXX-XXXX par call karein. "
                    f"Aapka time dene ke liye shukriya!"
                )
            else:
                assistant_reply = (
                    f"Absolutely, {session.customer_name} — I won't keep you. "
                    f"I've scheduled a callback for {sched_time}. "
                    f"You can also reach us anytime at 1800-XXX-XXXX. "
                    f"Thank you for your time!"
                )

        # ══ PRIORITY 12: Human Escalation ═════════════════════════════════════
        elif self._hit(speech_lower, [
            "human", "manager", "senior", "supervisor", "real person", "agent se baat",
            "support agent", "fraud", "scam", "cheating", "lodge complaint",
            "consumer court", "police", "legal action", "gussa hai", "complaint karna hai",
            "dispute raise", "escalate", "help nahi hua", "fed up", "disgusted"
        ]):
            priority = "HIGH" if self._hit(speech_lower, [
                "fraud", "scam", "police", "legal", "consumer court", "cheating"
            ]) else "MEDIUM"
            esc_res = voice_recovery_tools.escalate_to_human(
                customer_id=session.customer_id,
                reason=user_speech[:200],
                priority=priority,
            )
            tool_records.append(ToolCallRecord(
                tool_name="escalate_to_human",
                arguments={"customer_id": session.customer_id, "priority": priority},
                result=esc_res,
            ))
            session.status = "escalated"
            session.recorded_intent = "ESCALATED"
            voice_recovery_tools.record_customer_intent(
                session.customer_id, session.payment_id, "ESCALATED", "FRUSTRATED",
                f"Escalated ({priority}): {user_speech[:100]}"
            )
            if detected_lang in ("hi", "hinglish"):
                assistant_reply = (
                    f"Main aapki frustration poori tarah samajhta hoon {session.customer_name} ji "
                    f"aur genuinely apologize karta hoon. "
                    f"Maine aapka case turant ek senior payment specialist ko transfer kar diya hai "
                    f"(Ticket #{esc_res.get('ticket_id')}). "
                    f"Hamari team 2–4 ghante mein aapse personally call karegi. "
                    f"Ticket number note karein: #{esc_res.get('ticket_id')}."
                )
            else:
                assistant_reply = (
                    f"I completely understand your frustration, {session.customer_name}, "
                    f"and I sincerely apologize for the experience. "
                    f"I've immediately escalated your case to a senior payment specialist "
                    f"(Ticket #{esc_res.get('ticket_id')}). "
                    f"Our team will personally call you within 2–4 hours. "
                    f"Please save your ticket number: #{esc_res.get('ticket_id')}."
                )

        # ══ PRIORITY 13: Follow-up on Prior Actions ════════════════════════════
        elif self._hit(speech_lower, [
            "link aaya", "link mila", "link received", "got the link", "link nahi aaya",
            "link nahi mila", "no link", "not received", "kab aayega", "when will",
            "status kya", "kuch hua", "update do", "what happened", "kya progress",
            "ho gaya kya", "sorted", "resolved"
        ]):
            if session.payment_link_sent:
                if self._hit(speech_lower, ["nahi", "not", "no link", "nahi mila", "nahi aaya"]):
                    # Resend
                    link_res = voice_recovery_tools.create_payment_link(
                        customer_id=session.customer_id,
                        amount=session.amount,
                        customer_name=session.customer_name,
                        customer_phone=session.customer_phone,
                    )
                    tool_records.append(ToolCallRecord(
                        tool_name="create_payment_link",
                        arguments={
                            "customer_id": session.customer_id,
                            "amount": session.amount,
                            "resend": True,
                        },
                        result=link_res,
                    ))
                    if detected_lang in ("hi", "hinglish"):
                        assistant_reply = (
                            f"Maafi {session.customer_name} ji! Maine abhi dobara link bhej diya hai "
                            f"{session.customer_phone} par. "
                            f"Check karein WhatsApp mein — agar spam folder mein ho toh wahan bhi dekhein."
                        )
                    else:
                        assistant_reply = (
                            f"I apologize, {session.customer_name}! I've just resent the link to "
                            f"{session.customer_phone}. "
                            f"Please check WhatsApp — also check your spam folder if you don't see it."
                        )
                else:
                    if detected_lang in ("hi", "hinglish"):
                        assistant_reply = (
                            f"Bahut achha {session.customer_name} ji! "
                            f"Payment ho gayi toh aapka order immediately confirm ho jayega. "
                            f"Kya aur kuch chahiye?"
                        )
                    else:
                        assistant_reply = (
                            f"Wonderful, {session.customer_name}! "
                            f"Once payment is complete, your order will be confirmed instantly. "
                            f"Is there anything else you need?"
                        )
            elif session.dispute_filed:
                if detected_lang in ("hi", "hinglish"):
                    assistant_reply = (
                        f"Aapka dispute case under review hai {session.customer_name} ji. "
                        f"Bank auto-reversal 3–5 working days mein ho jayega. "
                        f"Koi update aane par aapko SMS milega."
                    )
                else:
                    assistant_reply = (
                        f"Your dispute case is under review, {session.customer_name}. "
                        f"The bank auto-reversal will happen within 3–5 working days. "
                        f"You'll receive an SMS update when it's processed."
                    )
            else:
                assistant_reply = self._generate_conversational_reply(session, user_speech, detected_lang)

        # ══ PRIORITY 14: LLM / Contextual Fallback ════════════════════════════
        else:
            assistant_reply = self._generate_conversational_reply(session, user_speech, detected_lang)

        agent_turn = VoiceTurn(
            role="assistant",
            content=assistant_reply,
            language=detected_lang,
            tool_calls=tool_records,
        )
        session.turns.append(agent_turn)
        return agent_turn

    # ── Greeting ──────────────────────────────────────────────────────────────

    def _generate_greeting(self, session: VoiceSession) -> str:
        """Generates the opening greeting with failure-reason-specific language."""
        reason_phrase = self._get_failure_intro(session.failure_reason, session.language_preference)
        if session.language_preference in ("hi", "hinglish"):
            return (
                f"Namaste {session.customer_name} ji! Main Razorpay se call kar raha hoon "
                f"hamari merchant partner ki taraf se. "
                f"Aapka Rs. {session.amount:,.2f} ka recent payment {reason_phrase} "
                f"Main aapki is issue ko quickly resolve karne mein madad karna chahta hoon. "
                f"Kya main {session.customer_name} ji se baat kar raha hoon?"
            )
        else:
            return (
                f"Hello {session.customer_name}! I'm calling from Razorpay on behalf of our merchant partner. "
                f"Your recent payment of Rs. {session.amount:,.2f} {reason_phrase} "
                f"I'm here to help you resolve this quickly and easily. "
                f"Am I speaking with {session.customer_name}?"
            )

    def _get_failure_intro(self, failure_reason: str, lang: str) -> str:
        """Short failure intro phrase for the greeting — maps reason to natural language."""
        r = failure_reason.lower()
        if lang in ("hi", "hinglish"):
            if "timeout" in r or "gateway" in r:
                return "bank gateway timeout ki wajah se complete nahi ho paya."
            if "insufficient" in r or "funds" in r:
                return "account mein insufficient balance ki wajah se complete nahi ho paya."
            if "expired" in r:
                return "card expire hone ki wajah se process nahi ho paya."
            if "otp" in r or "authentication" in r:
                return "OTP authentication issue ki wajah se complete nahi ho paya."
            if "mandate" in r or "nach" in r:
                return "mandate authorization decline hone ki wajah se process nahi ho paya."
            if "dropout" in r or "dropped" in r or "checkout" in r:
                return "checkout process mein interrupt aane ki wajah se complete nahi ho paya."
            if "netbanking" in r or "net banking" in r:
                return "netbanking server issue ki wajah se complete nahi ho paya."
            return f"ek technical issue ({failure_reason}) ki wajah se complete nahi ho paya."
        else:
            if "timeout" in r or "gateway" in r:
                return "could not be completed due to a bank gateway timeout."
            if "insufficient" in r or "funds" in r:
                return "could not be processed due to insufficient funds."
            if "expired" in r:
                return "could not be processed as the card on file has expired."
            if "otp" in r or "authentication" in r:
                return "could not complete due to an OTP authentication failure."
            if "mandate" in r or "nach" in r:
                return "could not be processed as the mandate authorization was declined."
            if "dropout" in r or "dropped" in r or "checkout" in r:
                return "was left incomplete during the checkout process."
            if "netbanking" in r or "net banking" in r:
                return "could not complete due to a netbanking server timeout."
            return f"could not be completed due to a technical issue ({failure_reason})."

    def _explain_failure_reason(self, failure_reason: str, lang: str, amount: float) -> str:
        """Returns a clear, empathetic explanation of why the payment failed."""
        r = failure_reason.lower()
        if lang in ("hi", "hinglish"):
            if "timeout" in r or "gateway" in r:
                return (
                    f"Aapka payment bank gateway timeout ki wajah se fail hua. "
                    f"Iska matlab hai ki payment process ke dauraan bank server ne response dene mein "
                    f"der ki aur connection timeout ho gaya. Aapke account par koi permanent effect nahi pada."
                )
            if "insufficient" in r or "funds" in r:
                return (
                    f"Aapka payment insufficient balance ki wajah se fail hua. "
                    f"Transaction ke time available balance Rs. {amount:,.2f} se kam tha. "
                    f"Aap UPI ya credit card se try kar sakte hain agar bank balance kam ho."
                )
            if "expired" in r:
                return (
                    f"Aapka payment card expire hone ki wajah se fail hua. "
                    f"Jo card system par register tha uski expiry date guzar chuki hai. "
                    f"Aap ek naya card ya UPI use kar sakte hain."
                )
            if "otp" in r or "authentication" in r:
                return (
                    f"Aapka payment OTP authentication fail hone ki wajah se incomplete raha. "
                    f"Transaction ke liye required OTP ya toh galat tha ya time expire ho gaya. "
                    f"Next time OTP aane ke 30 seconds ke andar enter karein."
                )
            if "mandate" in r or "nach" in r:
                return (
                    f"Aapka auto-debit mandate (NACH) bank ne approve nahi kiya. "
                    f"Iska matlab hai ki automatic deduction permission nahi mili. "
                    f"Aapko ek baar manually payment karni hogi."
                )
            if "dropout" in r or "dropped" in r or "checkout" in r:
                return (
                    f"Lagta hai aap payment page se exit kar gaye the ya internet connection toot gaya tha "
                    f"payment complete hone se pehle. Yeh bahut common hai aur easily fix hota hai."
                )
            return (
                f"Aapka payment '{failure_reason}' ki wajah se fail hua. "
                f"Yeh ek temporary technical issue tha aur aapka koi permanent loss nahi hua."
            )
        else:
            if "timeout" in r or "gateway" in r:
                return (
                    f"Your payment failed due to a bank gateway timeout. "
                    f"This means the bank's server took too long to respond during the payment process "
                    f"and the connection timed out. There is no permanent impact on your account."
                )
            if "insufficient" in r or "funds" in r:
                return (
                    f"Your payment failed due to insufficient funds. "
                    f"The available balance was below Rs. {amount:,.2f} at the time of the transaction. "
                    f"You could try using a different UPI account or credit card."
                )
            if "expired" in r:
                return (
                    f"Your payment failed because the card on file has expired. "
                    f"The card's expiry date has passed. You can use a new card or switch to UPI."
                )
            if "otp" in r or "authentication" in r:
                return (
                    f"Your payment failed because the OTP authentication was unsuccessful. "
                    f"The OTP was either incorrect or it expired before being entered. "
                    f"Please enter the OTP within 30 seconds next time."
                )
            if "mandate" in r or "nach" in r:
                return (
                    f"Your auto-debit mandate (NACH) was not approved by your bank. "
                    f"This means automatic deduction permission was declined. "
                    f"You'll need to make a one-time manual payment."
                )
            if "dropout" in r or "dropped" in r or "checkout" in r:
                return (
                    f"It appears you left the payment page before it completed, "
                    f"possibly due to a connection drop or navigating away. "
                    f"This is very common and easy to resolve."
                )
            return (
                f"Your payment failed due to '{failure_reason}'. "
                f"This was a temporary technical issue with no permanent impact on your account."
            )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _hit(self, text: str, keywords: list) -> bool:
        """Returns True if any keyword is found as a substring in text (case-insensitive)."""
        return any(kw in text for kw in keywords)

    def _extract_schedule_time(self, speech: str) -> str:
        """Parses a callback time from free-form speech."""
        if self._hit(speech, ["tomorrow", "kal subah", "kal morning"]):
            return "tomorrow morning at 11:00 AM"
        if self._hit(speech, ["evening", "shaam", "6 baje", "after 5", "after 6"]):
            return "this evening at 6:00 PM"
        if self._hit(speech, ["1 hour", "ek ghante", "ghante baad", "1 ghanta"]):
            return "in 1 hour"
        if self._hit(speech, ["after meeting", "meeting ke baad", "office ke baad"]):
            return "after your meeting today"
        if self._hit(speech, ["night", "raat", "9 baje", "9 pm"]):
            return "tonight at 9:00 PM"
        if self._hit(speech, ["driving", "drive", "home", "ghar"]):
            return "when you reach home"
        if self._hit(speech, ["kal", "tomorrow"]):
            return "tomorrow at 11:00 AM"
        return "tomorrow at 11:00 AM"

    def _detect_language(self, text: str, current_pref: str) -> str:
        """Detects whether text is predominantly English, Hindi, or Hinglish."""
        text_lower = text.lower()
        hindi_keywords = [
            "namaste", "haan", "nahi", "kya", "bhai", "ji", "paise", "kat", "gaye", "bhej",
            "karo", "baad", "mein", "kal", "samajh", "shukriya", "achha", "theek", "hai",
            "karna", "ho", "gaya", "chahiye", "karein", "aap", "main", "toh", "yeh",
            "woh", "bata", "milega", "kaise", "kyun", "kab", "kahan", "nahi", "bilkul",
            "zaroor", "matlab", "lekin", "aur", "se", "ke", "ka", "ki", "par", "pe"
        ]
        matches = sum(1 for kw in hindi_keywords if re.search(r"\b" + kw + r"\b", text_lower))
        if matches >= 2:
            return "hinglish"
        if matches == 1:
            return "hinglish" if current_pref in ("hinglish", "hi") else "en"
        return current_pref or "en"

    def _check_security_violations(self, text: str, lang: str) -> Optional[str]:
        """
        Enforces Section 2 Invariant: Zero Credential Collection.
        Fires immediately if user mentions or attempts to share OTP, CVV, PIN.
        """
        text_lower = text.lower()
        patterns = [
            r"\botp\b", r"\bcvv\b", r"\bcvc\b", r"\bupi\s*pin\b", r"\batm\s*pin\b",
            r"\bpassword\b", r"\bpasscode\b", r"\bpin\s+\d{4,6}\b", r"\b\d{4,6}\s+(?:is|hai|otp)\b"
        ]
        if any(re.search(p, text_lower) for p in patterns):
            if lang in ("hi", "hinglish"):
                return (
                    "⚠️ Rukiye! Yeh bahut zaroori baat hai — "
                    "Razorpay ya koi bhi legitimate company aapse kabhi OTP, CVV, ya UPI PIN nahi maangti. "
                    "Agar koi maange toh woh fraud hai. "
                    "Hum sirf aapko ek secure payment link bhejte hain — "
                    "aap khud apne device par safely pay karte hain. "
                    "Kya main abhi ek secure link bhejun?"
                )
            else:
                return (
                    "⚠️ Please stop right there! This is critical — "
                    "Razorpay or any legitimate company will NEVER ask for your OTP, CVV, or UPI PIN. "
                    "Anyone who does is attempting fraud. "
                    "We only send you a secure payment link where you pay safely on your own device. "
                    "Shall I send you a secure payment link right now?"
                )
        return None

    def _generate_conversational_reply(self, session: VoiceSession, user_text: str, lang: str) -> str:
        """Generates contextual reply using Gemini with full conversation history, or a smart fallback."""
        if self.api_key and self.provider != "mock":
            try:
                url = (
                    f"https://generativelanguage.googleapis.com/v1beta/models/"
                    f"{self.model}:generateContent?key={self.api_key}"
                )
                # Build last 8 turns of conversation history
                history_text = "\n".join([
                    f"{t.role.upper()}: {t.content}"
                    for t in session.turns[-8:]
                    if t.role in ("user", "assistant")
                ])
                system_prompt = (
                    f"You are the Razorpay Autonomous AI Voice Recovery Agent. "
                    f"Customer: {session.customer_name}. "
                    f"Failed payment: Rs. {session.amount:,.2f}. "
                    f"Failure reason: {session.failure_reason}. "
                    f"Session status: {session.status}. "
                    f"Payment link already sent: {session.payment_link_sent}. "
                    f"Dispute filed: {session.dispute_filed}. "
                    f"Language: {lang} — respond in {lang}. "
                    f"Keep response conversational, empathetic, 2–3 sentences max. "
                    f"NEVER ask for OTP, CVV, or UPI PIN. "
                    f"Guide towards payment resolution or appropriate tool action."
                )
                payload = {
                    "contents": [{
                        "parts": [{
                            "text": (
                                f"{system_prompt}\n\n"
                                f"Conversation so far:\n{history_text}\n\n"
                                f"Customer: {user_text}\nAgent:"
                            )
                        }]
                    }],
                    "generationConfig": {"temperature": 0.3, "maxOutputTokens": 150},
                }
                with httpx.Client(timeout=5.0) as client:
                    resp = client.post(url, json=payload)
                    if resp.status_code == 200:
                        reply = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if reply:
                            return reply
            except Exception as e:
                logger.warning(f"Gemini LLM call failed, using fallback: {e}")

        # Smart deterministic fallback — context-aware
        if lang in ("hi", "hinglish"):
            if session.payment_link_sent:
                return (
                    f"Kya aapko payment link mila {session.customer_name} ji? "
                    f"Agar nahi mila toh main dobara bhej sakta hoon, "
                    f"ya kisi aur tarike se help karna chahta hoon."
                )
            if session.dispute_filed:
                return (
                    f"Aapka dispute under review hai {session.customer_name} ji. "
                    f"Bank reversal 3–5 working days mein ho jayega. "
                    f"Tab tak kya main fresh payment link bhejun taaki order delay na ho?"
                )
            return (
                f"Ji {session.customer_name} ji, main aapki poori madad karne ke liye hoon. "
                f"Kya main aapke WhatsApp par Rs. {session.amount:,.2f} ka instant payment link bhejun?"
            )
        else:
            if session.payment_link_sent:
                return (
                    f"Did you receive the payment link, {session.customer_name}? "
                    f"If not, I can resend it or assist you another way."
                )
            if session.dispute_filed:
                return (
                    f"Your dispute is under review, {session.customer_name}. "
                    f"The bank reversal will happen in 3–5 working days. "
                    f"Would you like a fresh payment link in the meantime?"
                )
            return (
                f"I'm here to help you, {session.customer_name}. "
                f"Shall I send a secure payment link for Rs. {session.amount:,.2f} "
                f"to your WhatsApp or SMS right now?"
            )


# Global Voice Recovery Agent instance
voice_recovery_agent = VoiceRecoveryAgent()
