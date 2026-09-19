from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.models import Cart, CartItem, CartStatus
from app.repositories.base import BaseRepository


class CartRepository(BaseRepository[Cart]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Cart)

    async def get_active_cart(self, customer_id: int) -> Cart | None:
        result = await self.session.execute(
            select(Cart)
            .options(selectinload(Cart.items).selectinload(CartItem.product))
            .where(Cart.customer_id == customer_id, Cart.status == CartStatus.ACTIVE)
            .order_by(Cart.created_at.desc())
        )
        return result.scalars().first()

    async def get_or_create_active_cart(self, customer_id: int) -> Cart:
        cart = await self.get_active_cart(customer_id)
        if cart:
            return cart
        cart = Cart(customer_id=customer_id, status=CartStatus.ACTIVE)
        return await self.add(cart)

    async def find_item(self, cart_id: int, product_id: int) -> CartItem | None:
        result = await self.session.execute(
            select(CartItem).where(
                CartItem.cart_id == cart_id, CartItem.product_id == product_id
            )
        )
        return result.scalars().first()

    async def add_item(self, item: CartItem) -> CartItem:
        self.session.add(item)
        await self.session.flush()
        return item

    async def remove_item(self, item: CartItem) -> None:
        await self.session.delete(item)
        await self.session.flush()

    async def clear_items(self, cart: Cart) -> None:
        for item in list(cart.items):
            await self.session.delete(item)
        await self.session.flush()
