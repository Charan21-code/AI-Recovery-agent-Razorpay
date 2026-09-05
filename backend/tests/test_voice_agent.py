"""
Tests for Autonomous Voice Recovery Agent and Tool Suite.
Verifies security invariants, tool calling, and multilingual conversational logic.
"""

import pytest
from backend.services.voice.tools import voice_recovery_tools
from backend.services.voice.agent import voice_recovery_agent


@pytest.fixture(autouse=True)
def mock_voice_llm(monkeypatch):
    """Ensures unit tests validate deterministic offline logic without calling live LLM APIs."""
    monkeypatch.setattr(voice_recovery_agent, "provider", "mock")


def test_voice_tool_suite_operations():
    """Validates that all voice recovery tools execute and return expected schemas."""
    # 1. Status check
    status = voice_recovery_tools.get_payment_status("pay_test_12345")
    assert "payment_id" in status
    assert "status" in status
    assert "captured" in status

    # 2. Payment details
    details = voice_recovery_tools.get_payment_details("pay_test_12345")
    assert details["payment_id"] == "pay_test_12345"
    assert "amount" in details
    assert "customer_name" in details

    # 3. Create payment link
    link_res = voice_recovery_tools.create_payment_link(
        customer_id="cust_test_1",
        amount=1999.00,
        customer_name="Rohan Verma",
        customer_phone="+919876543210",
    )
    assert link_res["success"] is True
    assert "short_url" in link_res
    assert link_res["amount"] == 1999.00

    # 4. Schedule recovery
    sched_res = voice_recovery_tools.schedule_recovery(
        customer_id="cust_test_1",
        payment_id="pay_test_12345",
        channel="voice",
        scheduled_time_iso="2026-09-05T10:00:00Z",
    )
    assert sched_res["scheduled"] is True
    assert sched_res["channel"] == "voice"

    # 5. Escalate to human
    esc_res = voice_recovery_tools.escalate_to_human(
        customer_id="cust_test_1",
        reason="Customer requested senior account manager",
        priority="HIGH",
    )
    assert esc_res["escalated"] is True
    assert "ticket_id" in esc_res

    # 6. Record intent
    intent_res = voice_recovery_tools.record_customer_intent(
        customer_id="cust_test_1",
        payment_id="pay_test_12345",
        intent="PROMISE_TO_PAY",
        sentiment="POSITIVE",
    )
    assert intent_res["recorded"] is True
    assert intent_res["intent"] == "PROMISE_TO_PAY"


def test_voice_agent_greeting_and_session():
    """Validates session startup and multilingual greeting generation."""
    session = voice_recovery_agent.start_session(
        customer_id="cust_test_greeting",
        payment_id="pay_test_greet",
        language="hinglish",
    )
    assert session.session_id.startswith("vcall_")
    assert len(session.turns) == 1
    assert session.turns[0].role == "assistant"
    assert "Namaste" in session.turns[0].content or "Razorpay" in session.turns[0].content


def test_voice_agent_security_invariant_zero_credentials():
    """
    CRITICAL: Tests that agent enforces Zero Credential Collection.
    Never accepts OTP, CVV, or PIN and immediately warns user.
    """
    session = voice_recovery_agent.start_session(
        customer_id="cust_test_sec",
        payment_id="pay_test_sec",
        language="en",
    )
    turn = voice_recovery_agent.process_turn(session.session_id, "My OTP is 492019, can you enter it?")
    
    assert turn.role == "assistant"
    # Must refuse credential sharing
    assert any(w in turn.content.lower() for w in ["never share", "stop", "confidential", "rukiye", "pin"])
    assert len(turn.tool_calls) == 0  # No tool called on security violation


def test_voice_agent_deduction_claim_checks_status():
    """
    CRITICAL: Tests that agent never claims payment succeeded without tool confirmation.
    Must invoke get_payment_status tool.
    """
    session = voice_recovery_agent.start_session(
        customer_id="cust_test_deduct",
        payment_id="pay_test_deduct",
        language="hinglish",
    )
    turn = voice_recovery_agent.process_turn(
        session.session_id,
        "Arre paise kat gaye mere bank account se, payment ho chuka hai!",
    )
    
    # Must have called get_payment_status tool
    tool_names = [tc.tool_name for tc in turn.tool_calls]
    assert "get_payment_status" in tool_names
    # Must mention auto-reversal if not captured or captured if verified
    assert any(w in turn.content.lower() for w in ["reverse", "refund", "captured", "bank", "check"])


