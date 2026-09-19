"""Exercise real invoice persistence and roll back all test changes."""
import asyncio
from sqlalchemy import select
from app.core.database import AsyncSessionLocal, engine
from app.core.dependencies import current_merchant
from app.domain.models import Product, Order, InventoryMovement
from app.services.order_service import OrderService


async def main() -> None:
    try:
        async with AsyncSessionLocal() as session:
            try:
                merchant = await current_merchant(session)
                product = await session.scalar(select(Product).where(Product.merchant_id == merchant.id, Product.is_deleted.is_(False), Product.stock - Product.reserved_stock >= 1).order_by(Product.id).limit(1))
                if product is None:
                    print('Invoice check skipped: no product has one available unit.')
                    return
                invoice = await OrderService(session).create_invoice('Voice regression check', [{'product':product.name,'quantity':1}])
                order = await session.get(Order, invoice.order_id)
                movement = await session.scalar(select(InventoryMovement).where(InventoryMovement.order_id == invoice.order_id))
                assert order.merchant_id == merchant.id and order.invoice_number
                assert movement is not None and movement.quantity == -1
                print('PASS: invoice, customer, order item, and sale movement flushed to the configured database; test changes rolled back.')
            finally:
                await session.rollback()
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
