"""Merchant sales reports using calendar periods in India Standard Time."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models import Order, OrderItem, OrderStatus, Payment, Product

IST = timezone(timedelta(hours=5, minutes=30))


def period_start(period: str, now: datetime) -> datetime:
    local = now.astimezone(IST)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == 'day':
        return midnight
    if period == 'week':
        return midnight - timedelta(days=midnight.weekday())
    if period == 'month':
        return midnight.replace(day=1)
    raise ValueError('Unsupported report period')


class AnalyticsService:
    def __init__(self, session: AsyncSession, merchant_id: int):
        self.session = session
        self.merchant_id = merchant_id

    async def report(self, period: str = 'week') -> dict:
        now = datetime.now(timezone.utc)
        start = period_start(period, now)
        filters = [Order.merchant_id == self.merchant_id, Order.status.in_([OrderStatus.CONFIRMED, OrderStatus.PAID]), Order.created_at >= start, Order.created_at <= now]
        count, revenue, gst, paid = (await self.session.execute(select(
            func.count(Order.id), func.coalesce(func.sum(Order.total_amount), 0),
            func.coalesce(func.sum(Order.gst_amount), 0),
            func.coalesce(func.sum(case((Order.status == OrderStatus.PAID, Order.total_amount), else_=0)), 0),
        ).where(*filters))).one()
        top = (await self.session.execute(select(Product.name, func.sum(OrderItem.quantity).label('quantity'), func.sum(OrderItem.price * OrderItem.quantity).label('revenue')).select_from(OrderItem).join(Order, Order.id == OrderItem.order_id).join(Product, Product.id == OrderItem.product_id).where(*filters, Product.merchant_id == self.merchant_id).group_by(Product.id, Product.name).order_by(func.sum(OrderItem.price * OrderItem.quantity).desc()).limit(5))).all()
        outstanding = await self.session.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).join(Order, Order.id == Payment.order_id).where(Payment.merchant_id == self.merchant_id, Payment.status == 'outstanding', Order.status != OrderStatus.CANCELLED))
        low_count = await self.session.scalar(select(func.count(Product.id)).where(Product.merchant_id == self.merchant_id, Product.is_deleted.is_(False), Product.stock <= Product.low_stock_threshold))
        average = (revenue / count).quantize(Decimal('.01')) if count else Decimal(0)
        label = {'day': 'Aaj', 'week': 'Is hafte', 'month': 'Is mahine'}[period]
        summary = f'{label} {count} bills, total sales ₹{revenue:.2f}, in bills mein paid amount ₹{paid:.2f}. Average bill ₹{average:.2f}. Sabhi customers ka baki udhar ₹{outstanding:.2f}.'
        insights = [f'GST ₹{gst:.2f}.', f'{low_count} products low stock mein hain.']
        if top:
            insights.append(f'Sabse zyada revenue {top[0].name} se: ₹{top[0].revenue:.2f}, GST ke bina.')
        recommendations = []
        if low_count:
            recommendations.append('Low-stock products ka stock check karke restock kijiye.')
        if outstanding:
            recommendations.append('Udhar accounts ka follow-up kijiye.')
        if not count:
            recommendations.append('Is period mein confirmed sales nahi hain; doosra period check kijiye.')
        return {'summary': summary, 'insights': insights, 'recommendations': recommendations,
                'period': period, 'timezone': 'Asia/Kolkata', 'from': start.isoformat(), 'to': now.isoformat(),
                'order_count': count, 'sales_total': str(revenue), 'gst_total': str(gst),
                'paid_bills_total': str(paid), 'average_bill': str(average), 'outstanding_udhar': str(outstanding),
                'top_products': [{'name': r.name, 'quantity': str(r.quantity), 'sales_excluding_gst': str(r.revenue)} for r in top]}

    async def growth_plan(self) -> dict:
        """Actionable, data-aware sales-growth plan for a merchant voice query."""
        report = await self.report('week')
        actions = self._growth_actions(report)
        return {**report, 'growth_actions': actions}

    @staticmethod
    def _growth_actions(report: dict) -> list[str]:
        actions: list[str] = []
        top_products = report.get('top_products', [])
        if top_products:
            top_name = top_products[0]['name']
            actions.append(
                f"{top_name} aapka top seller hai; ise counter ke paas rakhiye aur iske saath related item ka combo offer dijiye."
            )
        else:
            actions.append(
                "Pehle 5 fast-moving daily-use products ko entrance ya counter ke paas clearly display kijiye."
            )
        actions.extend([
            "Har bill par ek low-price add-on suggest kijiye, jaise snack, salt ya small daily-use pack; isse average bill badhega.",
            "WhatsApp ya nearby customers ko weekly offer bhejiye: combo pack, fixed discount ya minimum bill par free delivery.",
            "Repeat customers ke liye simple loyalty offer rakhiye: 5 purchases ke baad ek small discount ya free item.",
        ])
        if report.get('top_products'):
            actions.append("Top-selling items kabhi out of stock na hone dijiye; sales lost hone se bachengi.")
        if Decimal(str(report.get('outstanding_udhar', '0'))) > 0:
            actions.append("Purane udhar ka polite follow-up kijiye, taki cash flow se naya fast-moving stock mangwa saken.")
        return actions
