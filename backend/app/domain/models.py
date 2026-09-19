"""Tenant-owned SQLAlchemy models for GrowthOS."""
import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

class CartStatus(str, enum.Enum): ACTIVE="active"; CHECKED_OUT="checked_out"; ABANDONED="abandoned"
class OrderStatus(str, enum.Enum):
    DRAFT="draft"; CONFIRMED="confirmed"; PAID="paid"; CANCELLED="cancelled"
    PENDING="draft"; DELIVERED="paid"  # compatibility aliases
class MovementType(str, enum.Enum): SALE="sale"; RESTOCK="restock"; ADJUSTMENT="adjustment"; CANCELLATION="cancellation"

class Merchant(Base):
    __tablename__="merchants"
    id: Mapped[int]=mapped_column(primary_key=True)
    business_name: Mapped[str]=mapped_column(String(255))
    email: Mapped[str]=mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str]=mapped_column(String(255))
    gstin: Mapped[str|None]=mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), server_default=func.now())
    products: Mapped[list["Product"]]=relationship(back_populates="merchant")


class Payment(Base):
    """One full-bill settlement per order. Udhar remains outstanding."""
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("order_id", name="uq_payments_order"), UniqueConstraint("provider", "transaction_id", name="uq_payments_transaction"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    merchant_id: Mapped[int] = mapped_column(ForeignKey("merchants.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"))
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    method: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    transaction_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Product(Base):
    __tablename__="products"
    __table_args__=(UniqueConstraint("merchant_id","sku",name="uq_products_merchant_sku"),UniqueConstraint("merchant_id","barcode",name="uq_products_merchant_barcode"),CheckConstraint("stock >= 0",name="ck_products_stock_nonnegative"),Index("ix_products_merchant_name","merchant_id","name"))
    id: Mapped[int]=mapped_column(primary_key=True); merchant_id: Mapped[int]=mapped_column(ForeignKey("merchants.id",ondelete="CASCADE"),index=True)
    name: Mapped[str]=mapped_column(String(255),index=True); sku: Mapped[str]=mapped_column(String(100)); barcode: Mapped[str|None]=mapped_column(String(100),nullable=True)
    category: Mapped[str]=mapped_column(String(100),default="General",index=True); price: Mapped[Decimal]=mapped_column(Numeric(10,2)); stock: Mapped[Decimal]=mapped_column(Numeric(10,3),default=0); reserved_stock: Mapped[Decimal]=mapped_column(Numeric(10,3),default=0); low_stock_threshold: Mapped[Decimal]=mapped_column(Numeric(10,3),default=5)
    unit: Mapped[str]=mapped_column(String(20),default="piece"); gst_percent: Mapped[Decimal]=mapped_column(Numeric(5,2),default=0); is_deleted: Mapped[bool]=mapped_column(Boolean,default=False,index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now()); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now(),onupdate=func.now())
    merchant: Mapped[Merchant]=relationship(back_populates="products"); cart_items: Mapped[list["CartItem"]]=relationship(back_populates="product"); order_items: Mapped[list["OrderItem"]]=relationship(back_populates="product"); movements: Mapped[list["InventoryMovement"]]=relationship(back_populates="product")

