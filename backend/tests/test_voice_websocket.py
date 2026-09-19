import unittest
from fastapi.testclient import TestClient
from app.agents.cart_agent import AgentResponse
from app.api.routes import voice
from app.intent.schemas import IntentType, ParsedIntent
from app.main import app

class FakeSession:
    async def __aenter__(self): return self
    async def __aexit__(self,*_): return None
    async def commit(self): return None
    async def rollback(self): return None
class FakeIntentEngine:
    async def interpret(self,customer_id,text): return ParsedIntent(intent=IntentType.VIEW_CART,raw_text=text)
class FakeRouter:
    def __init__(self,session): self.session=session
    async def route(self,customer_id,intent): return AgentResponse(speech="Cart is empty.",data={},success=True)

class VoiceWebSocketTests(unittest.TestCase):
    def test_stream_does_not_fall_through_to_static_files(self):
        original=(voice.AsyncSessionLocal,voice.get_intent_engine,voice.AgentRouter)
        voice.AsyncSessionLocal=lambda:FakeSession(); voice.get_intent_engine=lambda:FakeIntentEngine(); voice.AgentRouter=FakeRouter
        try:
            with TestClient(app).websocket_connect("/api/voice/stream") as socket:
                self.assertEqual(socket.receive_json(),{"type":"ready"})
                socket.send_json({"type":"transcript","customer_id":1,"text":"cart dikhao","is_final":True})
                self.assertEqual(socket.receive_json()["type"],"reply")
        finally:
            voice.AsyncSessionLocal,voice.get_intent_engine,voice.AgentRouter=original
