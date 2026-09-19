"""Voice-driven stock increases for products already in the merchant catalog."""
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.cart_agent import AgentResponse
from app.core.dependencies import current_merchant
from app.domain.models import InventoryMovement, MovementType, Product
from app.intent.schemas import ParsedIntent


class InventoryAgent:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def restock(self, intent: ParsedIntent) -> AgentResponse:
        merchant = await current_merchant(self.session)
        added: list[str] = []
        missing: list[str] = []
        for item in intent.items:
            if not item.product or item.quantity is None:
                continue
            product = await self.session.scalar(
                select(Product).where(
                    Product.merchant_id == merchant.id,
                    Product.is_deleted.is_(False),
                    Product.name.ilike(f"%{item.product}%"),
                ).with_for_update()
            )
            if product is None:
                missing.append(item.product)
                continue
            quantity = Decimal(str(item.quantity))
            product.stock += quantity
            if item.unit_price is not None:
                product.price = Decimal(str(item.unit_price))
            self.session.add(InventoryMovement(
                merchant_id=merchant.id, product_id=product.id,
                movement_type=MovementType.RESTOCK, quantity=quantity,
                note="Voice inventory restock",
            ))
            price_note = f" at ₹{product.price:g}" if item.unit_price is not None else ""
            added.append(f"{quantity:g} {product.unit} {product.name}{price_note}")
        if added:
            speech = f"Inventory mein {', '.join(added)} add ho gaya."
        else:
            speech = "Inventory mein add karne ke liye product aur quantity boliye."
        if missing:
            speech += f" {', '.join(missing)} catalog mein nahi mila. Naya product banane ke liye selling price aur unit boliye."
        return AgentResponse(speech, {"restocked": added, "missing_products": missing}, bool(added), "RESTOCK_INVENTORY")
