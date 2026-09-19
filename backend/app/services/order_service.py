"""Order persistence and invoice calculations for the conversational bill flow."""
from dataclasses import dataclass
from uuid import uuid4
from decimal import Decimal
from app.core.dependencies import current_merchant

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Customer, Order, OrderItem, Product, InventoryMovement, MovementType, OrderStatus
from app.repositories.product_repository import ProductRepository


class OrderProductNotFoundError(Exception):
    pass


class OrderInsufficientStockError(Exception):
    pass


@dataclass
class InvoiceLine:
    product: str
    quantity: float
    unit: str
    price: float
    line_total: float
    gst_percent: float


@dataclass
class Invoice:
    order_id: int
    customer_name: str
    lines: list[InvoiceLine]
    subtotal: float
    gst_amount: float
    total_amount: float


class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.products = ProductRepository(session)

    async def create_invoice(self, customer_name: str, draft_items: list[dict]) -> Invoice:
        merchant = await current_merchant(self.session)
        if not draft_items:
            raise OrderInsufficientStockError("Bill mein koi item nahi hai.")
        quantities: dict[int, Decimal] = {}
        for item in draft_items:
            product = await self.session.scalar(select(Product).where(Product.merchant_id == merchant.id, Product.is_deleted.is_(False), Product.name.ilike(f"%{item['product']}%")).order_by(Product.id).limit(1))
            if product is None:
                raise OrderProductNotFoundError(item["product"])
            quantity = Decimal(str(item["quantity"]))
            if not quantity.is_finite() or quantity <= 0:
                raise OrderInsufficientStockError("Quantity zero se zyada honi chahiye.")
            quantities[product.id] = quantities.get(product.id, Decimal(0)) + quantity
        products = (await self.session.scalars(select(Product).where(Product.merchant_id == merchant.id, Product.id.in_(quantities), Product.is_deleted.is_(False)).order_by(Product.id).with_for_update().execution_options(populate_existing=True))).all()
        if len(products) != len(quantities):
            raise OrderProductNotFoundError("Product is no longer available")
        resolved = [(product, quantities[product.id]) for product in products]
        for product, quantity in resolved:
            if product.stock - product.reserved_stock < quantity:
                raise OrderInsufficientStockError(
                    f"{product.name} sirf {float(product.stock):g} available hai."
                )
        customer = await self._get_or_create_customer(customer_name, merchant.id)
        subtotal = Decimal(0)
        gst_amount = Decimal(0)
        lines: list[InvoiceLine] = []
        for product, quantity in resolved:
            line_total = round(product.price * quantity, 2)
            line_gst = round(line_total * product.gst_percent / 100, 2)
            subtotal += line_total
            gst_amount += line_gst
            product.stock -= quantity
            lines.append(
                InvoiceLine(
                    product=product.name,
                    quantity=float(quantity),
                    unit=product.unit,
                    price=float(product.price),
                    line_total=float(line_total),
                    gst_percent=float(product.gst_percent),
                )
            )

        order = Order(
            merchant_id=merchant.id,
            invoice_number=f"INV-{uuid4().hex}",
            status=OrderStatus.CONFIRMED,
            customer_id=customer.id,
            total_amount=round(subtotal + gst_amount, 2),
            gst_amount=round(gst_amount, 2),
        )
        self.session.add(order)
        await self.session.flush()
        for product, quantity in resolved:
            self.session.add(OrderItem(order_id=order.id, product_id=product.id, quantity=quantity, price=float(product.price)))
            self.session.add(InventoryMovement(merchant_id=merchant.id, product_id=product.id, order_id=order.id, movement_type=MovementType.SALE, quantity=-quantity))
        await self.session.flush()

        return Invoice(
            order_id=order.id,
            customer_name=customer.name,
            lines=lines,
            subtotal=float(round(subtotal, 2)),
            gst_amount=float(round(gst_amount, 2)),
            total_amount=float(round(subtotal + gst_amount, 2)),
        )

    async def _get_or_create_customer(self, name: str, merchant_id: int) -> Customer:
        result = await self.session.execute(select(Customer).where(Customer.name == name, Customer.merchant_id == merchant_id))
        customer = result.scalars().first()
        if customer:
            return customer
        customer = Customer(merchant_id=merchant_id, name=name, phone=f"bill-{uuid4().hex[:14]}")
        self.session.add(customer)
        await self.session.flush()
        return customer
