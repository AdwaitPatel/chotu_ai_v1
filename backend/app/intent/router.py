"""Stateless extraction endpoint; voice session context remains in IntentEngine."""
from fastapi import APIRouter, Depends, Request

from app.intent.schemas import IntentParseRequest, ParsedIntent
from app.intent.service import IntentService

router = APIRouter(prefix="/api/intent", tags=["intent"])


def get_intent_service(request: Request) -> IntentService:
    return request.app.state.intent_service


@router.post("/parse", response_model=ParsedIntent)
async def parse_intent(payload: IntentParseRequest,
                       service: IntentService = Depends(get_intent_service)) -> ParsedIntent:
    return await service.parse(payload.transcript)
