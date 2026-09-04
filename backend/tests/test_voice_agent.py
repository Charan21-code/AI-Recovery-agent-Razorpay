"""
Tests for Autonomous Voice Recovery Agent and Tool Suite.
Verifies security invariants, tool calling, and multilingual conversational logic.
"""

import pytest
from backend.services.voice.tools import voice_recovery_tools
from backend.services.voice.agent import voice_recovery_agent


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
