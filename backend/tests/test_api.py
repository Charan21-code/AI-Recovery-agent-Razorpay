"""
Integration tests for FastAPI REST API endpoints.
Verifies Analytics, Opportunity Queue, Pipeline Simulation, and Voice Agent turns.
"""

import pytest
from fastapi.testclient import TestClient
from backend.db.init_db import init_sync_db
from backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_sync_db()
    yield


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["voice_agent"] == "ready"


def test_get_kpis():
    response = client.get("/api/v1/analytics/kpis")
    assert response.status_code == 200
    data = response.json()
    assert "total_revenue_at_risk" in data
    assert "total_revenue_recovered" in data
    assert "channels" in data
    assert len(data["channels"]) >= 4


def test_get_opportunity_queue():
    response = client.get("/api/v1/analytics/queue?limit=10")
    assert response.status_code == 200
    queue = response.json()
    assert isinstance(queue, list)
    assert len(queue) > 0
    item = queue[0]
    assert "customer_name" in item
    assert "expected_recovery_value" in item
    assert "recovery_propensity" in item


def test_get_event_explorer():
    response = client.get("/api/v1/analytics/events?limit=10")
    assert response.status_code == 200
    events = response.json()
    assert isinstance(events, list)
    assert len(events) > 0
    assert "event_type" in events[0]


def test_get_customer_360():
    response = client.get("/api/v1/customers/cust_blr_01")
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == "cust_blr_01"
    assert "metrics" in data
    assert "lifetime_value" in data["metrics"]


def test_simulate_pipeline():
    payload = {
        "event_type": "payment.failed",
        "amount": 4999.0,
        "previous_attempts": 0,
        "opt_out": False,
        "is_vip": True,
        "system_degradation": False,
        "customer_name": "Rohan Malhotra",
        "failure_category": "TRANSIENT_BANK_TIMEOUT",
    }
    response = client.post("/api/v1/pipeline/simulate", json=payload)
    assert response.status_code == 200, f"Error: {response.status_code} - {response.text}"
    data = response.json()
    assert "stages" in data
    assert "1_ingestion" in data["stages"]
    assert "4_ml_prediction" in data["stages"]
    assert "6_policy_verdict" in data["stages"]
    assert "7_execution_and_llm" in data["stages"]
    assert "8_outcome_and_feedback" in data["stages"]


def test_voice_session_lifecycle():
    # 1. Start Session
    start_payload = {
        "customer_id": "cust_blr_01",
        "payment_id": "pay_test_api_01",
        "language": "hinglish",
    }
    res_start = client.post("/api/v1/voice/session/start", json=start_payload)
    assert res_start.status_code == 200
    session_data = res_start.json()
    session_id = session_data["session_id"]
    assert session_id.startswith("vcall_")
    assert session_data["greeting_turn"] is not None

    # 2. Process Turn - Payment Link Request
    turn_payload = {
        "session_id": session_id,
        "speech_text": "Please send me a payment link on WhatsApp",
    }
    res_turn = client.post("/api/v1/voice/session/turn", json=turn_payload)
    assert res_turn.status_code == 200
    turn_data = res_turn.json()
    assert turn_data["session_id"] == session_id
    assert "turn" in turn_data
    tool_calls = turn_data["turn"].get("tool_calls", [])
    assert any(tc["tool_name"] == "create_payment_link" for tc in tool_calls)

    # 3. Retrieve Session
    res_get = client.get(f"/api/v1/voice/session/{session_id}")
    assert res_get.status_code == 200
    full_session = res_get.json()
    assert len(full_session["turns"]) >= 3  # greeting, user, assistant
