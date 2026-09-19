"""Transactional tenant-scoped catalog, cart, and order operations."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.config import get_settings
from app.core.exceptions import DomainError, NotFoundError, OutOfStockError
from app.domain.models import Cart, CartItem, CartStatus, Customer, InventoryMovement, MovementType, Order, OrderItem, OrderStatus, Product

class InvalidTransitionError(DomainError):
    code="INVALID_ORDER_TRANSITION"

class CommerceService:
    def __init__(self, session:AsyncSession, merchant_id:int): self.session=session; self.merchant_id=merchant_id
    async def product(self, product_id:int, lock:bool=False)->Product:
        query=select(Product).where(Product.id==product_id,Product.merchant_id==self.merchant_id,Product.is_deleted.is_(False))
        if lock: query=query.with_for_update()
        item=(await self.session.execute(query)).scalar_one_or_none()
        if not item: raise NotFoundError("Product not found")
        return item
    async def list_products(self,page:int,size:int,search:str|None,category:str|None,stock:str|None,sort:str)->tuple[list[Product],int]:
        query=select(Product).where(Product.merchant_id==self.merchant_id,Product.is_deleted.is_(False))
        if search: query=query.where((Product.name.ilike(f"%{search}%"))|(Product.sku.ilike(f"%{search}%"))|(Product.barcode.ilike(f"%{search}%")))
        if category: query=query.where(Product.category==category)
        if stock=="low": query=query.where(Product.stock<=Product.low_stock_threshold)
        elif stock=="in_stock": query=query.where(Product.stock>0)
        columns={"name":Product.name,"price":Product.price,"stock":Product.stock,"created_at":Product.created_at}
        descending=sort.startswith("-"); field=columns.get(sort.lstrip("-"),Product.name)
        query=query.order_by(field.desc() if descending else field.asc())
        total=(await self.session.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
        items=list((await self.session.execute(query.offset((page-1)*size).limit(size))).scalars())
        return items,total
    async def create_product(self, data:dict)->Product:
        product=Product(merchant_id=self.merchant_id,name=data["name"],sku=data["sku"],barcode=data.get("barcode"),price=data["price"],stock=data["stock_quantity"],gst_percent=data["gst_rate"],category=data["category"],unit=data["unit"],low_stock_threshold=data["low_stock_threshold"])
        self.session.add(product); await self.session.flush()
        if product.stock: self.session.add(InventoryMovement(merchant_id=self.merchant_id,product_id=product.id,movement_type=MovementType.RESTOCK,quantity=product.stock,note="Opening stock"))
        return product
    async def adjust_stock(self, product_id:int, quantity:Decimal, direction:str, note:str|None)->Product:
        product=await self.product(product_id,lock=True); signed=quantity if direction=="increase" else -quantity
        if product.stock+signed<0: raise OutOfStockError("Stock cannot be reduced below zero")
        product.stock+=signed
        self.session.add(InventoryMovement(merchant_id=self.merchant_id,product_id=product.id,movement_type=MovementType.RESTOCK if signed>0 else MovementType.ADJUSTMENT,quantity=signed,note=note))
        return product
    async def customer(self, customer_id:int)->Customer:
        item=(await self.session.execute(select(Customer).where(Customer.id==customer_id,Customer.merchant_id==self.merchant_id))).scalar_one_or_none()
        if not item: raise NotFoundError("Customer not found")
        return item
    async def active_cart(self, customer_id:int)->Cart:
        await self.customer(customer_id)
        query=select(Cart).options(selectinload(Cart.items).selectinload(CartItem.product)).where(Cart.customer_id==customer_id,Cart.merchant_id==self.merchant_id,Cart.status==CartStatus.ACTIVE)
        cart=(await self.session.execute(query)).scalars().first()
        if cart: return cart
        cart=Cart(merchant_id=self.merchant_id,customer_id=customer_id,items=[]); self.session.add(cart); await self.session.flush(); return cart
    async def checkout(self, customer_id:int)->Order:
        cart=await self.active_cart(customer_id)
        if not cart.items: raise DomainError("Cannot checkout an empty cart")
        product_ids=[item.product_id for item in cart.items]
        products={p.id:p for p in (await self.session.execute(select(Product).where(Product.id.in_(product_ids),Product.merchant_id==self.merchant_id,Product.is_deleted.is_(False)).with_for_update())).scalars()}
        if len(products)!=len(product_ids): raise NotFoundError("A cart product no longer exists")
        subtotal=Decimal("0"); gst=Decimal("0")
        for item in cart.items:
            product=products[item.product_id]
            if product.stock<item.quantity: raise OutOfStockError(f"Insufficient stock for {product.name}")
            subtotal+=item.price*item.quantity; gst+=(item.price*item.quantity*product.gst_percent/100)
        invoice=f"INV-{self.merchant_id}-{datetime.now(timezone.utc):%Y%m%d%H%M%S%f}"
        order=Order(merchant_id=self.merchant_id,customer_id=customer_id,invoice_number=invoice,total_amount=(subtotal+gst).quantize(Decimal(".01")),gst_amount=gst.quantize(Decimal(".01")),status=OrderStatus.CONFIRMED)
        self.session.add(order); await self.session.flush()
        for item in cart.items:
            product=products[item.product_id]; product.stock-=item.quantity; product.reserved_stock=max(Decimal("0"),product.reserved_stock-item.quantity)
            self.session.add(OrderItem(order_id=order.id,product_id=product.id,quantity=item.quantity,price=item.price))
            self.session.add(InventoryMovement(merchant_id=self.merchant_id,product_id=product.id,order_id=order.id,movement_type=MovementType.SALE,quantity=-item.quantity,note=order.invoice_number))
            await self.session.delete(item)
        cart.status=CartStatus.CHECKED_OUT
        await self.session.flush(); return await self.order(order.id)
    async def set_cart_item(self, customer_id:int, product_id:int, quantity:Decimal)->Cart:
        """Reserve stock while a cart is active, under the product row lock."""
        cart=await self.active_cart(customer_id); product=await self.product(product_id,lock=True)
        existing=next((item for item in cart.items if item.product_id==product_id),None)
        previous=existing.quantity if existing else Decimal("0")
        available=product.stock-product.reserved_stock+previous
        if quantity>available: raise OutOfStockError(f"Insufficient available stock for {product.name}")
        product.reserved_stock+=quantity-previous
        expiry=datetime.now(timezone.utc)+timedelta(minutes=get_settings().CART_RESERVATION_MINUTES)
        if existing: existing.quantity=quantity; existing.price=product.price; existing.reservation_expires_at=expiry
        else:
            self.session.add(CartItem(cart_id=cart.id,product_id=product.id,quantity=quantity,price=product.price,reservation_expires_at=expiry))
        await self.session.flush(); return await self.active_cart(customer_id)
    async def cancel_cart(self, customer_id:int)->None:
        cart=await self.active_cart(customer_id)
        for item in list(cart.items):
            product=await self.product(item.product_id,lock=True); product.reserved_stock=max(Decimal("0"),product.reserved_stock-item.quantity); await self.session.delete(item)
        cart.status=CartStatus.ABANDONED
    async def order(self, order_id:int)->Order:
        query=select(Order).options(selectinload(Order.items).selectinload(OrderItem.product)).where(Order.id==order_id,Order.merchant_id==self.merchant_id)
        order=(await self.session.execute(query)).scalar_one_or_none()
        if not order: raise NotFoundError("Order not found")
        return order
    async def cancel_order(self, order_id:int)->Order:
        order=await self.order(order_id)
        if order.status==OrderStatus.CANCELLED: return order
        if order.status==OrderStatus.PAID: raise InvalidTransitionError("A paid order cannot be cancelled")
        products={p.id:p for p in (await self.session.execute(select(Product).where(Product.id.in_([i.product_id for i in order.items])).with_for_update())).scalars()}
        for item in order.items:
            products[item.product_id].stock+=item.quantity
            self.session.add(InventoryMovement(merchant_id=self.merchant_id,product_id=item.product_id,order_id=order.id,movement_type=MovementType.CANCELLATION,quantity=item.quantity,note="Order cancelled"))
        order.status=OrderStatus.CANCELLED; return order
