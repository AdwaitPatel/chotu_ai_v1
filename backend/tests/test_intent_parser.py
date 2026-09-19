"""
Unit tests for the offline rule-based intent parser, covering every
example utterance from the project spec.
"""
import pytest

from app.intent.rule_based_parser import parse
from app.intent.schemas import IntentType


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("2 kilo chawal add karo", IntentType.ADD_TO_CART),
        ("4 kilo aata bhi add karo", IntentType.ADD_TO_CART),
        ("Order bhej do", IntentType.CREATE_ORDER),
        ("Iss hafte kitni sales hui?", IntentType.WEEKLY_SALES),
        ("Sabse zyada kya bika?", IntentType.TOP_PRODUCTS),
        ("GST report nikalo", IntentType.GST_REPORT),
        ("Revenue kaise badha sakte hain?", IntentType.GROWTH_INSIGHTS),
        ("Agle hafte kya stock mangwana chahiye?", IntentType.FORECAST_DEMAND),
        ("Cart dikhao", IntentType.VIEW_CART),
        ("Chini available hai?", IntentType.CHECK_STOCK),
    ],
)
def test_spec_examples_classify_correctly(text, expected_intent):
    result = parse(text)
    assert result.intent == expected_intent


def test_add_to_cart_extracts_product_and_quantity():
    result = parse("2 kilo chawal add karo")
    assert len(result.items) == 1
    assert result.items[0].product == "rice"
    assert result.items[0].quantity == 2
    assert result.items[0].unit == "kg"


def test_devanagari_transcript_is_normalized_for_offline_parsing():
    result = parse("२ किलो चावल डाल दो")
    assert result.intent == IntentType.ADD_TO_CART
    assert result.items[0].product == "rice"
    assert result.items[0].quantity == 2


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("cart dekho", IntentType.VIEW_CART),
        ("cart", IntentType.VIEW_CART),
        ("chawal hatao", IntentType.REMOVE_FROM_CART),
        ("isko paanch kilo kar do", IntentType.UPDATE_QUANTITY),
    ],
)
def test_common_cart_variants_classify_correctly(text, expected_intent):
    assert parse(text).intent == expected_intent


@pytest.mark.parametrize(
    "text,expected_intent",
    [
        ("कार्ड दिखा दो कार्ड", IntentType.VIEW_CART),
        ("फाइव केजी आटा", IntentType.ADD_TO_CART),
        ("पांच किलो आटा", IntentType.ADD_TO_CART),
    ],
)
def test_speech_recognition_variants_classify_correctly(text, expected_intent):
    assert parse(text).intent == expected_intent


def test_bill_creation_is_routed_to_order_flow_not_cart_addition():
    result = parse("शर्मा जी के नाम पे एक बिल बनाओ जिसमें पांच किलो आटा")
    assert result.intent == IntentType.CREATE_ORDER


@pytest.mark.parametrize("text", ["order banao", "ऑर्डर शुरू करो", "bill banao"])
def test_order_start_phrases(text):
    assert parse(text).intent == IntentType.CREATE_ORDER


@pytest.mark.parametrize("text", ["बिल बना एडमिट के नाम पर", "रुद्र के नाम पर बिल बना"])
def test_hindi_bill_start_word_order(text):
    assert parse(text).intent == IntentType.CREATE_ORDER


def test_pronoun_reference_flagged_for_session_resolution():
    result = parse("Isko 5 kilo kar do")
    assert result.intent == IntentType.UPDATE_QUANTITY
    assert result.items[0].is_reference is True
    assert result.items[0].product == ""
    assert result.items[0].quantity == 5
