"""Read models used by the merchant dashboard UI."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import current_merchant
from app.domain.models import Customer, Merchant, Order, OrderStatus, Payment, Product

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
IST = timezone(timedelta(hours=5, minutes=30))


def _start_of_today() -> datetime:
    now = datetime.now(timezone.utc).astimezone(IST)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


@router.get("")
async def dashboard(
    session: AsyncSession = Depends(get_db), merchant: Merchant = Depends(current_merchant)
) -> dict:
    """Return live, tenant-scoped operational data without UI placeholders."""
    today = _start_of_today()
    sales_filter = (
        Order.merchant_id == merchant.id,
        Order.status.in_([OrderStatus.CONFIRMED, OrderStatus.PAID]),
        Order.created_at >= today,
    )
    transaction_count, sales_total = (await session.execute(
        select(func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0)).where(*sales_filter)
    )).one()
    low_stock = list((await session.execute(
        select(Product).where(
            Product.merchant_id == merchant.id,
            Product.is_deleted.is_(False),
            Product.stock <= Product.low_stock_threshold,
        ).order_by(Product.stock.asc()).limit(6)
    )).scalars())
    recent = (await session.execute(
        select(Order, Customer.name, Payment.method, Payment.status)
        .join(Customer, Customer.id == Order.customer_id)
        .outerjoin(Payment, Payment.order_id == Order.id)
        .where(Order.merchant_id == merchant.id, Order.status != OrderStatus.CANCELLED)
        .order_by(Order.created_at.desc()).limit(10)
    )).all()
    sales = Decimal(sales_total)
    count = int(transaction_count)
    return {
        "merchant": {"id": merchant.id, "name": merchant.business_name, "created_at": merchant.created_at},
        "metrics": {
            "today_collections": str(sales),
            "transaction_count": count,
            "average_ticket": str((sales / count).quantize(Decimal(".01")) if count else Decimal("0")),
            "low_stock_count": len(low_stock),
        },
        "low_stock": [{"id": p.id, "name": p.name, "stock": str(p.stock), "unit": p.unit} for p in low_stock],
        "recent_transactions": [
            {
                "id": order.id, "invoice_number": order.invoice_number, "payer": name,
                "method": method or "Pending", "payment_status": payment_status or order.status.value,
                "amount": str(order.total_amount), "created_at": order.created_at,
            }
            for order, name, method, payment_status in recent
        ],
    }
