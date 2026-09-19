"""
Structured contracts the Intent Engine produces, regardless of which
backend (rule-based, Gemini, OpenAI) parsed the utterance.
"""
import enum

from pydantic import BaseModel, Field


class IntentType(str, enum.Enum):
    ADD_TO_CART = "ADD_TO_CART"
    REMOVE_FROM_CART = "REMOVE_FROM_CART"
    UPDATE_QUANTITY = "UPDATE_QUANTITY"
    VIEW_CART = "VIEW_CART"
    CREATE_ORDER = "CREATE_ORDER"
    REPEAT_ORDER = "REPEAT_ORDER"
    CANCEL_ORDER = "CANCEL_ORDER"
    CHECK_PRICE = "CHECK_PRICE"
    CHECK_STOCK = "CHECK_STOCK"
    DAILY_SALES = "DAILY_SALES"
    WEEKLY_SALES = "WEEKLY_SALES"
    MONTHLY_SALES = "MONTHLY_SALES"
    TOP_PRODUCTS = "TOP_PRODUCTS"
    GST_REPORT = "GST_REPORT"
    GROWTH_INSIGHTS = "GROWTH_INSIGHTS"
    FORECAST_DEMAND = "FORECAST_DEMAND"
    RESTOCK_INVENTORY = "RESTOCK_INVENTORY"
    UNKNOWN = "UNKNOWN"


class ItemMention(BaseModel):
    product: str
    quantity: float | None = None
    unit: str | None = None
    unit_price: float | None = Field(default=None, gt=0)
    # True when the merchant referred to the item pronomially
    # ("isko", "ise", "iska") rather than by name — resolved via session memory.
    is_reference: bool = False


class ParsedIntent(BaseModel):
    intent: IntentType
    items: list[ItemMention] = Field(default_factory=list)
    raw_text: str
    confidence: float = 1.0