def test_voice_agent_payment_link_dispatch():
    """Tests that user requesting a link triggers create_payment_link tool."""
    session = voice_recovery_agent.start_session(
        customer_id="cust_test_link",
        payment_id="pay_test_link",
        language="en",
    )
    turn = voice_recovery_agent.process_turn(
        session.session_id,
        "Please send me a payment link on WhatsApp, I will pay right now.",
    )
    
    tool_names = [tc.tool_name for tc in turn.tool_calls]
    assert "create_payment_link" in tool_names
    assert "link" in turn.content.lower() or "dispatched" in turn.content.lower()


def test_voice_agent_greeting_identity_and_affirmative_link_flow():
    """
    Validates end-to-end multi-turn flow:
    1. Greeting -> 2. Customer confirms identity ("Haan bol raha hoon")
    -> 3. Customer accepts link offer ("Haan bhej do") -> 4. Acknowledges delivery ("Mil gaya")
    -> 5. In-progress hold ("Wait karo pay kar raha hoon") -> 6. Completion claim ("Pay kar diya")
    """
    session = voice_recovery_agent.start_session(
        customer_id="cust_multi_1",
        payment_id="pay_multi_1",
        language="hinglish",
    )
    assert session.last_agent_prompt_type == "greeting_identity"

    # Step 1: User confirms identity
    turn1 = voice_recovery_agent.process_turn(session.session_id, "Haan, main Rohan bol raha hoon.")
    assert session.identity_confirmed is True
    assert session.last_agent_prompt_type == "link_offered"
    assert any(w in turn1.content.lower() for w in ["shukriya", "confirm", "payment", "link"])

    # Step 2: User agrees affirmatively to receive link
    turn2 = voice_recovery_agent.process_turn(session.session_id, "Haan theek hai, link bhej do.")
    assert session.payment_link_sent is True
    tool_names = [tc.tool_name for tc in turn2.tool_calls]
    assert "create_payment_link" in tool_names
    assert session.last_agent_prompt_type == "link_delivered_check"

    # Step 3: User confirms delivery
    turn3 = voice_recovery_agent.process_turn(session.session_id, "Haan mil gaya link!")
    assert session.link_delivery_confirmed is True
    assert any(w in turn3.content.lower() for w in ["badhiya", "line par", "wait", "complete"])

    # Step 4: User states payment is in progress
    turn4 = voice_recovery_agent.process_turn(session.session_id, "Ek minute ruko, pay kar raha hoon.")
    assert session.payment_in_progress is True
    assert any(w in turn4.content.lower() for w in ["aaram se", "koi jaldi nahi", "available", "line"])

    # Step 5: User claims payment completed
    turn5 = voice_recovery_agent.process_turn(session.session_id, "Maine pay kar diya hai.")
    t5_tool_names = [tc.tool_name for tc in turn5.tool_calls]
    assert "get_payment_status" in t5_tool_names


def test_voice_agent_informational_queries():
    """Validates responses to caller identity, amount, and payment method inquiries."""
    session = voice_recovery_agent.start_session(
        customer_id="cust_info_1",
        payment_id="pay_info_1",
        language="hinglish",
    )

    # 1. Caller identity
    turn_id = voice_recovery_agent.process_turn(session.session_id, "Aap kaun bol rahe ho?")
    assert "razorpay" in turn_id.content.lower()

    # 2. Amount inquiry
    turn_amt = voice_recovery_agent.process_turn(session.session_id, "Kitna amount pay karna hai?")
    assert f"{session.amount:,.2f}" in turn_amt.content or "2,499" in turn_amt.content

    # 3. Payment methods inquiry
    turn_methods = voice_recovery_agent.process_turn(session.session_id, "Kaise pay kar sakte hain? Google Pay chalega?")
    assert any(w in turn_methods.content.lower() for w in ["google pay", "phonepe", "upi", "card"])


def test_voice_agent_fallback_rotation_no_stuck_loop():
    """
    Validates that offline/unrecognized turns do NOT repeat the identical response
    consecutively and offer escalation after multiple failed turns.
    """
    session = voice_recovery_agent.start_session(
        customer_id="cust_fall_1",
        payment_id="pay_fall_1",
        language="en",
    )
    # Turn 1: unrecognized
    turn1 = voice_recovery_agent.process_turn(session.session_id, "Blue sky purple clouds")
    assert session.consecutive_fallback_count == 1

    # Turn 2: unrecognized - must NOT be identical to Turn 1
    turn2 = voice_recovery_agent.process_turn(session.session_id, "Random gibberish words 123")
    assert session.consecutive_fallback_count == 2
    assert turn2.content != turn1.content

    # Turn 3: unrecognized - triggers escalation offer
    turn3 = voice_recovery_agent.process_turn(session.session_id, "Still speaking complete nonsense")
    assert session.consecutive_fallback_count >= 3
    assert any(w in turn3.content.lower() for w in ["specialist", "transfer", "callback"])


