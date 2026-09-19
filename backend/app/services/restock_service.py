"""Create durable seller-restock requests from current inventory."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Product, RestockReminder


class RestockService:
    def __init__(self, session: AsyncSession, merchant_id: int):
        self.session = session
        self.merchant_id = merchant_id

    async def queue_out_of_stock_reminder(self) -> dict:
        products = list((await self.session.scalars(
            select(Product).where(
                Product.merchant_id == self.merchant_id,
                Product.is_deleted.is_(False),
                Product.stock <= 0,
            ).order_by(Product.name)
        )).all())
        if not products:
            return {"summary": "Abhi koi product stock khatam nahi hai; seller reminder nahi banaya.", "items": [], "status": "not_needed"}
        lines = [f"{product.name}: current stock {product.stock:g} {product.unit}" for product in products]
        message = "Restock request:\n" + "\n".join(lines)
        reminder = RestockReminder(merchant_id=self.merchant_id, message=message, item_count=len(products), status="queued")
        self.session.add(reminder)
        await self.session.flush()
        return {
            "summary": f"{len(products)} out-of-stock products ke liye seller restock reminder queue mein daal diya.",
            "reminder_id": reminder.id, "status": reminder.status, "message": message,
            "items": [{"product_id": p.id, "name": p.name, "stock": str(p.stock), "unit": p.unit} for p in products],
        }
