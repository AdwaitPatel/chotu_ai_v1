"""
LLM-backed Intent parser using function/tool calling.

This is the production path: given a merchant utterance in Hindi,
Hinglish, or English, we ask the LLM to call a single function
`extract_intent` with strictly-typed arguments matching ParsedIntent.
Swap OPENAI_ / GROQ_ / GEMINI_ clients here without touching the rest of the
system — IntentEngine only depends on `LLMIntentParser.parse()`.
"""
import json
from typing import Protocol

from app.core.config import get_settings
from app.intent.schemas import IntentType, ItemMention, ParsedIntent

SYSTEM_PROMPT = """You are the Intent Engine for a kirana (small retail) store
assistant. Merchants speak in Hindi, Hinglish, or English. Classify each
utterance into exactly one intent and extract any product/quantity/unit
mentions. "inventory mein add karo" means RESTOCK_INVENTORY: increase the
merchant's own stock, never a customer cart. Always call the `extract_intent`
function — never reply in plain text.
"""

EXTRACT_INTENT_FUNCTION = {
    "name": "extract_intent",
    "description": "Extract the structured intent and item mentions from a merchant utterance.",
    "parameters": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": [t.value for t in IntentType],
            },
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "product": {"type": "string"},
                        "quantity": {"type": "number"},
                        "unit": {"type": "string"},
                        "unit_price": {"type": "number", "description": "selling price per stated unit, if spoken"},
                        "is_reference": {
                            "type": "boolean",
                            "description": "true if the merchant used a pronoun like 'isko'/'ise' instead of naming the product",
                        },
                    },
                    "required": ["product"],
                },
            },
        },
        "required": ["intent", "items"],
    },
}


class LLMClient(Protocol):
    """Any client (Gemini, OpenAI, ...) implementing this can back the parser."""

    async def call_with_function(
        self, system_prompt: str, user_text: str, function_schema: dict
    ) -> dict:
        """Returns the parsed function-call arguments as a dict."""
        ...


class OpenAIClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def call_with_function(
        self, system_prompt: str, user_text: str, function_schema: dict
    ) -> dict:
        from openai import AsyncOpenAI  # local import: optional dependency

        client = AsyncOpenAI(api_key=self.api_key)
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            tools=[{"type": "function", "function": function_schema}],
            tool_choice={"type": "function", "function": {"name": function_schema["name"]}},
        )
        tool_call = response.choices[0].message.tool_calls[0]
        return json.loads(tool_call.function.arguments)


class GroqClient:
    """Groq's OpenAI-compatible API client."""

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    async def call_with_function(
        self, system_prompt: str, user_text: str, function_schema: dict
    ) -> dict:
        from openai import AsyncOpenAI  # Groq exposes an OpenAI-compatible API

        client = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.groq.com/openai/v1",
        )
        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            tools=[{"type": "function", "function": function_schema}],
            tool_choice={"type": "function", "function": {"name": function_schema["name"]}},
        )
        tool_call = response.choices[0].message.tool_calls[0]
        return json.loads(tool_call.function.arguments)


class GeminiClient:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def call_with_function(
        self, system_prompt: str, user_text: str, function_schema: dict
    ) -> dict:
        import google.generativeai as genai  # local import: optional dependency

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(
            "gemini-1.5-flash",
            system_instruction=system_prompt,
            tools=[{"function_declarations": [function_schema]}],
        )
        response = await model.generate_content_async(user_text)
        call = response.candidates[0].content.parts[0].function_call
        return dict(call.args)


class LLMIntentParser:
    def __init__(self, client: LLMClient):
        self.client = client

    async def parse(self, text: str) -> ParsedIntent:
        args = await self.client.call_with_function(
            SYSTEM_PROMPT, text, EXTRACT_INTENT_FUNCTION
        )
        items = [
            ItemMention(
                product=item.get("product", ""),
                quantity=item.get("quantity"),
                unit=item.get("unit"),
                unit_price=item.get("unit_price"),
                is_reference=item.get("is_reference", False),
            )
            for item in args.get("items", [])
        ]
        return ParsedIntent(
            intent=IntentType(args["intent"]),
            items=items,
            raw_text=text,
            confidence=0.95,
        )


def build_llm_parser() -> LLMIntentParser | None:
    """Factory: returns None if no LLM provider is configured (rule-based fallback used instead)."""
    settings = get_settings()
    if settings.LLM_PROVIDER == "openai" and settings.OPENAI_API_KEY:
        return LLMIntentParser(OpenAIClient(settings.OPENAI_API_KEY))
    if settings.LLM_PROVIDER == "groq" and settings.GROQ_API_KEY:
        return LLMIntentParser(GroqClient(settings.GROQ_API_KEY, settings.GROQ_MODEL))
    if settings.LLM_PROVIDER == "gemini" and settings.GEMINI_API_KEY:
        return LLMIntentParser(GeminiClient(settings.GEMINI_API_KEY))
    return None
