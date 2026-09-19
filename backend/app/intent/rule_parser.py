"""Conservative offline extraction; only exact commands bypass the LLM."""
import re

from app.intent.rule_based_parser import (
    HINDI_NUMERALS, PRODUCT_ALIASES, UNIT_ALIASES, _normalize_text,
    parse as legacy_parse,
)
from app.intent.schemas import IntentType, ItemMention, ParsedIntent

QUANTITY = r"(?:\d+(?:\.\d+)?|" + "|".join(sorted(HINDI_NUMERALS, key=len, reverse=True)) + r")\b"
UNIT = r"(?:" + "|".join(sorted(UNIT_ALIASES, key=len, reverse=True)) + r")\b"
MEASURE = rf"(?P<qty>{QUANTITY})(?:\s*(?P<unit>{UNIT}))?"
PRODUCT = re.compile(r"\b(?:" + "|".join(sorted(PRODUCT_ALIASES, key=len, reverse=True)) + r")\b")
REFERENCE = re.compile(r"\b(?:isko|ise|usko|wahi|iska|isse)\b")


class RuleIntentParser:
    def parse(self, transcript: str) -> ParsedIntent:
        text = _normalize_text(transcript).strip()
        for word, replacement in {"उसको": "usko", "वही": "wahi"}.items():
            text = text.replace(word, replacement)
        if not text:
            return ParsedIntent(intent=IntentType.UNKNOWN, raw_text=transcript, confidence=0)
        customer_bill = re.search(r"^(?P<name>.+?)\s+के\s+नाम(?:\s+का)?\s+.*(?:बिल|बेल)", transcript.strip())
        if customer_bill:
            return ParsedIntent(
                intent=IntentType.CUSTOMER_BILLS,
                customer_name=customer_bill.group("name").strip(),
                raw_text=transcript,
                confidence=0.95,
            )
        if ("सबसे" in transcript and ("बिका" in transcript or "बिकने" in transcript)) or re.search(r"\b(?:top|best.?selling|sabse zyada)\b", text):
            return ParsedIntent(intent=IntentType.TOP_PRODUCTS, raw_text=transcript, confidence=0.95)
        if ("स्टॉक" in transcript and "खत्म" in transcript and ("रिमाइंडर" in transcript or "भेज" in transcript)) or re.search(r"\b(?:stock|restock).*(?:reminder|bhej)\b", text):
            return ParsedIntent(intent=IntentType.RESTOCK_REMINDER, raw_text=transcript, confidence=0.95)
        try:
            result = legacy_parse(transcript)
        except ValueError:
            return ParsedIntent(intent=IntentType.UNKNOWN, raw_text=transcript, confidence=0)
        # Segment around products so a quantity cannot accidentally be reused.
        products = list(PRODUCT.finditer(text))
        items: list[ItemMention] = []
        consumed_until = 0
        for index, product in enumerate(products):
            before = text[consumed_until:product.start()]
            measure = re.search(MEASURE + r"\s*$", before)
            end = product.end()
            if measure is None:
                next_start = products[index + 1].start() if index + 1 < len(products) else len(text)
                after = text[product.end():next_start]
                measure = re.match(r"\s+" + MEASURE, after)
                if measure:
                    # 'rice and 2 kg flour' belongs to the next product.
                    end += measure.end()
            quantity = None
            unit = None
            if measure:
                raw = measure.group("qty")
                quantity = float(HINDI_NUMERALS[raw]) if raw in HINDI_NUMERALS else float(raw)
                unit = UNIT_ALIASES.get(measure.group("unit"))
            if quantity is not None and quantity <= 0:
                return ParsedIntent(intent=IntentType.UNKNOWN, raw_text=transcript, confidence=0)
            items.append(ItemMention(product=PRODUCT_ALIASES[product.group()], quantity=quantity, unit=unit))
            consumed_until = end
        if not items and REFERENCE.search(text):
            measure = re.search(MEASURE, text)
            raw = measure.group("qty") if measure else None
            quantity = (float(HINDI_NUMERALS[raw]) if raw in HINDI_NUMERALS else float(raw)) if raw else None
            if quantity is not None and quantity <= 0:
                return ParsedIntent(intent=IntentType.UNKNOWN, raw_text=transcript, confidence=0)
            items = [ItemMention(is_reference=True, quantity=quantity,
                                 unit=UNIT_ALIASES.get(measure.group("unit")) if measure else None)]
            if quantity is not None and result.intent == IntentType.UNKNOWN:
                result.intent = IntentType.UPDATE_QUANTITY
        result.items = items
        if result.intent == IntentType.UNKNOWN and items and any(i.product for i in items):
            result.intent = IntentType.ADD_TO_CART
        if result.intent == IntentType.UNKNOWN:
            if re.search(r"\bremove\b", text):
                result.intent = IntentType.REMOVE_FROM_CART
            elif re.search(r"\bsales\b", text):
                # No time period: let Groq clarify instead of assuming a day.
                pass
        result.confidence = 0.65 if result.intent != IntentType.UNKNOWN else 0.0
        exact = {
            "cart": IntentType.VIEW_CART, "cart dikhao": IntentType.VIEW_CART,
            "show cart": IntentType.VIEW_CART, "view cart": IntentType.VIEW_CART,
            "order bana do": IntentType.CREATE_ORDER, "order banao": IntentType.CREATE_ORDER,
            "bill banao": IntentType.CREATE_ORDER,
        }
        command = text.strip(" .!?।")
        if command in exact:
            result.intent = exact[command]
            result.confidence = 0.99
        return result
