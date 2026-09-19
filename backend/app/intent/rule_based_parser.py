"""
Rule-based fallback parser for the Intent Engine.

Works without any LLM API key so the system is demoable offline, and
serves as a fast first-pass / validation layer even when an LLM backend
is enabled. Handles the Hindi numeral words, common units, and verb
patterns from the spec's examples.
"""
import re

from app.intent.schemas import IntentType, ItemMention, ParsedIntent

HINDI_NUMERALS = {
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5,
    "che": 6, "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
}

UNIT_ALIASES = {
    "kilo": "kg", "kg": "kg", "kilogram": "kg",
    "litre": "litre", "liter": "litre", "l": "litre",
    "gram": "g", "g": "g",
    "piece": "piece", "pcs": "piece", "packet": "packet", "packets": "packet",
}

PRODUCT_ALIASES = {
    "chawal": "rice", "rice": "rice",
    "aata": "flour", "atta": "flour", "flour": "flour",
    "chini": "sugar", "sugar": "sugar",
    "tel": "edible oil", "oil": "edible oil",
    "namak": "salt", "salt": "salt",
    "dal": "lentils", "lentils": "lentils",
    "maida": "maida", "milk": "milk", "doodh": "milk",
    "maggi": "maggi",
}

# Chrome's hi-IN speech recognition normally returns Devanagari while the
# rules below use the Romanized wording common in merchant conversations.
# Normalize the supported vocabulary so either transcript form works offline.
DEVANAGARI_REPLACEMENTS = {
    "बिजनेस": "business", "बिज़नेस": "business", "बिज़नेस": "business", "एनालिसिस": "analysis", "एनालाइज": "analysis", "विश्लेषण": "analysis",
    "सेल्स": "sales", "बिक्री": "sales", "वीक": "week", "हफ्ते": "week", "हफ़्ते": "week", "सप्ताह": "week",
    "आज": "today", "महीने": "month", "मंथ": "month",
    "डाल दो": "daal do", "कर दो": "kar do",
    "चावल": "chawal", "आटा": "aata", "मैदा": "maida", "चीनी": "chini", "तेल": "tel", "फ्लावर": "flour", "गेहूं": "wheat", "ऐड": "add", "प्राइ": "price", "प्राइस": "price", "रुपये": "price",
    "दूध": "milk", "मैगी": "maggi", "पैकेट्स": "packets", "पैकेट": "packet", "लीटर": "liter", "लिटर": "liter",
    "नमक": "namak", "दाल": "dal", "कार्ट": "cart", "कार्ड": "cart", "किलो": "kilo",
    "किलोग्राम": "kilogram", "केजी": "kg", "दिखाओ": "dikhao", "दिखा": "dikha",
    "जोड़ो": "add", "जोड़": "add", "डालो": "dalo", "इसको": "isko",
    "इसे": "ise", "हटाओ": "hatao", "बिल": "bill", "बनाओ": "banao", "बना": "bana", "बनाऊं": "banao", "बनाऊँ": "banao", "डन": "done", "ऑर्डर": "order", "लाओ": "lao",
    "शुरू": "shuru", "करो": "karo", "इन्वेंटरी": "inventory",
    "डेढ़": "1.5", "डेढ़": "1.5", "ढ़ाई": "2.5", "ढाई": "2.5",
    "वन फिफ्टी": "150", "पाँच": "paanch", "पांच": "paanch", "चार": "chaar", "तीन": "teen",
    "दो": "do", "एक": "ek", "छह": "che", "सात": "saat", "आठ": "aath",
    "नौ": "nau", "दस": "das", "सौ": "sau", "के": "ke", "की": "ki", "का": "ka", "फिफ्टी": "50", "फाइव": "paanch", "फोर": "chaar",
    "थ्री": "teen", "टू": "do", "वन": "ek", "सिक्स": "che",
    "सेवन": "saat", "एट": "aath", "नाइन": "nau", "टेन": "das",
}
DEVANAGARI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _normalize_text(text: str) -> str:
    # Treat the spoken/written rupee symbol as a price marker as well.  Browser
    # STT may return either "₹20" or "20 रुपये" for the same utterance.
    normalized = text.lower().replace("₹", " price ").translate(DEVANAGARI_DIGITS)
    for source, replacement in sorted(DEVANAGARI_REPLACEMENTS.items(), key=lambda item: len(item[0]), reverse=True):
        normalized = normalized.replace(source, replacement)
    return re.sub(r"\bcard\b", "cart", normalized)

