from fastapi.testclient import TestClient

from app.agents.cart_agent import AgentResponse
from app.api.routes import voice
from app.intent.schemas import IntentType, ParsedIntent
from app.main import app


class FakeSession:
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return None
    async def commit(self): return None
    async def rollback(self): return None


class FakeIntentEngine:
    async def interpret(self, customer_id, text):
        return ParsedIntent(intent=IntentType.VIEW_CART, raw_text=text)


class FakeRouter:
    def __init__(self, session): self.session = session
    async def route(self, customer_id, intent):
        return AgentResponse(speech="Cart is empty.", data={}, success=True)


def test_voice_stream_sends_interim_and_reply(monkeypatch):
    monkeypatch.setattr(voice, "AsyncSessionLocal", lambda: FakeSession())
    monkeypatch.setattr(voice, "get_intent_engine", lambda: FakeIntentEngine())
    monkeypatch.setattr(voice, "AgentRouter", FakeRouter)
    with TestClient(app).websocket_connect("/api/voice/stream") as socket:
        assert socket.receive_json() == {"type": "ready"}
        socket.send_json({"type": "transcript", "customer_id": 1, "text": "Cart", "is_final": False})
        assert socket.receive_json() == {"type": "interim", "text": "Cart"}
        socket.send_json({"type": "transcript", "customer_id": 1, "text": "Cart dikhao", "is_final": True})
        reply = socket.receive_json()
    assert reply["type"] == "reply"
    assert reply["intent"] == "VIEW_CART"
    assert reply["speech"] == "Cart is empty."