class Customer(Base):
    __tablename__="customers"; __table_args__=(UniqueConstraint("merchant_id","phone",name="uq_customers_merchant_phone"),Index("ix_customers_merchant_phone","merchant_id","phone"))
    id: Mapped[int]=mapped_column(primary_key=True); merchant_id: Mapped[int]=mapped_column(ForeignKey("merchants.id",ondelete="CASCADE"),index=True); name: Mapped[str]=mapped_column(String(255),index=True); phone: Mapped[str]=mapped_column(String(20)); email: Mapped[str|None]=mapped_column(String(320),nullable=True); address: Mapped[str|None]=mapped_column(String(500),nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    carts: Mapped[list["Cart"]]=relationship(back_populates="customer"); orders: Mapped[list["Order"]]=relationship(back_populates="customer")

class Cart(Base):
    __tablename__="carts"
    id: Mapped[int]=mapped_column(primary_key=True); merchant_id: Mapped[int]=mapped_column(ForeignKey("merchants.id",ondelete="CASCADE"),index=True); customer_id: Mapped[int]=mapped_column(ForeignKey("customers.id",ondelete="CASCADE")); status: Mapped[CartStatus]=mapped_column(Enum(CartStatus,native_enum=False),default=CartStatus.ACTIVE); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    customer: Mapped[Customer]=relationship(back_populates="carts"); items: Mapped[list["CartItem"]]=relationship(back_populates="cart",cascade="all, delete-orphan")
class CartItem(Base):
    __tablename__="cart_items"; __table_args__=(UniqueConstraint("cart_id","product_id",name="uq_cart_items_cart_product"),)
    id: Mapped[int]=mapped_column(primary_key=True); cart_id: Mapped[int]=mapped_column(ForeignKey("carts.id",ondelete="CASCADE")); product_id: Mapped[int]=mapped_column(ForeignKey("products.id")); quantity: Mapped[Decimal]=mapped_column(Numeric(10,3)); price: Mapped[Decimal]=mapped_column(Numeric(10,2)); reservation_expires_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    cart: Mapped[Cart]=relationship(back_populates="items"); product: Mapped[Product]=relationship(back_populates="cart_items")

class Order(Base):
    __tablename__="orders"; __table_args__=(UniqueConstraint("merchant_id","invoice_number",name="uq_orders_merchant_invoice"),Index("ix_orders_merchant_created_status","merchant_id","created_at","status"))
    id: Mapped[int]=mapped_column(primary_key=True); merchant_id: Mapped[int]=mapped_column(ForeignKey("merchants.id",ondelete="CASCADE"),index=True); customer_id: Mapped[int]=mapped_column(ForeignKey("customers.id"),index=True); invoice_number: Mapped[str]=mapped_column(String(64)); total_amount: Mapped[Decimal]=mapped_column(Numeric(12,2)); gst_amount: Mapped[Decimal]=mapped_column(Numeric(12,2),default=0); status: Mapped[OrderStatus]=mapped_column(Enum(OrderStatus,native_enum=False),default=OrderStatus.DRAFT); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    customer: Mapped[Customer]=relationship(back_populates="orders"); items: Mapped[list["OrderItem"]]=relationship(back_populates="order",cascade="all, delete-orphan")
class OrderItem(Base):
    __tablename__="order_items"
    id: Mapped[int]=mapped_column(primary_key=True); order_id: Mapped[int]=mapped_column(ForeignKey("orders.id",ondelete="CASCADE")); product_id: Mapped[int]=mapped_column(ForeignKey("products.id")); quantity: Mapped[Decimal]=mapped_column(Numeric(10,3)); price: Mapped[Decimal]=mapped_column(Numeric(10,2))
    order: Mapped[Order]=relationship(back_populates="items"); product: Mapped[Product]=relationship(back_populates="order_items")
class InventoryMovement(Base):
    __tablename__="inventory_movements"
    id: Mapped[int]=mapped_column(primary_key=True); merchant_id: Mapped[int]=mapped_column(ForeignKey("merchants.id",ondelete="CASCADE"),index=True); product_id: Mapped[int]=mapped_column(ForeignKey("products.id"),index=True); order_id: Mapped[int|None]=mapped_column(ForeignKey("orders.id"),nullable=True); movement_type: Mapped[MovementType]=mapped_column(Enum(MovementType,native_enum=False)); quantity: Mapped[Decimal]=mapped_column(Numeric(10,3)); note: Mapped[str|None]=mapped_column(String(255),nullable=True); created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),server_default=func.now())
    product: Mapped[Product]=relationship(back_populates="movements")