# Ordered so more specific / higher-priority intents are checked first.
INTENT_PATTERNS: list[tuple[IntentType, list[str]]] = [
    (IntentType.RESTOCK_INVENTORY, [r"\binventory\b.*\b(add|daal do|dalo|kar do|karo)\b", r"\b(add|daal do|dalo|kar do|karo)\b.*\binventory\b"]),
    (IntentType.CREATE_ORDER, [r"\border\b.*\b(lao|bhej|place|confirm|kar|karo|banao|bana|create|generate|shuru)\b", r"\bcheckout\b", r"\bbill\b.*\b(banao|bana|create|generate|shuru)\b", r"\b(banao|bana|create|generate)\b.*\bbill\b"]),
    (IntentType.REPEAT_ORDER, [r"\b(last|pichhla|pehla)\b.*\border\b.*\brepeat\b", r"\brepeat.*order\b"]),
    (IntentType.CANCEL_ORDER, [r"\border\b.*\bcancel\b", r"\bcancel\b.*\border\b"]),
    (IntentType.GST_REPORT, [r"\bgst\b"]),
    (IntentType.VIEW_CART, [r"\bcart\b.*\b(dikhao|dikha|dekho|dekhna|show|view)\b", r"\b(show|view)\b.*\bcart\b"]),
    (IntentType.UPDATE_QUANTITY, [r"\b(isko|ise|iska|isse)\b.*\bkar\b", r"\bupdate\b.*\bquantity\b", r"\bquantity\b.*\b(badhao|kam karo|set)\b"]),
    (IntentType.REMOVE_FROM_CART, [r"\bcart\b.*\b(hatao|remove|nikalo)\b", r"\b(hatao|remove|nikalo)\b.*\bcart\b", r"\b(hatao|remove|nikalo)\b"]),
    (IntentType.TOP_PRODUCTS, [r"\b(sabse zyada|top|best.?selling)\b"]),
    (IntentType.WEEKLY_SALES, [r"\b(hafte|week|weekly)\b.*\bsales\b|\bsales\b.*\b(hafte|week)\b"]),
    (IntentType.MONTHLY_SALES, [r"\b(mahine|month|monthly)\b.*\bsales\b|\bsales\b.*\b(mahine|month)\b"]),
    (IntentType.DAILY_SALES, [r"\b(aaj|today|daily)\b.*\bsales\b|\bsales\b.*\b(aaj|today)\b"]),
    (IntentType.GROWTH_INSIGHTS, [r"\b(business|sales)\b.*\b(analysis|analyse|analyze|insights)\b", r"\b(analysis|analyse|analyze)\b.*\b(business|sales)\b", r"\bbusiness\b"]),
    (IntentType.GROWTH_INSIGHTS, [r"\brevenue\b.*\b(badha|grow|increase)\b", r"\bgrowth\b"]),
    (IntentType.FORECAST_DEMAND, [r"\bstock\b.*\bmangwana\b", r"\bforecast\b", r"\bagle hafte\b.*\bstock\b"]),
    (IntentType.CHECK_STOCK, [r"\bstock\b.*\b(khatam|available|hai)\b", r"\bavailable hai\b"]),
    (IntentType.CHECK_PRICE, [r"\bkitne ka\b", r"\bprice\b", r"\bkeemat\b|\bkimat\b"]),
    (IntentType.ADD_TO_CART, [r"\badd\b", r"\bdaal do\b", r"\bdalo\b"]),
]

# quantity + optional unit + product, e.g. "2 kilo chawal", "4 kg aata"
ITEM_PATTERN = re.compile(
    r"\b(?P<qty>\d+(?:\.\d+)?|"
    + "|".join(HINDI_NUMERALS.keys())
    + r")\s*(?:(?P<unit>kilogram|kilo|kg|litre|liter|l|gram|g|piece|pcs|packet)\b\s*)?"
    r"(?P<product>[a-zA-Z]+)\b",
    re.IGNORECASE,
)

# Handles speech-recognition word order such as "flour add 10 kg inventory mein".
ITEM_AFTER_PRODUCT_PATTERN = re.compile(
    r"\b(?P<product>[a-zA-Z]+)\b(?:\s+\S+){0,4}?\s+"
    r"(?P<qty>\d+(?:\.\d+)?|" + "|".join(HINDI_NUMERALS.keys()) + r")\s*"
    r"(?P<unit>kilogram|kilo|kg|litre|liter|l|gram|g|piece|pcs|packet|packets)\b",
    re.IGNORECASE,
)
# Speech recognition often places the product before its unit: "10 maggi ke
# packets".  Extract this before the generic quantity-product form so it is
# not incorrectly assigned the default kilogram unit.
ITEM_WITH_TRAILING_UNIT_PATTERN = re.compile(
    r"\b(?P<qty>\d+(?:\.\d+)?|" + "|".join(HINDI_NUMERALS.keys()) + r")\s*"
    r"(?P<product>[a-zA-Z]+)\s*(?:ke|ki|ka)?\s*"
    r"(?P<unit>kilogram|kilo|kg|litre|liter|l|gram|g|piece|pcs|packet|packets)\b",
    re.IGNORECASE,
)
PRICE_PATTERN = re.compile(
    r"\b(?P<price>(?:\d+(?:\.\d+)?|"
    + "|".join(HINDI_NUMERALS.keys())
    + r")\s+sau|\d+(?:\.\d+)?|"
    + "|".join(HINDI_NUMERALS.keys()) + r")\s*(?:ke\s+)?price\b",
    re.IGNORECASE,
)
PRICE_PREFIX_PATTERN = re.compile(
    r"\bprice\s*(?P<price>\d+(?:\.\d+)?|(?:ek|do|teen|char|chaar|paanch|das)\s+sau|"
    + "|".join(HINDI_NUMERALS.keys()) + r")\b",
    re.IGNORECASE,
)


