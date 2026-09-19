"""
POST /api/voice/query is the unified entry point for both the voice
pipeline (after Sarvam STT transcribes speech to text) and the chat
UI. It runs: text -> Intent Engine -> Agent Router -> AgentResponse,
and the response's `speech` field is what would be sent to Sarvam TTS.
"""
import logging

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.router import AgentRouter
from app.api.schemas import AgentReplyResponse, VoiceQueryRequest
from app.core.database import AsyncSessionLocal, get_db
from app.intent.engine import IntentEngine, get_intent_engine

router = APIRouter(prefix="/api/voice", tags=["voice"])
logger = logging.getLogger(__name__)


async def _handle_stream_text(customer_id: int, text: str) -> AgentReplyResponse:
    """Process one final live-STT transcript through the merchant agents."""
    async with AsyncSessionLocal() as session:
        try:
            parsed_intent = await get_intent_engine().interpret(customer_id, text)
            result = await AgentRouter(session).route(customer_id, parsed_intent)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    return AgentReplyResponse(intent=result.intent or parsed_intent.intent.value, speech=result.speech,
                              data=result.data, success=result.success)


@router.post("/query", response_model=AgentReplyResponse)
async def voice_query(
    payload: VoiceQueryRequest,
    session: AsyncSession = Depends(get_db),
    intent_engine: IntentEngine = Depends(get_intent_engine),
):
    parsed_intent = await intent_engine.interpret(payload.customer_id, payload.text)

    agent_router = AgentRouter(session)
    result = await agent_router.route(payload.customer_id, parsed_intent)

    return AgentReplyResponse(
        intent=result.intent or parsed_intent.intent.value,
        speech=result.speech,
        data=result.data,
        success=result.success,
    )


@router.websocket("/stream")
async def voice_stream(websocket: WebSocket):
    """Receive neutral STT transcript events, emitting interim and reply events."""
    await websocket.accept()
    await websocket.send_json({"type": "ready"})
    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") != "transcript":
                await websocket.send_json({"type": "error", "message": "Expected a transcript event."})
                continue
            text = str(message.get("text", "")).strip()
            customer_id = message.get("customer_id", 1)
            if not isinstance(customer_id, int) or customer_id < 1:
                await websocket.send_json({"type": "error", "message": "customer_id must be a positive integer."})
                continue
            if not text:
                continue
            if not message.get("is_final", False):
                await websocket.send_json({"type": "interim", "text": text})
                continue
            try:
                reply = await _handle_stream_text(customer_id, text)
                await websocket.send_json({"type": "reply", "transcript": text, **reply.model_dump()})
            except Exception:
                logger.exception("Failed to process streamed transcript")
                await websocket.send_json({"type": "error", "message": "Could not process transcript. Check database and Redis."})
    except WebSocketDisconnect:
        return