def test_voice_agent_devanagari_intent_recognition():
    """
    Validates that speech transcribed in Devanagari script (from browser Web Speech API)
    correctly routes to the same intent logic as Latin Hinglish.
    """
    # 1. Deduction claim in Devanagari
    session1 = voice_recovery_agent.start_session(
        customer_id="cust_dev_1",
        payment_id="pay_dev_1",
        language="hi",
    )
    turn_deduct = voice_recovery_agent.process_turn(session1.session_id, "अरे पैसे कट गए बैंक से!")
    tool_names = [tc.tool_name for tc in turn_deduct.tool_calls]
    assert "get_payment_status" in tool_names
    assert session1.recorded_intent in ("DISPUTE_DEBITED", "PAYMENT_CAPTURED_CONFIRMED")

    # 2. Security violation in Devanagari
    session2 = voice_recovery_agent.start_session(
        customer_id="cust_dev_2",
        payment_id="pay_dev_2",
        language="hi",
    )
    turn_sec = voice_recovery_agent.process_turn(session2.session_id, "मेरा ओटीपी 582910 है")
    assert "⚠️" in turn_sec.content
    assert any(w in turn_sec.content.lower() for w in ["rukiye", "stop", "kabhi", "fraud"])

    # 3. Link request in Devanagari
    session3 = voice_recovery_agent.start_session(
        customer_id="cust_dev_3",
        payment_id="pay_dev_3",
        language="hi",
    )
    turn_link = voice_recovery_agent.process_turn(session3.session_id, "हाँ मुझे लिंक भेज दो")
    tool_names_link = [tc.tool_name for tc in turn_link.tool_calls]
    assert "create_payment_link" in tool_names_link
    assert session3.payment_link_sent is True


def test_voice_agent_max_link_resend_cap():
    """
    Validates that the agent caps link resends at max_link_resends (2)
    and switches to alternative resolution (direct UPI ID / specialist)
    rather than looping continuously.
    """
    session = voice_recovery_agent.start_session(
        customer_id="cust_cap_1",
        payment_id="pay_cap_1",
        customer_phone="+919876543210",
        language="hinglish",
    )
    assert session.link_resend_count == 0
    assert session.max_link_resends == 2

    # Attempt 1: First time asking for link
    turn1 = voice_recovery_agent.process_turn(session.session_id, "Payment link bhej do.")
    assert session.payment_link_sent is True
    assert session.link_resend_count == 1
    assert "create_payment_link" in [tc.tool_name for tc in turn1.tool_calls]

    # Attempt 2: User says didn't receive link (1st resend)
    turn2 = voice_recovery_agent.process_turn(session.session_id, "Nahi aaya link abhi tak.")
    assert session.link_resend_count == 2
    assert "create_payment_link" in [tc.tool_name for tc in turn2.tool_calls]

    # Attempt 3: User says didn't receive link AGAIN (cap reached, must NOT resend link)
    turn3 = voice_recovery_agent.process_turn(session.session_id, "Abhi bhi nahi aaya link.")
    assert session.link_resend_count == 2  # capped at 2
    tool_names_3 = [tc.tool_name for tc in turn3.tool_calls]
    assert "create_payment_link" not in tool_names_3
    # Must offer alternative resolution
    assert any(w in turn3.content.lower() for w in ["upi", "specialist", "support", "transfer", "baar"])

    # Attempt 4: User explicitly asks again (must still respect cap)
    turn4 = voice_recovery_agent.process_turn(session.session_id, "Mujhe link bhejo dobara.")
    assert session.link_resend_count == 2
    assert "create_payment_link" not in [tc.tool_name for tc in turn4.tool_calls]
    assert any(w in turn4.content.lower() for w in ["upi", "specialist", "support", "baar"])


def test_voice_agent_gemini_action_execution():
    """
    Validates that Gemini tool commands (ACTION: <tool>) are parsed and executed correctly.
    """
    session = voice_recovery_agent.start_session(
        customer_id="cust_gem_1",
        payment_id="pay_gem_1",
        language="hinglish",
    )
    raw_response = (
        "ACTION: create_payment_link\n"
        "Maine aapke registered mobile par Razorpay payment link bhej diya hai. Kripya check karein."
    )
    turn = voice_recovery_agent._execute_gemini_response(session, raw_response, "hinglish")
    assert turn.role == "assistant"
    assert "Maine aapke registered mobile" in turn.content
    assert "ACTION:" not in turn.content
    assert session.payment_link_sent is True
    assert session.link_resend_count == 1
    assert any(tc.tool_name == "create_payment_link" for tc in turn.tool_calls)