def _normalize_qty(raw: str) -> float:
    raw_lower = raw.lower()
    if raw_lower in HINDI_NUMERALS:
        return float(HINDI_NUMERALS[raw_lower])
    return float(raw)


def _extract_unit_price(text: str) -> float | None:
    match = PRICE_PATTERN.search(text) or PRICE_PREFIX_PATTERN.search(text)
    if not match:
        return None
    raw = match.group("price").lower().strip()
    if raw.endswith(" sau"):
        return _normalize_qty(raw.removesuffix(" sau")) * 100
    return _normalize_qty(raw)


def _extract_items(text: str) -> list[ItemMention]:
    items: list[ItemMention] = []
    for match in ITEM_WITH_TRAILING_UNIT_PATTERN.finditer(text):
        product_raw = match.group("product").lower()
        if product_raw not in PRODUCT_ALIASES:
            continue
        unit_raw = match.group("unit").lower()
        items.append(ItemMention(
            product=PRODUCT_ALIASES[product_raw],
            quantity=_normalize_qty(match.group("qty")),
            unit=UNIT_ALIASES[unit_raw],
        ))
    if items:
        return items
    for match in ITEM_PATTERN.finditer(text):
        product_raw = match.group("product").lower()
        if product_raw not in PRODUCT_ALIASES:
            continue  # skip incidental number+word matches that aren't products
        unit_raw = (match.group("unit") or "kg").lower()
        items.append(
            ItemMention(
                product=PRODUCT_ALIASES[product_raw],
                quantity=_normalize_qty(match.group("qty")),
                unit=UNIT_ALIASES.get(unit_raw, unit_raw),
            )
        )
    if items:
        return items
    for match in ITEM_AFTER_PRODUCT_PATTERN.finditer(text):
        product_raw = match.group("product").lower()
        if product_raw not in PRODUCT_ALIASES:
            continue
        unit_raw = match.group("unit").lower()
        items.append(ItemMention(
            product=PRODUCT_ALIASES[product_raw],
            quantity=_normalize_qty(match.group("qty")),
            unit=UNIT_ALIASES[unit_raw],
        ))
    return items


def _extract_named_products(text: str) -> list[ItemMention]:
    """Extract products without a quantity, for commands such as 'chawal hatao'."""
    return [
        ItemMention(product=canonical)
        for spoken, canonical in PRODUCT_ALIASES.items()
        if re.search(rf"\b{re.escape(spoken)}\b", text)
    ]


def _detect_reference_only_update(text: str) -> ItemMention | None:
    """Handles 'Isko 5 kilo kar do' — no product named, resolved later via session."""
    match = re.search(
        r"\b(?:isko|ise|iska|isse)\b\s*(?P<qty>\d+(?:\.\d+)?|"
        + "|".join(HINDI_NUMERALS.keys())
        + r")\s*"
        r"(?P<unit>kilo|kg|litre|liter|gram|piece)?",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    return ItemMention(
        product="",
        quantity=_normalize_qty(match.group("qty")),
        unit=UNIT_ALIASES.get((match.group("unit") or "kg").lower(), "kg"),
        is_reference=True,
    )


def parse(text: str) -> ParsedIntent:
    lowered = _normalize_text(text).strip()

    detected_intent = IntentType.UNKNOWN
    for intent_type, patterns in INTENT_PATTERNS:
        if any(re.search(p, lowered) for p in patterns):
            detected_intent = intent_type
            break

    items = _extract_items(lowered)
    unit_price = _extract_unit_price(lowered)
    if unit_price is not None:
        for item in items:
            item.unit_price = unit_price

    if detected_intent == IntentType.REMOVE_FROM_CART and not items:
        items = _extract_named_products(lowered)

    if detected_intent == IntentType.UPDATE_QUANTITY and not items:
        ref_item = _detect_reference_only_update(lowered)
        if ref_item:
            items = [ref_item]

    # Fallback: if we found item mentions but no verb matched, assume ADD_TO_CART
    if detected_intent == IntentType.UNKNOWN and items:
        detected_intent = IntentType.ADD_TO_CART

    if items and unit_price is not None:
        detected_intent = IntentType.RESTOCK_INVENTORY

    # A bare "cart" is a common short request to view its current contents.
    if detected_intent == IntentType.UNKNOWN and re.search(r"\bcart\b", lowered):
        detected_intent = IntentType.VIEW_CART

    confidence = 0.6 if detected_intent == IntentType.UNKNOWN else 0.85

    return ParsedIntent(
        intent=detected_intent, items=items, raw_text=text, confidence=confidence
    )
