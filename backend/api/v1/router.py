"""
FastAPI v1 API Router: Exposes Analytics, Opportunity Queue, Pipeline Simulation,
and Autonomous Voice Agent interaction endpoints.
"""

import asyncio
import json
from typing import Any, Dict, Optional
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.db.session import SyncSessionLocal
from backend.services.analytics import analytics_service
from backend.services.ingestion.receiver import ingest_raw_event
from backend.services.normalization.normalizer import normalize_razorpay_event
from backend.services.voice import voice_recovery_agent

logger = get_logger("api_v1_router")

router = APIRouter()


class SimulationRequest(BaseModel):
    event_type: str = Field(default="payment.failed")
    amount: float = Field(default=4999.0, ge=1.0)
    previous_attempts: int = Field(default=0, ge=0, le=10)
    opt_out: bool = Field(default=False)
    is_vip: bool = Field(default=False)
    system_degradation: bool = Field(default=False)
    customer_name: str = Field(default="Priya Sharma")
    failure_category: str = Field(default="TRANSIENT_BANK_TIMEOUT")


class VoiceSessionStartRequest(BaseModel):
    customer_id: str = Field(default="cust_blr_01")
    payment_id: str = Field(default="pay_live_2000")
    language: str = Field(default="hinglish")
    customer_name: Optional[str] = Field(default=None)
    customer_phone: Optional[str] = Field(default=None)
    amount: Optional[float] = Field(default=None)
    failure_reason: Optional[str] = Field(default=None)


class VoiceSessionTurnRequest(BaseModel):
    session_id: str
    speech_text: str


# -------------------------------------------------------------------------
# Analytics & Monitoring Endpoints
# -------------------------------------------------------------------------

@router.get("/analytics/kpis", summary="Macro Business KPIs")
async def get_kpis(time_range: str = Query(default="30d")):
    """Returns top-level financial metrics, channel performance, and recovery trends."""
    return analytics_service.get_kpis(time_range=time_range)


@router.get("/analytics/queue", summary="Prioritized Opportunity Queue")
async def get_opportunity_queue(limit: int = Query(default=50, ge=1, le=100)):
    """Returns ranked opportunities sorted by Expected Recovery Value."""
    return analytics_service.get_opportunity_queue(limit=limit)


@router.get("/analytics/events", summary="Real-time Event Explorer Feed")
async def get_event_explorer(limit: int = Query(default=50, ge=1, le=100)):
    """Returns normalized events stream with recovery actionability."""
    return analytics_service.get_event_explorer(limit=limit)


@router.get("/analytics/bandit", summary="Reinforcement Learning Bandit Metrics")
async def get_bandit_analytics():
    """Returns multi-armed bandit arm pulls, average rewards, and policy ranking."""
    return analytics_service.get_bandit_analytics()


@router.get("/customers/{customer_id}", summary="Customer 360 View")
async def get_customer_360(customer_id: str):
    """Returns customer profile, lifetime metrics, and intervention history."""
    return analytics_service.get_customer_360(customer_id=customer_id)


# -------------------------------------------------------------------------
# Interactive 8-Stage Pipeline Simulation
# -------------------------------------------------------------------------

@router.post("/pipeline/simulate", summary="Execute 8-Stage Recovery Pipeline")
async def simulate_pipeline(req: SimulationRequest):
    """Executes full autonomous recovery pipeline across all 8 stages and returns trace."""
    try:
        result = analytics_service.simulate_pipeline(req.model_dump())
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# -------------------------------------------------------------------------
# Real-time Live Event SSE Stream
# -------------------------------------------------------------------------

@router.get("/stream/live-events", summary="Real-time Live Pipeline Event Stream (SSE)")
async def stream_live_events(interval_seconds: float = Query(default=5.0, ge=1.0, le=30.0)):
    """
    Server-Sent Events (SSE) endpoint.
    Continuously streams autonomous pipeline execution events in real-time.
    Frontend connects with EventSource('http://localhost:8000/api/v1/stream/live-events').
    Each event is a complete 8-stage pipeline run on a randomly generated payment failure.
    """
    async def event_generator():
        # Send an initial heartbeat
        yield "data: {\"stream_type\": \"connected\", \"message\": \"Live pipeline stream connected\"}\n\n"
        while True:
            try:
                # Run pipeline event generation in thread pool to avoid blocking
                import concurrent.futures
                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    event_data = await loop.run_in_executor(
                        pool, analytics_service.generate_live_pipeline_event
                    )
                yield f"data: {json.dumps(event_data)}\n\n"
            except asyncio.CancelledError:
                break
            except Exception as e:
                yield f"data: {{\"stream_type\": \"error\", \"message\": \"{str(e)}\"}}\n\n"
            await asyncio.sleep(interval_seconds)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
        },
    )


