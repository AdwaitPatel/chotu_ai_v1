"""
Cart Service — business logic for cart operations.
Sits between the repository layer (data access) and the Cart Agent
(conversational orchestration), keeping domain rules in one place.
"""
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Cart, CartItem
from app.repositories.cart_repository import CartRepository
from app.repositories.product_repository import ProductRepository


class ProductNotFoundError(Exception):
    def __init__(self, product_query: str):
        self.product_query = product_query
        super().__init__(f"Product not found: {product_query}")


class InsufficientStockError(Exception):
    def __init__(self, product_name: str, available: float, requested: float):
        self.product_name = product_name
        self.available = available
        self.requested = requested
        super().__init__(
            f"Insufficient stock for {product_name}: requested {requested}, "
            f"available {available}"
        )


@dataclass
class CartItemView:
    product_id: int
    product_name: str
    quantity: float
    unit: str
    unit_price: float
    line_total: float


@dataclass
class CartView:
    cart_id: int
    items: list[CartItemView]
    subtotal: float


class CartService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.carts = CartRepository(session)
        self.products = ProductRepository(session)

    async def add_product(
        self, customer_id: int, product_query: str, quantity: float
    ) -> CartView:
        product = await self.products.find_by_name(product_query)
        if product is None:
            raise ProductNotFoundError(product_query)
        if product.stock < quantity:
            raise InsufficientStockError(product.name, float(product.stock), quantity)

        cart = await self.carts.get_or_create_active_cart(customer_id)
        existing = await self.carts.find_item(cart.id, product.id)

        if existing:
            existing.quantity = float(existing.quantity) + quantity
        else:
            await self.carts.add_item(
                CartItem(
                    cart_id=cart.id,
                    product_id=product.id,
                    quantity=quantity,
                    price=float(product.price),
                )
            )

        return await self.view_cart(customer_id)

    async def update_quantity(
        self, customer_id: int, product_query: str, quantity: float
    ) -> CartView:
        cart = await self.carts.get_active_cart(customer_id)
        if not cart:
            raise ProductNotFoundError(product_query)

        product = await self.products.find_by_name(product_query)
        if product is None:
            raise ProductNotFoundError(product_query)

        item = await self.carts.find_item(cart.id, product.id)
        if item is None:
            # Merchant said "isko X kar do" for something not yet in cart —
            # treat it as an add.
            return await self.add_product(customer_id, product_query, quantity)

        if product.stock < quantity:
            raise InsufficientStockError(product.name, float(product.stock), quantity)

        item.quantity = quantity
        return await self.view_cart(customer_id)

    async def remove_product(self, customer_id: int, product_query: str) -> CartView:
        cart = await self.carts.get_active_cart(customer_id)
        if not cart:
            raise ProductNotFoundError(product_query)

        product = await self.products.find_by_name(product_query)
        if product is None:
            raise ProductNotFoundError(product_query)

        item = await self.carts.find_item(cart.id, product.id)
        if item:
            await self.carts.remove_item(item)

        return await self.view_cart(customer_id)

    async def clear_cart(self, customer_id: int) -> CartView:
        cart = await self.carts.get_active_cart(customer_id)
        if cart:
            await self.carts.clear_items(cart)
        return await self.view_cart(customer_id)

    async def view_cart(self, customer_id: int) -> CartView:
        cart: Cart | None = await self.carts.get_active_cart(customer_id)
        if not cart or not cart.items:
            cart_id = cart.id if cart else 0
            return CartView(cart_id=cart_id, items=[], subtotal=0.0)

        views = [
            CartItemView(
                product_id=item.product_id,
                product_name=item.product.name,
                quantity=float(item.quantity),
                unit=item.product.unit,
                unit_price=float(item.price),
                line_total=round(float(item.quantity) * float(item.price), 2),
            )
            for item in cart.items
        ]
        subtotal = round(sum(v.line_total for v in views), 2)
        return CartView(cart_id=cart.id, items=views, subtotal=subtotal)
