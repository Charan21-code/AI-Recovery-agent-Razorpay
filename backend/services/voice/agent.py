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
    link_resend_count: int = 0
    max_link_resends: int = 2
    status_checked: bool = False
    dispute_filed: bool = False
    refund_requested: bool = False
    # ── Conversational dialog context ─────────────────────────────────────────
    identity_confirmed: bool = False
    link_delivery_confirmed: bool = False
    payment_in_progress: bool = False
    last_agent_prompt_type: Optional[str] = "greeting_identity"
    consecutive_fallback_count: int = 0
    last_assistant_reply: Optional[str] = None


class VoiceRecoveryAgent:
    """
    Autonomous AI Voice Recovery Agent.
    Priority-ordered intent detection (14 intents), strict security invariants,
    dynamic failure-reason-aware greeting, direct Gemini LLM generation, and multilingual/Devanagari NLP.
    """

    def __init__(self):
        self._sessions: Dict[str, VoiceSession] = {}
        self.api_key = settings.LLM_API_KEY or os.environ.get("GEMINI_API_KEY")
        self.model = settings.LLM_MODEL or "gemini-flash-lite-latest"
        self.provider = settings.LLM_PROVIDER
        self._http_client = httpx.Client(
            timeout=4.5,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=60.0),
        )

    def _get_model_name(self) -> str:
        """Dynamically retrieves configured model, prioritizing low-latency flash-lite."""
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        env_path = os.path.join(root_dir, ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("LLM_MODEL="):
                            val = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if val:
                                return val
            except Exception:
                pass
        return os.environ.get("LLM_MODEL") or getattr(settings, "LLM_MODEL", None) or "gemini-flash-lite-latest"

    def _get_api_key(self) -> Optional[str]:
        """Dynamically retrieves the LLM API key from env vars, settings, or .env on disk."""
        key = os.environ.get("LLM_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if key and key.strip():
            return key.strip()

        if settings.LLM_API_KEY and settings.LLM_API_KEY.strip():
            return settings.LLM_API_KEY.strip()

        # Check .env directly in workspace root
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        env_path = os.path.join(root_dir, ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("LLM_API_KEY=") or line.startswith("GEMINI_API_KEY="):
                            parts = line.split("=", 1)
                            if len(parts) == 2 and parts[1].strip():
                                val = parts[1].strip().strip('"').strip("'")
                                if val:
                                    return val
            except Exception as e:
                logger.warning(f"Could not read .env: {e}")
        return None

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
            last_agent_prompt_type="greeting_identity",
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

        # ── Guard: only stop if customer explicitly opted out / refused ──────
        if session.status == "refused":
            lang = session.language_preference
            if lang in ("hi", "hinglish"):
                msg = (
                    f"Dhanyawad {session.customer_name} ji! "
                    f"Aapke anurodh par humne call close kar di hai. "
                    f"Aur madad ke liye 1800-XXX-XXXX par call karein."
                )
            else:
                msg = (
                    f"Thank you, {session.customer_name}. "
                    f"As requested, this conversation is closed. "
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
            session.consecutive_fallback_count = 0
            session.last_agent_prompt_type = "link_offered"
            session.last_assistant_reply = security_intervention
            agent_turn = VoiceTurn(role="assistant", content=security_intervention, language=detected_lang)
            session.turns.append(agent_turn)
            return agent_turn

        # ══ PRIORITY 2: Wrong Number ══════════════════════════════════════════
        if self._hit(speech_lower, [
            "wrong number", "galat number", "wrong person", "galat aadmi",
            "i am not", "main nahi hoon", "yeh number galat", "who are you calling",
            "not the right person", "aap galat jagah", "i don't know about this payment",
            "koi aur hoga", "mujhe nahi pata razorpay",
            "गलत नंबर", "गलत व्यक्ति", "गलत आदमी", "मैं नहीं हूँ", "मुझे नहीं पता"
        ]) and not self._hit(speech_lower, ["link", "payment", "paise", "retry", "help", "लिंक"]):
            session.status = "completed"
            session.recorded_intent = "WRONG_NUMBER"
            session.consecutive_fallback_count = 0
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
            session.last_assistant_reply = assistant_reply
            agent_turn = VoiceTurn(role="assistant", content=assistant_reply, language=detected_lang)
            session.turns.append(agent_turn)
            return agent_turn

        # ══ PRIORITY 3: Hard Refusal / Opt-Out ════════════════════════════════
        if self._hit(speech_lower, [
            "not interested", "nahi chahiye", "mujhe nahi chahiye", "don't call me",
            "mat karo call", "stop calling", "remove my number", "mera number hata",
            "do not disturb", "dnd", "leave me alone", "go away", "don't want",
            "no thank", "band karo", "mere peeche se hato", "harass", "spam",
            "नहीं चाहिए", "कॉल मत करो", "फोन मत करो", "नंबर हटाओ", "डिस्टर्ब मत करो", "बंद करो"
        ]) and not self._hit(speech_lower, [
            "link", "payment link", "whatsapp", "retry", "schedule callback", "लिंक"
        ]):
            session.status = "refused"
            session.recorded_intent = "REFUSAL"
            session.consecutive_fallback_count = 0
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
            session.last_assistant_reply = assistant_reply
            agent_turn = VoiceTurn(role="assistant", content=assistant_reply, language=detected_lang)
            session.turns.append(agent_turn)
            return agent_turn

        # ══ LIVE GEMINI GENERATIVE REASONER ══════════════════════════════════
        # If API key is present and not mock, send speech directly to Gemini
        # for dynamic, real, human-like voice recovery dialogue and tool calling.
        api_key = self._get_api_key()
        if api_key and self.provider != "mock":
            gemini_turn = self._process_with_gemini(session, user_speech, detected_lang, api_key)
            if gemini_turn:
                return gemini_turn

        # ══ MULTILINGUAL INTENT ROUTING (OFFLINE / FALLBACK DETERMINISTIC) ════
        # ══ PRIORITY 4: Claimed Already Paid via a Different Method ═══════════
        if self._hit(speech_lower, [
            "already paid", "paid already", "already done", "dusre se pay", "different method",
            "by card paid", "net banking se diya", "by gpay", "by phonepe", "ne pay kar diya",
            "done kar diya", "completed already", "pay kar chuka hoon", "pehle se pay kar diya",
            "maine pay kar diya",
            "पे कर दिया", "भुगतान कर दिया", "पेमेंट हो गया", "पैसे दे दिए", "पेमेंट कर दिया", "पहले ही पे कर दिया"
        ]) and not self._hit(speech_lower, [
            "paise kat", "kat gaye", "debit ho gaye", "bank se kat", "cut ho gaya", "pay kar raha",
            "पैसे कट", "कट गए", "कट गया"
        ]):
            status_res = voice_recovery_tools.get_payment_status(session.payment_id)
            tool_records.append(ToolCallRecord(
                tool_name="get_payment_status",
                arguments={"payment_id": session.payment_id},
                result=status_res,
            ))
            session.status_checked = True
            session.consecutive_fallback_count = 0

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
                session.recorded_intent = "CLAIMED_PAID_NOT_CONFIRMED"
                session.last_agent_prompt_type = "link_offered"
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
        elif self._hit(speech_lower, [
            "paise kat gaye", "paise kat gaya", "money deducted", "bank se kat gaya",
            "account se kat gaya", "debit ho gaya", "debit ho gaye", "cut from bank",
            "cut ho gaya", "already deducted", "balance kat gaya", "paisa gaya",
            "mere paise gaye", "kat liye", "paise chale gaye", "transaction hua",
            "money cut", "money gone", "bank ne le liya", "bank cut money",
            "पैसे कट गए", "पैसे कट गया", "पैसे कट", "अकाउंट से कट", "बैंक से कट", "खाते से कट",
            "डेबिट हो गया", "डेबिट हो गए", "कट गया", "कट गए", "पैसे चले गए"
        ]):
            status_res = voice_recovery_tools.get_payment_status(session.payment_id)
            tool_records.append(ToolCallRecord(
                tool_name="get_payment_status",
                arguments={"payment_id": session.payment_id},
                result=status_res,
            ))
            session.status_checked = True
            session.consecutive_fallback_count = 0

            if status_res.get("captured"):
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
                session.last_agent_prompt_type = "dispute_choice"
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
            "give me back my money", "mujhe refund do",
            "रिफंड", "पैसे वापस", "पैसा वापस", "रिफंड चाहिए", "ऑर्डर कैंसिल", "वापस करो", "रिफंड दो"
        ]):
            session.consecutive_fallback_count = 0
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
            "explain karo", "kya issue tha",
            "कॉल क्यों किया", "फेल क्यों हुआ", "क्या हुआ", "क्यों कटा", "प्रॉब्लम क्या थी", "कारण बताओ", "रीज़न क्या है"
        ]):
            session.consecutive_fallback_count = 0
            reason_explanation = self._explain_failure_reason(
                session.failure_reason, detected_lang, session.amount
            )
            session.last_agent_prompt_type = "link_offered"
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
            "kuch toh milega", "waiver", "price kam karo", "negotiate",
            "डिस्काउंट", "छूट", "कम करो", "थोड़ा कम", "ऑफर", "कुछ कम करो"
        ]):
            session.consecutive_fallback_count = 0
            session.last_agent_prompt_type = "link_offered"
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

        # ══ PRIORITY 9: Payment Link Request (Explicit or Affirmative to offer) ═
        elif (
            self._hit(speech_lower, [
                "payment link", "send link", "link bhej", "link bhejdo", "bhej do", "whatsapp link",
                "pay now", "pay right now", "payment link do", "send payment link",
                "send me a payment link", "link on whatsapp", "link send karo", "mujhe link bhejo",
                "share link", "online pay karna hai", "link chahiye", "payment karna hai", "link bhejo",
                "bhejo link", "bhej do link",
                "लिंक भेजो", "लिंक भेज दो", "पेमेंट लिंक", "व्हाट्सएप पर भेजो", "पे करना है", "ऑनलाइन पे", "लिंक चाहिए", "भेज दो"
            ])
            or (
                session.last_agent_prompt_type in ("link_offered", "dispute_choice")
                and self._is_affirmative(speech_lower)
                and not self._is_negative(speech_lower)
            )
        ):
            session.consecutive_fallback_count = 0
            if session.payment_link_sent:
                if session.link_resend_count >= session.max_link_resends:
                    session.last_agent_prompt_type = "alternative_resolution"
                    if detected_lang in ("hi", "hinglish"):
                        assistant_reply = (
                            f"Maine already do baar payment link bhej diya hai {session.customer_phone} par {session.customer_name} ji. "
                            f"Network ya SMS delivery issue lag raha hai. "
                            f"Aap chahein toh direct humare official UPI ID par transfer kar sakte hain, "
                            f"ya main abhi support specialist se aapki call connect karwa doon?"
                        )
                    else:
                        assistant_reply = (
                            f"I have already resent the payment link twice to {session.customer_phone}, {session.customer_name}. "
                            f"There seems to be an SMS or telecom delivery delay. "
                            f"Would you like to pay directly via our official UPI ID, "
                            f"or should I connect you with a senior specialist right away?"
                        )
                else:
                    session.link_resend_count += 1
                    link_res = voice_recovery_tools.create_payment_link(
                        customer_id=session.customer_id,
                        amount=session.amount,
                        customer_name=session.customer_name,
                        customer_phone=session.customer_phone,
                    )
                    tool_records.append(ToolCallRecord(
                        tool_name="create_payment_link",
                        arguments={"customer_id": session.customer_id, "amount": session.amount, "resend": True},
                        result=link_res,
                    ))
                    session.last_agent_prompt_type = "link_delivered_check"
                    if detected_lang in ("hi", "hinglish"):
                        assistant_reply = (
                            f"Ji {session.customer_name} ji, maine ek fresh payment link dobara {session.customer_phone} par bhej diya hai. "
                            f"Kripya WhatsApp aur SMS check karein. Kya abhi receive hua?"
                        )
                    else:
                        assistant_reply = (
                            f"Certainly, {session.customer_name}! I've resent the payment link to {session.customer_phone}. "
                            f"Please check your WhatsApp and SMS inbox. Did you receive it?"
                        )
            else:
                session.link_resend_count = 1
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
                session.last_agent_prompt_type = "link_delivered_check"
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
                        f"Link sirf 24 ghante ke liye valid hai. Kya link deliver ho gaya?"
                    )
                else:
                    assistant_reply = (
                        f"Done, {session.customer_name}! "
                        f"I've sent a secure 1-click Razorpay payment link to {session.customer_phone} "
                        f"via WhatsApp and SMS. "
                        f"You can pay using UPI, card, or netbanking. The link is valid for 24 hours. "
                        f"Please let me know once you receive it!"
                    )

        # ══ PRIORITY 10: Follow-up on Link Delivery (Aagaya / Nahi aaya) ══════
        elif session.payment_link_sent and self._hit(speech_lower, [
            "aagaya", "aa gaya", "mil gaya", "got it", "received", "haan mila",
            "haan aaya", "haan ji mila", "dekh liya", "yes got it", "yes received",
            "link aaya", "link mila", "nahi aaya", "nahi mila", "not received",
            "still waiting", "no link", "haven't received", "did not get",
            "आ गया", "मिल गया", "नहीं आया", "नहीं मिला", "नहीं पहुंचा", "नहीं दिख रहा", "आया", "मिला"
        ]):
            session.consecutive_fallback_count = 0
            if self._hit(speech_lower, ["nahi", "not", "no link", "haven't", "still waiting", "नहीं आया", "नहीं मिला", "नहीं पहुंचा", "नहीं दिख रहा"]):
                if session.link_resend_count >= session.max_link_resends:
                    session.last_agent_prompt_type = "alternative_resolution"
                    if detected_lang in ("hi", "hinglish"):
                        assistant_reply = (
                            f"Main poori tarah samajh raha hoon {session.customer_name} ji, "
                            f"maine already do baar link bhej diya hai lekin network delivery delay ho rahi hai. "
                            f"Aap chahein toh direct humari official UPI ID par transfer kar sakte hain, "
                            f"ya main abhi senior support specialist se call connect karwa doon?"
                        )
                    else:
                        assistant_reply = (
                            f"I understand, {session.customer_name}. I have already resent the link twice, "
                            f"but SMS delivery appears to be delayed by the telecom network. "
                            f"Would you prefer paying directly via our official UPI ID, "
                            f"or shall I connect you with a senior specialist right away?"
                        )
                else:
                    session.link_resend_count += 1
                    link_res = voice_recovery_tools.create_payment_link(
                        customer_id=session.customer_id,
                        amount=session.amount,
                        customer_name=session.customer_name,
                        customer_phone=session.customer_phone,
                    )
                    tool_records.append(ToolCallRecord(
                        tool_name="create_payment_link",
                        arguments={"customer_id": session.customer_id, "amount": session.amount, "resend": True},
                        result=link_res,
                    ))
                    session.last_agent_prompt_type = "link_delivered_check"
                    if detected_lang in ("hi", "hinglish"):
                        assistant_reply = (
                            f"Maafi chahta hoon {session.customer_name} ji! Maine abhi dobara fresh payment link bhej diya hai "
                            f"{session.customer_phone} par. "
                            f"Kripya WhatsApp aur normal message inbox check karein. Agar spam folder ho toh wahan bhi zaroor dekhein."
                        )
                    else:
                        assistant_reply = (
                            f"Apologies for the delay, {session.customer_name}! I have just resent the payment link to "
                            f"{session.customer_phone}. "
                            f"Please check your WhatsApp and SMS inbox, as well as your spam folder."
                        )
            else:
                session.link_delivery_confirmed = True
                session.last_agent_prompt_type = "waiting_for_payment"
                if detected_lang in ("hi", "hinglish"):
                    assistant_reply = (
                        f"Bahut badhiya {session.customer_name} ji! "
                        f"Aap link open karke UPI, card, ya netbanking se payment complete kar sakte hain. "
                        f"Main line par wait kar raha hoon — payment hone ke baad mujhe bataiye!"
                    )
                else:
                    assistant_reply = (
                        f"Wonderful, {session.customer_name}! "
                        f"You can open the link to complete payment via UPI, card, or netbanking. "
                        f"I'm right here on the line — please let me know once done!"
                    )

        # ══ PRIORITY 11: Customer Claims Payment Just Completed ═══════════════
        elif self._hit(speech_lower, [
            "pay kar diya", "kar diya maine", "payment done", "ho gaya payment",
            "paid just now", "maine bhej diya", "ho gaya pay", "completed payment",
            "done paying", "pay ho gaya", "maine pay kar diya hai", "payment successful",
            "paid now",
            "पे कर दिया", "हो गया पेमेंट", "पेमेंट डन", "पैसे भेज दिए", "पेमेंट हो गई", "पे हो गया"
        ]):
            session.consecutive_fallback_count = 0
            status_res = voice_recovery_tools.get_payment_status(session.payment_id)
            tool_records.append(ToolCallRecord(
                tool_name="get_payment_status",
                arguments={"payment_id": session.payment_id},
                result=status_res,
            ))
            session.status_checked = True

            if status_res.get("captured"):
                session.status = "completed"
                session.recorded_intent = "PAYMENT_CAPTURED_CONFIRMED"
                voice_recovery_tools.record_customer_intent(
                    session.customer_id, session.payment_id, "PAYMENT_CAPTURED", "POSITIVE",
                    "Customer completed payment during voice session"
                )
                if detected_lang in ("hi", "hinglish"):
                    assistant_reply = (
                        f"Bilkul shandar {session.customer_name} ji! Maine gateway par live verify kar liya hai — "
                        f"aapka Rs. {session.amount:,.2f} ka payment successfully capture ho chuka hai! "
                        f"Aapka order securely confirm ho gaya hai. Bahut shukriya aur aapka din shubh ho!"
                    )
                else:
                    assistant_reply = (
                        f"Fantastic, {session.customer_name}! I have verified with our gateway — "
                        f"your payment of Rs. {session.amount:,.2f} has been successfully captured. "
                        f"Your order is now fully confirmed. Thank you so much and have a great day!"
                    )
            else:
                if detected_lang in ("hi", "hinglish"):
                    assistant_reply = (
                        f"Maine gateway par status check kiya {session.customer_name} ji — "
                        f"bank aur gateway ke beech transaction synchronization chal raha hai. "
                        f"Agar aapke bank se debit notification aa chuki hai, toh order automatically secure ho jayega. "
                        f"Aapko 2 minute ke andar official confirmation SMS mil jayega."
                    )
                else:
                    assistant_reply = (
                        f"I've checked our live gateway, {session.customer_name} — "
                        f"the transaction synchronization is currently in progress between your bank and Razorpay. "
                        f"If your account was debited, your order is secure and you will receive a confirmation SMS within 2 minutes."
                    )

        # ══ PRIORITY 12: In-Progress Payment / Hold On ════════════════════════
        elif self._hit(speech_lower, [
            "pay kar raha", "kar raha hoon", "paying now", "paying right now",
            "wait karo", "wait please", "ek minute", "ek min", "hold on",
            "just a minute", "rukiye", "ruko", "checking now", "doing it now",
            "line par raho", "line pe raho", "ek second", "wait a sec",
            "पे कर रहा हूँ", "कर रहा हूँ", "रुकिए", "रुको", "एक मिनट", "लाइन पर रहो", "एक सेकंड", "लाइन पे रहो"
        ]):
            session.consecutive_fallback_count = 0
            session.payment_in_progress = True
            session.last_agent_prompt_type = "waiting_for_payment"
            if detected_lang in ("hi", "hinglish"):
                assistant_reply = (
                    f"Bilkul {session.customer_name} ji, koi jaldi nahi hai! "
                    f"Aap aaram se payment complete kijiye, main call par hi available hoon. "
                    f"Jaise hi authorization ho jaye, mujhe bataiye main verify kar doonga."
                )
            else:
                assistant_reply = (
                    f"Take your time, {session.customer_name}! "
                    f"I'm right here holding on the line. "
                    f"Just let me know once you've authorized the payment, and I'll verify it immediately."
                )

        # ══ PRIORITY 13: Greeting Identity Confirmation (Customer says "Haan" / "Speaking") ═
        elif session.last_agent_prompt_type == "greeting_identity" and not self._hit(speech_lower, ["link", "payment", "paise", "amount", "refund", "retry", "nonsense", "wrong"]) and (
            self._is_affirmative(speech_lower)
            or any(re.search(r"\b" + re.escape(kw) + r"\b", speech_lower) for kw in [
                "speaking", "bol raha", "bol rahi", "main hoon", "main hi hoon", "this is", "myself", "bolo", "batao", "sun raha"
            ])
        ) and not self._is_negative(speech_lower) and not self._hit(speech_lower, ["still", "not speaking", "why are you"]):
            session.identity_confirmed = True
            session.last_agent_prompt_type = "link_offered"
            session.consecutive_fallback_count = 0
            reason_phrase = self._get_failure_intro(session.failure_reason, detected_lang)
            if detected_lang in ("hi", "hinglish"):
                assistant_reply = (
                    f"Shukriya confirm karne ke liye {session.customer_name} ji! "
                    f"Aapka Rs. {session.amount:,.2f} ka payment {reason_phrase} "
                    f"Main aapki quick assistance ke liye hoon. "
                    f"Kya main aapke WhatsApp par ek 1-click secure payment link bhej doon, "
                    f"ya aap UPI retry karna chahenge?"
                )
            else:
                assistant_reply = (
                    f"Thank you for confirming, {session.customer_name}! "
                    f"Your recent payment of Rs. {session.amount:,.2f} {reason_phrase} "
                    f"I'm here to assist you. "
                    f"Would you like me to send a secure 1-click payment link to your WhatsApp, "
                    f"or would you prefer a UPI retry?"
                )

        # ══ PRIORITY 14: Caller Identity Query ("Who are you?") ═══════════════
        elif self._hit(speech_lower, [
            "who are you", "who is this", "aap kaun", "kaun bol rahe", "kahan se call",
            "koun bol raha", "company kaunsi", "kya naam hai", "who is calling",
            "kisse baat ho rahi",
            "आप कौन हो", "कौन बोल रहे हो", "कहाँ से बोल रहे हो", "कौन हो", "आप कौन बोल रहे हैं"
        ]):
            session.consecutive_fallback_count = 0
            session.last_agent_prompt_type = "link_offered"
            if detected_lang in ("hi", "hinglish"):
                assistant_reply = (
                    f"Main Razorpay ka AI recovery specialist hoon {session.customer_name} ji, "
                    f"hamari merchant partner ki taraf se call kar raha hoon. "
                    f"Hum aapke recent Rs. {session.amount:,.2f} ke failed payment ko securely complete karne mein madad karte hain. "
                    f"Kya main aapke WhatsApp par ek 1-click payment link bhej doon?"
                )
            else:
                assistant_reply = (
                    f"I'm the Razorpay AI recovery specialist calling on behalf of our merchant partner, {session.customer_name}. "
                    f"I'm reaching out to help you safely resolve your recent incomplete transaction of Rs. {session.amount:,.2f}. "
                    f"Shall I dispatch a secure payment link to your WhatsApp?"
                )

        # ══ PRIORITY 15: Amount Inquiry ("How much is the amount?") ═══════════
        elif self._hit(speech_lower, [
            "kitna amount", "kitne paise", "how much", "what is the amount",
            "total amount", "kitna pay karna", "kitne ka payment", "amount kitna",
            "what amount", "balance kitna",
            "कितना अमाउंट", "कितने पैसे", "कितना रुपया", "कितना पे करना है", "अमाउंट कितना है"
        ]):
            session.consecutive_fallback_count = 0
            session.last_agent_prompt_type = "link_offered"
            if detected_lang in ("hi", "hinglish"):
                assistant_reply = (
                    f"Aapka pending transaction amount exact Rs. {session.amount:,.2f} hai {session.customer_name} ji. "
                    f"Kya main is transaction ka secure payment link aapke WhatsApp par bhej doon?"
                )
            else:
                assistant_reply = (
                    f"Your pending transaction amount is exactly Rs. {session.amount:,.2f}, {session.customer_name}. "
                    f"Shall I send you a secure payment link for this amount via WhatsApp?"
                )

        # ══ PRIORITY 16: Order / Details Inquiry ("Which order was this for?") 
        elif self._hit(speech_lower, [
            "kis cheez ka", "which order", "what order", "kis product", "kahan ka payment",
            "what is this for", "kis transaction", "order details", "kya khareeda",
            "kis website", "kaha ka payment",
            "किस चीज़ का", "कौन सा ऑर्डर", "किस वेबसाइट का", "किसका पेमेंट", "क्या खरीदा"
        ]):
            session.consecutive_fallback_count = 0
            session.last_agent_prompt_type = "link_offered"
            if detected_lang in ("hi", "hinglish"):
                assistant_reply = (
                    f"Yeh Rs. {session.amount:,.2f} ka payment hamare merchant partner ke checkout order ke liye tha "
                    f"{session.customer_name} ji (Payment ID: {session.payment_id}). "
                    f"Kya main aapke number {session.customer_phone} par ek secure payment link bhej doon?"
                )
            else:
                assistant_reply = (
                    f"This payment of Rs. {session.amount:,.2f} was for your checkout order with our merchant partner "
                    f"(Payment ID: {session.payment_id}), {session.customer_name}. "
                    f"Would you like me to send a secure payment link to your phone {session.customer_phone}?"
                )

        # ══ PRIORITY 17: Payment Methods Inquiry ("How can I pay?") ═══════════
        elif self._hit(speech_lower, [
            "kaise pay", "how to pay", "how can i pay", "kya payment method", "payment methods",
            "google pay chalega", "phonepe chalega", "credit card se", "debit card",
            "upi se ho jayega", "netbanking chalegi", "kaise karna hai",
            "कैसे पे करें", "पेमेंट कैसे करें", "गूगल पे चलेगा", "फोनपे चलेगा", "यूपीआई चलेगा"
        ]):
            session.consecutive_fallback_count = 0
            session.last_agent_prompt_type = "link_offered"
            if detected_lang in ("hi", "hinglish"):
                assistant_reply = (
                    f"Aap Google Pay, PhonePe, Paytm, kisi bhi UPI app, credit/debit card, ya netbanking se easily pay kar sakte hain "
                    f"{session.customer_name} ji. "
                    f"Kya main aapke registered number {session.customer_phone} par 1-click payment link bhej doon?"
                )
            else:
                assistant_reply = (
                    f"You can easily pay using Google Pay, PhonePe, Paytm, any UPI app, credit/debit cards, or netbanking, {session.customer_name}. "
                    f"Shall I dispatch a 1-click secure payment link to your phone {session.customer_phone}?"
                )


        # ══ PRIORITY 18: Retry Payment ════════════════════════════════════════
        elif self._hit(speech_lower, [
            "retry", "try again", "phir se try", "koshish karo", "dobara try",
            "please try", "attempt again", "re-initiate", "phir karo", "again karo",
            "फिर से ट्राई", "दोबारा कोशिश", "रीट्राई", "दोबारा करो", "फिर से करो"
        ]):
            session.consecutive_fallback_count = 0
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
                session.last_agent_prompt_type = "waiting_for_payment"
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

        # ══ PRIORITY 19: Schedule Callback ════════════════════════════════════
        elif self._hit(speech_lower, [
            "busy", "call later", "kal call", "baad mein call", "later call",
            "evening mein", "tomorrow call", "drive kar raha", "driving", "meeting mein",
            "in a meeting", "not now", "abhi nahi", "ghar pahunch ke", "after some time",
            "thodi der mein", "give me time", "time de do", "remind me later",
            "call back",
            "बाद में कॉल करो", "कल फोन करो", "शाम को कॉल", "अभी बिजी हूँ", "मीटिंग में हूँ", "गाड़ी चला रहा हूँ", "बाद में बात"
        ]):
            session.consecutive_fallback_count = 0
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

        # ══ PRIORITY 20: Human Escalation ═════════════════════════════════════
        elif self._hit(speech_lower, [
            "human", "manager", "senior", "supervisor", "real person", "agent se baat",
            "support agent", "fraud", "scam", "cheating", "lodge complaint",
            "consumer court", "police", "legal action", "gussa hai", "complaint karna hai",
            "dispute raise", "escalate", "help nahi hua", "fed up", "disgusted",
            "इंसान से बात कराओ", "मैनेजर से बात कराओ", "सीनियर से बात", "कंज्यूमर कोर्ट", "शिकायत दर्ज", "गुस्सा", "पुलिस"
        ]):
            session.consecutive_fallback_count = 0
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

        # ══ PRIORITY 21: Polite Gratitude / Closing ═══════════════════════════
        elif self._hit(speech_lower, [
            "thank you", "thanks", "shukriya", "dhanyawad", "bye", "okay thanks",
            "theek hai thanks", "alvida", "goodbye", "have a good day", "all good",
            "sab theek hai", "aur kuch nahi",
            "धन्यवाद", "शुक्रिया", "ठीक है धन्यवाद", "बाय", "अलविदा"
        ]):
            session.consecutive_fallback_count = 0
            if detected_lang in ("hi", "hinglish"):
                assistant_reply = (
                    f"Aapka bahut bahut shukriya {session.customer_name} ji! "
                    f"Agar aage kisi bhi transaction mein sahayata chahiye toh batayein. "
                    f"Aapka din shubh ho aur Razorpay use karne ke liye dhanyawad!"
                )
            else:
                assistant_reply = (
                    f"You're very welcome, {session.customer_name}! "
                    f"Thank you for your time, and please let us know if you need any further assistance. "
                    f"Have a wonderful day ahead!"
                )

        # ══ PRIORITY 22: Contextual Dialog Engine & LLM Fallback ══════════════
        else:
            assistant_reply = self._generate_conversational_reply(session, user_speech, detected_lang)

        session.last_assistant_reply = assistant_reply
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

    def _is_affirmative(self, text: str) -> bool:
        """Returns True if the text indicates affirmative agreement or confirmation."""
        cleaned = re.sub(r"\bright\s+now\b", "", text)
        affirmations = [
            "haan", "yes", "sure", "theek hai", "theek", "ok", "okay", "bhejo", "bhej do",
            "send it", "kar do", "karo", "ji haan", "haanji", "ha", "bilkul",
            "sahi hai", "sahi", "yeah", "yup", "correct", "please do", "done", "alright", "proceed",
            "accha", "achha", "zaroor", "karo bhej", "send please", "pls send", "plz send",
            "हाँ", "हां", "जी हाँ", "जी हां", "हाँजी", "हांजी", "ठीक है", "ठीक", "भेज दो", "भेजो", "बिल्कुल", "सही है", "ज़रूर", "जरूर"
        ]
        return any(re.search(r"\b" + re.escape(kw) + r"\b", cleaned) for kw in affirmations) or self._hit(text, ["bhej do", "theek hai", "ji haan", "भेज दो", "ठीक है", "हाँ", "हां", "भेजो"])

    def _is_negative(self, text: str) -> bool:
        """Returns True if the text indicates negation."""
        negations = [
            "nahi", "no", "nahi chahiye", "don't", "dont", "not now", "mat karo", "mat bhejo",
            "nope", "never", "cancel", "stop", "na",
            "नहीं", "ना", "मत", "नहीं चाहिए", "मत करो", "मत भेजो"
        ]
        return any(re.search(r"\b" + re.escape(kw) + r"\b", text) for kw in negations) or self._hit(text, ["नहीं", "नहीं चाहिए", "मत करो"])

    def _extract_schedule_time(self, speech: str) -> str:
        """Parses a callback time from free-form speech."""
        if self._hit(speech, ["tomorrow", "kal subah", "kal morning", "कल सुबह"]):
            return "tomorrow morning at 11:00 AM"
        if self._hit(speech, ["evening", "shaam", "6 baje", "after 5", "after 6", "शाम"]):
            return "this evening at 6:00 PM"
        if self._hit(speech, ["1 hour", "ek ghante", "ghante baad", "1 ghanta", "एक घंटे"]):
            return "in 1 hour"
        if self._hit(speech, ["after meeting", "meeting ke baad", "office ke baad", "मीटिंग"]):
            return "after your meeting today"
        if self._hit(speech, ["night", "raat", "9 baje", "9 pm", "रात"]):
            return "tonight at 9:00 PM"
        if self._hit(speech, ["driving", "drive", "home", "ghar", "घर"]):
            return "when you reach home"
        if self._hit(speech, ["kal", "tomorrow", "कल"]):
            return "tomorrow at 11:00 AM"
        return "tomorrow at 11:00 AM"

    def _detect_language(self, text: str, current_pref: str) -> str:
        """Detects whether text is predominantly English, Hindi, or Hinglish."""
        # Devanagari Unicode detection
        if re.search(r"[\u0900-\u097F]", text):
            return "hinglish" if current_pref in ("hinglish", "hi") else "hi"

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
            r"\bpassword\b", r"\bpasscode\b", r"\bpin\s+\d{4,6}\b", r"\b\d{4,6}\s+(?:is|hai|otp)\b",
            r"ओटीपी", r"सीवीवी", r"पिन\s*\d{4,6}", r"पासवर्ड"
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

    def _process_with_gemini(
        self,
        session: VoiceSession,
        user_speech: str,
        detected_lang: str,
        api_key: str,
    ) -> Optional[VoiceTurn]:
        """
        Direct generative AI reasoner using Google Gemini.
        Natively handles multilingual input (Devanagari/Latin/English), reasons contextually,
        executes recovery actions, and outputs dynamic, empathetic spoken responses.
        """
        speech_lower = user_speech.lower()
        pre_status = None
        if self._hit(speech_lower, ["paise kat", "kat gaye", "कट गए", "कट गया", "debit", "already paid", "pay kar diya", "पे कर दिया", "paisa gaya"]):
            pre_status = voice_recovery_tools.get_payment_status(session.payment_id)
            session.status_checked = True

        history_text = "\n".join([
            f"{t.role.upper()}: {t.content}"
            for t in session.turns[-8:]
            if t.role in ("user", "assistant")
        ])

        status_context = (
            f"Gateway check for {session.payment_id}: captured={pre_status.get('captured')}, status={pre_status.get('status')}"
            if pre_status else "No gateway check required yet."
        )

        system_instruction = (
            f"You are the Razorpay Autonomous AI Voice Recovery Specialist on an active live telephone call with customer {session.customer_name}.\n"
            f"Live Call Context:\n"
            f"- Customer Name: {session.customer_name}\n"
            f"- Customer Phone: {session.customer_phone}\n"
            f"- Incomplete Transaction: Rs. {session.amount:,.2f} {session.currency}\n"
            f"- Payment ID: {session.payment_id}\n"
            f"- Original Failure Reason: {session.failure_reason}\n"
            f"- Payment Link Sent: {session.payment_link_sent} (Resend Count: {session.link_resend_count}/{session.max_link_resends})\n"
            f"- Link Delivery Confirmed: {session.link_delivery_confirmed}\n"
            f"- Dispute Filed: {session.dispute_filed}\n"
            f"- Current Status: {session.status}\n"
            f"- Live Gateway Check: {status_context}\n\n"
            f"OPERATIONAL VOICE GUIDELINES:\n"
            f"1. Spoken Phone Style: You are on a real telephone call. Be empathetic, polite, and concise (1–3 sentences max). Never sound like a robot. Never output markdown bullet points or formal letters.\n"
            f"2. Language: Respond in {detected_lang} (natural conversational Hinglish, Hindi, or English matching the customer's speech). You natively understand both Devanagari script (e.g. पैसे कट गए, लिंक भेज दो, हाँ, नहीं आया) and Romanized Hinglish.\n"
            f"3. ZERO CREDENTIAL COLLECTION: NEVER ask for or accept OTP, CVV, or UPI PIN. If customer mentions them, politely warn that Razorpay never asks for credentials.\n"
            f"4. ACTIONS: If an operational action must be executed, output an action tag on the FIRST LINE of your response in this exact format:\n"
            f"   ACTION: <action_name>\n"
            f"   Valid actions:\n"
            f"   - ACTION: create_payment_link (when customer agrees to pay, asks for a link, or asks to resend)\n"
            f"   - ACTION: get_payment_status (when customer claims money was deducted or already paid)\n"
            f"   - ACTION: file_dispute_complaint (when customer reports money debited from bank)\n"
            f"   - ACTION: escalate_to_human (when customer insists on human/manager or is extremely angry)\n"
            f"   - ACTION: schedule_recovery (when customer asks to call later, driving, in meeting)\n"
            f"   - ACTION: send_refund_request (when customer asks for refund or wants to cancel order)\n"
            f"   - ACTION: retry_payment (when customer requests UPI retry)\n"
            f"   If NO tool action is needed (e.g. answering amount, explaining failure reason, greeting, conversational chatter), do NOT output an ACTION line.\n"
            f"5. RESEND LINK DISCIPLINE:\n"
            f"   - If link was sent and customer says they did not receive it, you may trigger ACTION: create_payment_link ONLY if Resend Count < {session.max_link_resends}.\n"
            f"   - If Resend Count >= {session.max_link_resends}, DO NOT OFFER TO RESEND! Instead, offer to pay via direct UPI ID or connect with a specialist.\n"
            f"   - If customer is talking about other topics (amount, failure reason, bank deduction), ANSWER THEIR TOPIC DIRECTLY. Do NOT repeatedly ask about the link!\n"
            f"6. DEDUCTION CLAIMS: If customer reports money debited: reassure them that if money debited, bank will auto-reverse in 3-5 days. Trigger ACTION: file_dispute_complaint so we track it.\n"
        )

        payload = {
            "contents": [{
                "parts": [{
                    "text": (
                        f"{system_instruction}\n\n"
                        f"Conversation Transcript So Far:\n{history_text}\n\n"
                        f"Customer: {user_speech}\nAgent:"
                    )
                }]
            }],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 250},
        }

        # Try models in order: configured model, then ultra-fast flash-lite models for telephony
        configured = self._get_model_name()
        models_to_try = [configured, "gemini-flash-lite-latest", "gemini-flash-latest", "gemini-3-flash-preview", "gemini-3.7-flash"]
        seen = set()
        deduped_models = [m for m in models_to_try if m and not (m in seen or seen.add(m))]

        client = getattr(self, "_http_client", None)
        if client is None or getattr(client, "is_closed", False):
            client = httpx.Client(timeout=4.5, limits=httpx.Limits(max_keepalive_connections=10, max_connections=20, keepalive_expiry=60.0))
            self._http_client = client

        for m in deduped_models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
            try:
                resp = client.post(url, json=payload, timeout=4.0)
                if resp.status_code == 200:
                    candidates = resp.json().get("candidates", [])
                    if candidates and "content" in candidates[0]:
                        parts = candidates[0]["content"].get("parts", [])
                        if parts and "text" in parts[0]:
                            raw_text = parts[0]["text"].strip()
                            return self._execute_gemini_response(session, raw_text, detected_lang, pre_status)
                elif resp.status_code in (404, 503, 429):
                    logger.warning(f"Gemini model {m} returned {resp.status_code}, trying fallback model...")
                    continue
                else:
                    logger.warning(f"Gemini API error ({resp.status_code}): {resp.text[:200]}")
                    continue
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                logger.warning(f"Gemini fast timeout on {m}: {e}, switching to next model...")
                continue
            except Exception as e:
                logger.warning(f"Gemini call exception on {m}: {e}")
                continue

        return None

    def _execute_gemini_response(
        self,
        session: VoiceSession,
        raw_text: str,
        detected_lang: str,
        pre_status: Optional[Dict[str, Any]] = None,
    ) -> VoiceTurn:
        lines = raw_text.split("\n")
        tool_records: List[ToolCallRecord] = []
        speech_lines = []

        if pre_status:
            tool_records.append(ToolCallRecord(
                tool_name="get_payment_status",
                arguments={"payment_id": session.payment_id},
                result=pre_status,
            ))
            session.status_checked = True

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("ACTION:"):
                action_part = stripped.replace("ACTION:", "").strip().lower()
                if "create_payment_link" in action_part:
                    if session.link_resend_count < session.max_link_resends:
                        session.link_resend_count += 1
                        link_res = voice_recovery_tools.create_payment_link(
                            customer_id=session.customer_id,
                            amount=session.amount,
                            customer_name=session.customer_name,
                            customer_phone=session.customer_phone,
                        )
                        tool_records.append(ToolCallRecord(
                            tool_name="create_payment_link",
                            arguments={"amount": session.amount, "phone": session.customer_phone},
                            result=link_res,
                        ))
                        session.payment_link_sent = True
                        session.recorded_intent = "PROMISE_TO_PAY"
                elif "get_payment_status" in action_part:
                    res = pre_status or voice_recovery_tools.get_payment_status(session.payment_id)
                    tool_records.append(ToolCallRecord(
                        tool_name="get_payment_status",
                        arguments={"payment_id": session.payment_id},
                        result=res,
                    ))
                    session.status_checked = True
                    if res.get("captured"):
                        session.status = "completed"
                        session.recorded_intent = "PAYMENT_CAPTURED_CONFIRMED"
                elif "file_dispute_complaint" in action_part:
                    if not session.dispute_filed:
                        res = voice_recovery_tools.file_dispute_complaint(
                            customer_id=session.customer_id,
                            payment_id=session.payment_id,
                            claim_amount=session.amount,
                            description=f"Customer reported deduction: {session.customer_name}",
                        )
                        tool_records.append(ToolCallRecord(
                            tool_name="file_dispute_complaint",
                            arguments={"claim_amount": session.amount},
                            result=res,
                        ))
                        session.dispute_filed = True
                        session.status = "disputed"
                        session.recorded_intent = "DISPUTE_DEBITED"
                elif "escalate_to_human" in action_part:
                    res = voice_recovery_tools.escalate_to_human(
                        customer_id=session.customer_id,
                        reason="Customer requested human specialist",
                        priority="HIGH",
                    )
                    tool_records.append(ToolCallRecord(
                        tool_name="escalate_to_human",
                        arguments={"priority": "HIGH"},
                        result=res,
                    ))
                    session.status = "escalated"
                    session.recorded_intent = "ESCALATED"
                elif "schedule_recovery" in action_part:
                    res = voice_recovery_tools.schedule_recovery(
                        customer_id=session.customer_id,
                        payment_id=session.payment_id,
                        channel="voice",
                        scheduled_time_iso="tomorrow at 11:00 AM",
                    )
                    tool_records.append(ToolCallRecord(
                        tool_name="schedule_recovery",
                        arguments={"channel": "voice"},
                        result=res,
                    ))
                    session.status = "scheduled"
                    session.recorded_intent = "SCHEDULED_CALLBACK"
                elif "send_refund_request" in action_part:
                    if not session.refund_requested:
                        res = voice_recovery_tools.send_refund_request(
                            payment_id=session.payment_id,
                            customer_id=session.customer_id,
                            reason="Customer requested refund",
                            amount=session.amount,
                        )
                        tool_records.append(ToolCallRecord(
                            tool_name="send_refund_request",
                            arguments={"amount": session.amount},
                            result=res,
                        ))
                        session.refund_requested = True
                        session.recorded_intent = "REFUND_REQUESTED"
                elif "retry_payment" in action_part:
                    res = voice_recovery_tools.retry_payment(session.payment_id, preferred_method="upi")
                    tool_records.append(ToolCallRecord(
                        tool_name="retry_payment",
                        arguments={"preferred_method": "upi"},
                        result=res,
                    ))
            else:
                speech_lines.append(line)

        speech_text = "\n".join(speech_lines).strip()
        if not speech_text:
            speech_text = "Main aapki poori sahayata kar raha hoon, kya aapko koi aur jankari chahiye?"

        session.last_assistant_reply = speech_text
        session.consecutive_fallback_count = 0
        turn = VoiceTurn(
            role="assistant",
            content=speech_text,
            language=detected_lang,
            tool_calls=tool_records,
        )
        session.turns.append(turn)
        return turn

    def _generate_conversational_reply(self, session: VoiceSession, user_text: str, lang: str) -> str:
        """Generates contextual reply using Gemini with full conversation history, or a smart varied fallback."""
        api_key = self._get_api_key()
        if api_key and self.provider != "mock":
            gemini_turn = self._process_with_gemini(session, user_text, lang, api_key)
            if gemini_turn:
                return gemini_turn.content

        # Smart multi-variation, non-repetitive deterministic fallback
        return self._get_contextual_fallback(session, lang)

    def _get_contextual_fallback(self, session: VoiceSession, lang: str) -> str:
        """
        Returns a context-aware fallback response that NEVER repeats the exact
        same sentence consecutively, and offers escalation after repeated unrecognized inputs.
        """
        session.consecutive_fallback_count += 1
        count = session.consecutive_fallback_count

        if count >= 3:
            session.last_agent_prompt_type = "escalation_offered"
            if lang in ("hi", "hinglish"):
                return (
                    f"{session.customer_name} ji, lagta hai main aapki baat theek se samajh nahi pa raha hoon. "
                    f"Kya main aapki call turant hamare senior payment specialist ko transfer kar doon, "
                    f"ya kisi convenient time ke liye callback schedule kar doon?"
                )
            else:
                return (
                    f"I want to make sure I understand you properly, {session.customer_name}. "
                    f"Would you prefer I connect you directly with a senior payment specialist, "
                    f"or schedule a callback at a convenient time?"
                )

        if session.payment_in_progress:
            session.last_agent_prompt_type = "waiting_for_payment"
            options_hi = [
                f"Main line par hi hoon {session.customer_name} ji. Aap aaram se payment complete karein, koi jaldi nahi hai.",
                f"Take your time {session.customer_name} ji! Payment authorization hone ke baad mujhe bataiye, main yahan check kar loonga.",
                f"Call active hai {session.customer_name} ji. Aap app par confirm karein, main line par wait kar raha hoon.",
            ]
            options_en = [
                f"I'm holding on the line, {session.customer_name}. Please take your time to complete the transaction.",
                f"Still here on the call, {session.customer_name}. Let me know once your payment is authorized.",
                f"The line is active, {session.customer_name}. I'll verify the status as soon as you're done.",
            ]
        elif session.link_delivery_confirmed:
            session.last_agent_prompt_type = "waiting_for_payment"
            options_hi = [
                f"Aapne jo link receive kiya hai {session.customer_name} ji, us par click karke aap UPI, card ya netbanking se pay kar sakte hain. Kya koi issue aa raha hai?",
                f"Link ke zariye aap securely transaction complete kar sakte hain {session.customer_name} ji. Agar kisi aur method se try karna ho toh batayein.",
                f"Kya aapko payment link open karne ya pay karne mein koi dikkat aa rahi hai {session.customer_name} ji?",
            ]
            options_en = [
                f"You can use the link you received, {session.customer_name}, to pay via UPI, card, or netbanking. Is there anything holding you up?",
                f"The link is ready on your phone, {session.customer_name}. Would you like assistance with any payment step?",
                f"Let me know if you need any help while completing the payment through the link, {session.customer_name}.",
            ]
        elif session.payment_link_sent:
            if session.link_resend_count >= session.max_link_resends:
                session.last_agent_prompt_type = "alternative_resolution"
                options_hi = [
                    f"Maine do baar link bhej diya hai {session.customer_name} ji, lagta hai SMS ya WhatsApp delivery mein operator issue hai. Kya aap direct hamare verified UPI ID par pay karenge, ya senior specialist se connect kar doon?",
                    f"Link dispatch limit reach ho chuki hai {session.customer_name} ji. Aap direct Google Pay ya PhonePe se pay karna chahenge, ya callback schedule kar doon?",
                ]
                options_en = [
                    f"I have already resent the payment link twice, {session.customer_name}. Would you like to pay directly via UPI ID, or connect with a specialist?",
                    f"Link delivery seems delayed on the network, {session.customer_name}. Shall I offer direct UPI details or transfer to our support team?",
                ]
            else:
                session.last_agent_prompt_type = "link_delivered_check"
                options_hi = [
                    f"Maine aapke number {session.customer_phone} par 1-click link bhej diya tha {session.customer_name} ji. Kya notification mil gayi?",
                    f"Kya aapko WhatsApp ya SMS par payment link receive hua {session.customer_name} ji? Agar nahi mila toh batayein.",
                    f"Payment link {session.customer_phone} par active hai {session.customer_name} ji. Kya payment complete karne mein koi sahayata chahiye?",
                ]
                options_en = [
                    f"I dispatched the payment link to {session.customer_phone}, {session.customer_name}. Did you receive the notification?",
                    f"Could you confirm if the payment link reached your WhatsApp or SMS, {session.customer_name}?",
                    f"The payment link is active on your phone, {session.customer_name}. Let me know if you need any help completing it.",
                ]
        elif session.dispute_filed:
            session.last_agent_prompt_type = "dispute_choice"
            options_hi = [
                f"Aapka dispute ticket under monitoring hai {session.customer_name} ji. Bank 3–5 dino mein auto-reverse kar dega. Kya aap order continue rakhne ke liye fresh link chahenge?",
                f"Chinta mat kijiye {session.customer_name} ji, aapke paise bilkul safe hain aur bank auto-reversal ho jayega. Kya main order delay rokne ke liye ek fresh link bhejun?",
                f"Dispute record ho chuka hai {session.customer_name} ji. Kya main is mamle mein kuch aur madad kar sakta hoon?",
            ]
            options_en = [
                f"Your dispute is being monitored, {session.customer_name}. The bank will reverse the funds in 3–5 business days. Would you like a fresh link to avoid order cancellation?",
                f"Rest assured your funds are safe with bank auto-reversal, {session.customer_name}. Would you like an alternative link in the meantime?",
                f"The dispute ticket is logged, {session.customer_name}. Is there anything else regarding this transaction I can assist with?",
            ]
        elif session.identity_confirmed:
            session.last_agent_prompt_type = "link_offered"
            options_hi = [
                f"Ji {session.customer_name} ji, main aapki poori madad karne ke liye hoon. Kya main aapke WhatsApp par Rs. {session.amount:,.2f} ka 1-click payment link bhej doon?",
                f"Aapka transaction recover karne ke liye main abhi ek secure Razorpay link bhej sakta hoon {session.customer_name} ji. Kya main bhej doon?",
                f"Kya aap UPI se dobara attempt karna chahenge {session.customer_name} ji, ya WhatsApp par instant payment link bhejun?",
            ]
            options_en = [
                f"I'm here to assist you, {session.customer_name}. Shall I send a 1-click payment link for Rs. {session.amount:,.2f} to your WhatsApp right now?",
                f"To help recover this payment quickly, {session.customer_name}, I can dispatch a secure link to your phone. Would you like that?",
                f"Would you prefer a direct UPI retry, {session.customer_name}, or shall I send a WhatsApp payment link?",
            ]
        else:
            session.last_agent_prompt_type = "link_offered"
            options_hi = [
                f"Ji {session.customer_name} ji, main Razorpay se aapke Rs. {session.amount:,.2f} ke pending payment ke silsile mein baat kar raha hoon. Kya main aapko ek secure link bhejun?",
                f"Main aapki payment issue resolve karne mein madad kar sakta hoon {session.customer_name} ji. Kya main aapko payment link bhej doon?",
                f"Kya main {session.customer_name} ji se baat kar raha hoon? Main aapke failed payment ko easily clear karne mein guide kar sakta hoon.",
            ]
            options_en = [
                f"Hello {session.customer_name}, I'm calling regarding your pending payment of Rs. {session.amount:,.2f}. Shall I send a secure link to resolve it?",
                f"I'm here to help resolve your recent transaction issue, {session.customer_name}. May I send you a 1-click link to complete it?",
                f"Am I speaking with {session.customer_name}? I can help you easily complete your payment for Rs. {session.amount:,.2f}.",
            ]

        pool = options_hi if lang in ("hi", "hinglish") else options_en
        for opt in pool:
            if opt != session.last_assistant_reply:
                return opt
        return pool[0]


# Global Voice Recovery Agent instance
voice_recovery_agent = VoiceRecoveryAgent()
