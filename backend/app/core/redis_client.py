"""
Redis-backed conversational session memory.

Stores per-customer state so the Intent Engine / Agents can resolve
context-dependent utterances, e.g.:

    Merchant: "2 kilo chawal add karo"
    Merchant: "Isko 5 kilo kar do"   <- "isko" (this) resolves via last_product

Keys are namespaced per customer: session:{customer_id}
"""
import json
from typing import Any

import redis.asyncio as redis

from app.core.config import get_settings

settings = get_settings()

_redis_pool = redis.from_url(settings.REDIS_URL, decode_responses=True)


class SessionMemory:
    """Thin wrapper around Redis hash storage for one customer's session."""

    def __init__(self, customer_id: int):
        self.key = f"session:{customer_id}"

    async def get(self) -> dict[str, Any]:
        raw = await _redis_pool.get(self.key)
        return json.loads(raw) if raw else {}

    async def update(self, **fields: Any) -> dict[str, Any]:
        state = await self.get()
        state.update(fields)
        await _redis_pool.set(
            self.key, json.dumps(state), ex=settings.SESSION_TTL_SECONDS
        )
        return state

    async def append_history(self, role: str, text: str, max_turns: int = 20) -> None:
        state = await self.get()
        history: list[dict[str, str]] = state.get("conversation_history", [])
        history.append({"role": role, "text": text})
        state["conversation_history"] = history[-max_turns:]
        await _redis_pool.set(
            self.key, json.dumps(state), ex=settings.SESSION_TTL_SECONDS
        )

    async def clear(self) -> None:
        await _redis_pool.delete(self.key)


def get_session_memory(customer_id: int) -> SessionMemory:
    return SessionMemory(customer_id)
