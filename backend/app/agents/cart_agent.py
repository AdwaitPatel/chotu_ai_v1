"""
Cart Agent — one of the specialized agents behind the Agent Router.
Responsibilities (per spec): Add Product, Remove Product, Update
Quantity, View Cart, Clear Cart.

Takes a ParsedIntent from the Intent Engine, calls CartService, and
returns a natural-language (Hinglish) response suitable for TTS.
"""
from dataclasses import dataclass

from app.intent.schemas import IntentType, ParsedIntent
from app.services.cart_service import (
    CartService,
    CartView,
    InsufficientStockError,
    ProductNotFoundError,
)


@dataclass
class AgentResponse:
    speech: str          # what Sarvam TTS should say back to the merchant
    data: dict            # structured payload for the frontend/dashboard
    success: bool = True
    intent: str | None = None


def _format_cart(cart: CartView) -> str:
    if not cart.items:
        return "Aapka cart abhi khali hai."
    lines = [
        f"{item.quantity:g} {item.unit} {item.product_name} - ₹{item.line_total:.0f}"
        for item in cart.items
    ]
    return "; ".join(lines) + f". Total: ₹{cart.subtotal:.0f}"


class CartAgent:
    """Handles ADD_TO_CART, REMOVE_FROM_CART, UPDATE_QUANTITY, VIEW_CART intents."""

    SUPPORTED_INTENTS = {
        IntentType.ADD_TO_CART,
        IntentType.REMOVE_FROM_CART,
        IntentType.UPDATE_QUANTITY,
        IntentType.VIEW_CART,
    }

    def __init__(self, cart_service: CartService):
        self.cart_service = cart_service

    async def handle(self, customer_id: int, intent: ParsedIntent) -> AgentResponse:
        try:
            if intent.intent == IntentType.ADD_TO_CART:
                return await self._handle_add(customer_id, intent)
            if intent.intent == IntentType.UPDATE_QUANTITY:
                return await self._handle_update(customer_id, intent)
            if intent.intent == IntentType.REMOVE_FROM_CART:
                return await self._handle_remove(customer_id, intent)
            if intent.intent == IntentType.VIEW_CART:
                cart = await self.cart_service.view_cart(customer_id)
                return AgentResponse(speech=_format_cart(cart), data=cart.__dict__)

            return AgentResponse(
                speech="Maaf kijiye, main yeh cart operation samajh nahi paaya.",
                data={},
                success=False,
            )
        except ProductNotFoundError as e:
            return AgentResponse(
                speech=f"'{e.product_query}' humare catalog mein nahi mila.",
                data={"error": "product_not_found", "query": e.product_query},
                success=False,
            )
        except InsufficientStockError as e:
            return AgentResponse(
                speech=(
                    f"{e.product_name} sirf {e.available:g} available hai, "
                    f"{e.requested:g} nahi de sakte."
                ),
                data={"error": "insufficient_stock"},
                success=False,
            )

    async def _handle_add(self, customer_id: int, intent: ParsedIntent) -> AgentResponse:
        if not intent.items:
            return AgentResponse(
                speech="Kaunsa product aur kitni quantity add karni hai?",
                data={},
                success=False,
            )
        cart = None
        added_summary = []
        for item in intent.items:
            cart = await self.cart_service.add_product(
                customer_id, item.product, item.quantity or 1
            )
            added_summary.append(f"{item.quantity:g} {item.unit} {item.product}")
        return AgentResponse(
            speech=f"{', '.join(added_summary)} cart mein add ho gaya. {_format_cart(cart)}",
            data=cart.__dict__,
        )

    async def _handle_update(self, customer_id: int, intent: ParsedIntent) -> AgentResponse:
        if not intent.items:
            return AgentResponse(
                speech="Kis product ki quantity update karni hai?", data={}, success=False
            )
        item = intent.items[0]
        if not item.product:
            return AgentResponse(
                speech="Samajh nahi paaya kis product ki baat ho rahi hai.",
                data={},
                success=False,
            )
        cart = await self.cart_service.update_quantity(
            customer_id, item.product, item.quantity or 1
        )
        return AgentResponse(
            speech=f"{item.product} ki quantity update ho gayi. {_format_cart(cart)}",
            data=cart.__dict__,
        )

    async def _handle_remove(self, customer_id: int, intent: ParsedIntent) -> AgentResponse:
        if not intent.items:
            return AgentResponse(
                speech="Kaunsa product hatana hai?", data={}, success=False
            )
        item = intent.items[0]
        cart = await self.cart_service.remove_product(customer_id, item.product)
        return AgentResponse(
            speech=f"{item.product} cart se hata diya. {_format_cart(cart)}",
            data=cart.__dict__,
        )
