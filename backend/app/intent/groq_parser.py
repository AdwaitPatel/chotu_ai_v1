"""Async Groq adapter. Transport/validation errors are handled by IntentService."""
import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.intent.prompts import SYSTEM_PROMPT
from app.intent.schemas import IntentType, ItemMention, ParsedIntent


class GroqOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intent: IntentType
    items: list[ItemMention] = Field(max_length=50)
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    customer_name: str | None = Field(default=None, max_length=255)
    report_weekday: int | None = Field(default=None, ge=0, le=6)


class GroqIntentParser:
    def __init__(self, client: httpx.AsyncClient, api_key: str,
                 model: str = "llama-3.3-70b-versatile", timeout: float = 10.0):
        self.client = client
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def parse(self, transcript: str) -> ParsedIntent:
        if not transcript.strip():
            return ParsedIntent(intent=IntentType.UNKNOWN, raw_text=transcript, confidence=0)
        response = await self.client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "temperature": 0,
                  "response_format": {"type": "json_object"},
                  "max_completion_tokens": 2048,
                  "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                               {"role": "user", "content": transcript}]},
            timeout=self.timeout,
        )
        response.raise_for_status()
        choice = response.json()["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise ValueError("Incomplete Groq extraction")
        content = choice["message"]["content"]
        if not isinstance(content, str) or len(content) > 32000:
            raise ValueError("Invalid Groq content")
        # Validate JSON types strictly; JSON enum strings are accepted by Pydantic.
        result = GroqOutput.model_validate_json(content, strict=True)
        for item in result.items:
            if not item.product and not item.is_reference:
                raise ValueError("Item has neither a product nor a reference")
            if item.is_reference and item.product:
                raise ValueError("Reference product must be resolved from session")
            if item.unit is not None and item.unit not in {"kg", "g", "litre", "ml", "piece", "packet"}:
                raise ValueError("Unsupported normalized unit")
        if result.intent in {IntentType.UNKNOWN, IntentType.IRRELEVANT} and result.items:
            raise ValueError("Unknown intent contains actionable items")
        return ParsedIntent(**result.model_dump(), raw_text=transcript)
