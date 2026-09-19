"""Real configured PostgreSQL tests. All fixture records are rolled back."""
import unittest
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, patch
from sqlalchemy import select, func
from app.core.database import AsyncSessionLocal, engine
from app.core.dependencies import current_merchant
from app.domain.models import Customer, Order, OrderStatus, Payment
from app.services.payment_service import PaymentService
from app.services.analytics_service import AnalyticsService
from app.core.exceptions import DomainError


class PaymentDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_cash_udhar_online_and_reports(self):
        try:
            async with AsyncSessionLocal() as session:
                try:
                    merchant = await current_merchant(session)
                    service = PaymentService(session, merchant.id)
                    customer = Customer(merchant_id=merchant.id, name='Payment regression', phone=uuid4().hex[:18])
                    session.add(customer)
                    await session.flush()
                    async def bill():
                        order = Order(merchant_id=merchant.id, customer_id=customer.id, invoice_number=f'TEST-{uuid4().hex}', total_amount=Decimal('100'), gst_amount=Decimal('5'), status=OrderStatus.CONFIRMED)
                        session.add(order)
                        await session.flush()
                        return order
                    cash = await bill()
                    await service.record(cash.id, 'cash')
                    await service.record(cash.id, 'cash')
                    self.assertEqual(cash.status, OrderStatus.PAID)
                    self.assertEqual(await session.scalar(select(func.count(Payment.id)).where(Payment.order_id == cash.id)), 1)
                    credit = await bill()
                    await service.record(credit.id, 'udhar', customer.id)
                    await service.record(credit.id, 'udhar', customer.id)
                    self.assertEqual(await service.balance(customer.id), Decimal('100'))
                    self.assertEqual(credit.status, OrderStatus.CONFIRMED)
                    online = await bill()
                    with patch('app.services.payment_service.PaytmVerifier.check', AsyncMock(return_value={'verified': False, 'status':'PENDING'})):
                        self.assertFalse((await service.verify_online(online.id))['verified'])
                    self.assertEqual(online.status, OrderStatus.CONFIRMED)
                    with patch('app.services.payment_service.PaytmVerifier.check', AsyncMock(return_value={'verified':True,'status':'TXN_SUCCESS','transaction_id':uuid4().hex})):
                        self.assertTrue((await service.verify_online(online.id))['verified'])
                        self.assertTrue((await service.verify_online(online.id))['verified'])
                    self.assertEqual(online.status, OrderStatus.PAID)
                    report = await AnalyticsService(session, merchant.id).report('week')
                    self.assertGreaterEqual(report['order_count'], 3)
                    self.assertGreaterEqual(Decimal(report['outstanding_udhar']), Decimal('100'))
                    self.assertIn('summary', report)
                    credit.status = OrderStatus.CANCELLED
                    await session.flush()
                    self.assertEqual(await service.balance(customer.id), Decimal('0'))
                    with self.assertRaises(DomainError):
                        await service.record(credit.id, 'cash')
                finally:
                    await session.rollback()
        finally:
            await engine.dispose()
