"""Hybrid orchestration with bounded provider latency and offline degradation."""
import logging
from typing import Protocol

from app.intent.catalog import CatalogResolver
from app.intent.rule_parser import RuleIntentParser
from app.intent.schemas import IntentType, ParsedIntent

logger = logging.getLogger(__name__)


class AsyncIntentParser(Protocol):
    async def parse(self, transcript: str) -> ParsedIntent: ...


class IntentService:
    def __init__(self, groq_parser: AsyncIntentParser | None = None,
                 rule_parser: RuleIntentParser | None = None,
                 catalog_resolver: CatalogResolver | None = None):
        self.groq_parser = groq_parser
        self.rule_parser = rule_parser or RuleIntentParser()
        self.catalog_resolver = catalog_resolver

    async def parse(self, transcript: str) -> ParsedIntent:
        if not transcript.strip() or len(transcript) > 4000:
            return ParsedIntent(intent=IntentType.UNKNOWN, raw_text=transcript, confidence=0)
        result = None
        if self.groq_parser is not None:
            try:
                result = await self.groq_parser.parse(transcript)
            except Exception as error:
                # Never log transcript text, provider bodies, or API credentials.
                logger.warning("intent_provider_fallback error_type=%s", type(error).__name__)
        if result is None:
            result = self.rule_parser.parse(transcript)
        if self.catalog_resolver:
            for item in result.items:
                if not item.is_reference:
                    item.product = self.catalog_resolver.resolve(item.product)
        return result
