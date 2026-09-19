"""
Intent Engine — the single entry point that turns a raw merchant
utterance into a ParsedIntent, resolving pronomial references
("isko", "ise") against Redis session memory along the way.

    FastAPI Gateway -> Intent Engine -> Agent Router -> Business Tools

This module is the "Intent Engine" box in that pipeline.
"""
from app.core.redis_client import SessionMemory, get_session_memory
from app.intent.llm_parser import build_llm_parser
from app.intent.rule_based_parser import parse as rule_based_parse
from app.intent.schemas import ParsedIntent

_llm_parser = build_llm_parser()  # None if no LLM key configured -> pure rule-based mode


class IntentEngine:
    async def interpret(self, customer_id: int, text: str) -> ParsedIntent:
        session = get_session_memory(customer_id)

        parsed = await self._parse(text)
        parsed = await self._resolve_references(parsed, session)

        await session.append_history(role="merchant", text=text)
        if parsed.items:
            last_item = parsed.items[-1]
            if last_item.product:
                await session.update(last_product=last_item.product)
        await session.update(last_intent=parsed.intent.value)

        return parsed

    async def _parse(self, text: str) -> ParsedIntent:
        if _llm_parser is not None:
            try:
                return await _llm_parser.parse(text)
            except Exception:
                # Never let an LLM/API hiccup break the merchant flow —
                # degrade gracefully to the offline rule-based parser.
                pass
        return rule_based_parse(text)

    async def _resolve_references(
        self, parsed: ParsedIntent, session: SessionMemory
    ) -> ParsedIntent:
        """Fill in pronoun references like 'isko' using last_product from Redis."""
        if not parsed.items:
            return parsed

        state = await session.get()
        last_product = state.get("last_product")

        for item in parsed.items:
            if item.is_reference and not item.product and last_product:
                item.product = last_product

        return parsed


def get_intent_engine() -> IntentEngine:
    return IntentEngine()