# -------------------------------------------------------------------------
# Autonomous Voice Agent Endpoints
# -------------------------------------------------------------------------

@router.post("/voice/session/start", summary="Start Autonomous Voice Call")
async def start_voice_session(req: VoiceSessionStartRequest):
    """Initializes a voice session and generates the personalized multilingual greeting."""
    try:
        session = voice_recovery_agent.start_session(
            customer_id=req.customer_id,
            payment_id=req.payment_id,
            language=req.language,
            customer_name=req.customer_name,
            customer_phone=req.customer_phone,
            amount=req.amount,
            failure_reason=req.failure_reason,
        )
        return {
            "session_id": session.session_id,
            "customer_id": session.customer_id,
            "payment_id": session.payment_id,
            "customer_name": session.customer_name,
            "amount": session.amount,
            "currency": session.currency,
            "status": session.status,
            "language": session.language_preference,
            "greeting_turn": session.turns[0].model_dump() if session.turns else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/voice/session/turn", summary="Process Voice Conversational Turn")
async def process_voice_turn(req: VoiceSessionTurnRequest):
    """
    Processes speech input from customer, enforces security boundaries,
    executes backend tools, and returns spoken response and tool trace.
    """
    try:
        turn = voice_recovery_agent.process_turn(
            session_id=req.session_id,
            user_speech=req.speech_text,
        )
        session = voice_recovery_agent.get_session(req.session_id)
        return {
            "session_id": req.session_id,
            "turn": turn.model_dump(),
            "session_status": session.status if session else "active",
            "recorded_intent": session.recorded_intent if session else None,
        }
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voice/session/{session_id}", summary="Get Full Voice Session Transcript")
async def get_voice_session(session_id: str):
    """Retrieves full conversation turns, tool calls, and session status."""
    session = voice_recovery_agent.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Voice session '{session_id}' not found.")
    return session.model_dump()


# -------------------------------------------------------------------------
# Razorpay Inbound Webhook Endpoint
# -------------------------------------------------------------------------

@router.post("/webhooks/razorpay", summary="Razorpay Inbound Webhook Receiver")
async def receive_razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(default=None, alias="X-Razorpay-Signature"),
):
    """
    Receives live webhooks from Razorpay (e.g. payment.failed, payment.captured).
    Verifies HMAC-SHA256 signature against RAZORPAY_WEBHOOK_SECRET,
    checks idempotency, persists the raw payload, and passes to normalization.
    """
    payload_bytes = await request.body()
    try:
        payload_dict = json.loads(payload_bytes.decode("utf-8"))
    except Exception as e:
        logger.warning(f"Webhook received invalid JSON payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # If webhook secret is still placeholder, relax signature check for initial test pings
    verify_sig = bool(
        settings.RAZORPAY_WEBHOOK_SECRET
        and settings.RAZORPAY_WEBHOOK_SECRET != "placeholder_webhook_secret"
    )

    with SyncSessionLocal() as session:
        success, message, raw_payload_model = ingest_raw_event(
            session=session,
            payload_dict=payload_dict,
            payload_bytes=payload_bytes,
            signature=x_razorpay_signature,
            verify_sig=verify_sig,
            webhook_secret=settings.RAZORPAY_WEBHOOK_SECRET if verify_sig else None,
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        event_name = payload_dict.get("event", "unknown")
        event_id = payload_dict.get("event_id") or payload_dict.get("id")
        logger.info(f"Razorpay webhook ingested: event={event_name}, id={event_id}")

        return {
            "status": "success",
            "message": message,
            "event": event_name,
            "event_id": event_id,
        }

