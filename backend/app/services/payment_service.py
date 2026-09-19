"""Full-bill cash, Paytm verification, and customer credit accounting."""
import json
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import DomainError, NotFoundError
from app.domain.models import Customer, Order, OrderStatus, Payment


class PaytmVerifier:
    async def check(self, order_id: str, amount: Decimal) -> dict[str, Any]:
        settings = get_settings()
        if not settings.PAYTM_MID or not settings.PAYTM_MERCHANT_KEY:
            return {'verified': False, 'status': 'not_configured', 'message': 'Paytm MID aur merchant key configure nahi hain. Payment pending hai.'}
        import PaytmChecksum
        body = {'mid': settings.PAYTM_MID, 'orderId': order_id}
        signature = PaytmChecksum.generateSignature(json.dumps(body), settings.PAYTM_MERCHANT_KEY)
        host = 'https://securegw.paytm.in' if settings.PAYTM_PRODUCTION else 'https://securegw-stage.paytm.in'
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(f'{host}/v3/order/status', json={'body': body, 'head': {'signature': signature}})
                response.raise_for_status()
            result = response.json()
            payload = result['body']
            valid_signature = PaytmChecksum.verifySignature(json.dumps(payload), settings.PAYTM_MERCHANT_KEY, result['head']['signature'])
            if not valid_signature:
                raise ValueError('Invalid signature')
            status = payload['resultInfo']['resultStatus']
            if status != 'TXN_SUCCESS':
                return {'verified': False, 'status': status, 'message': 'Paytm ne payment successful confirm nahi kiya. Payment pending hai; baad mein check boliye.'}
            if (payload.get('mid') != settings.PAYTM_MID or payload.get('orderId') != order_id
                    or Decimal(str(payload['txnAmount'])) != amount or not payload.get('txnId')
                    or Decimal(str(payload.get('refundAmt', '0'))) != 0
                    or payload.get('baseCurrency', 'INR') != 'INR'):
                raise ValueError('Transaction does not match bill')
            return {'verified': True, 'status': status, 'transaction_id': str(payload['txnId'])}
        except (httpx.HTTPError, ValueError, KeyError, TypeError, InvalidOperation):
            return {'verified': False, 'status': 'verification_error', 'message': 'Paytm verification nahi ho paya. Bill paid mark nahi hua; dobara check boliye.'}


class PaymentService:
    def __init__(self, session: AsyncSession, merchant_id: int):
        self.session = session
        self.merchant_id = merchant_id

    async def order(self, order_id: int) -> Order:
        order = await self.session.scalar(select(Order).where(Order.id == order_id, Order.merchant_id == self.merchant_id).with_for_update().execution_options(populate_existing=True))
        if order is None:
            raise NotFoundError('Bill nahi mila.')
        if order.status == OrderStatus.CANCELLED:
            raise DomainError('Cancelled bill ka payment nahi le sakte.')
        return order

    async def payment(self, order_id: int) -> Payment | None:
        return await self.session.scalar(select(Payment).where(Payment.order_id == order_id, Payment.merchant_id == self.merchant_id))

    async def record(self, order_id: int, method: str, customer_id: int | None = None) -> Payment:
        if method not in {'cash', 'online', 'udhar'}:
            raise DomainError('Cash, online ya udhar select kijiye.')
        order = await self.order(order_id)
        payment = await self.payment(order_id)
        if payment and payment.status in {'paid', 'outstanding'}:
            if payment.method != method or (method == 'udhar' and payment.customer_id != customer_id):
                raise DomainError('Is bill ka payment pehle record ho chuka hai.')
            return payment
        if order.status == OrderStatus.PAID:
            raise DomainError('Bill already paid hai.')
        if method == 'udhar':
            customer = await self.session.scalar(select(Customer).where(Customer.id == customer_id, Customer.merchant_id == self.merchant_id))
            if customer is None:
                raise NotFoundError('Udhar customer nahi mila.')
        if payment is None:
            payment = Payment(merchant_id=self.merchant_id, order_id=order.id, amount=order.total_amount)
            self.session.add(payment)
        payment.method = method
        payment.customer_id = customer_id if method == 'udhar' else order.customer_id
        payment.status = {'cash': 'paid', 'online': 'pending', 'udhar': 'outstanding'}[method]
        payment.provider = 'paytm' if method == 'online' else None
        if method == 'cash':
            order.status = OrderStatus.PAID
        await self.session.flush()
        return payment

    async def verify_online(self, order_id: int) -> dict[str, Any]:
        order = await self.order(order_id)
        payment = await self.payment(order_id)
        if payment and payment.status == 'paid' and payment.method == 'online':
            return {'verified': True, 'status': 'TXN_SUCCESS', 'transaction_id': payment.transaction_id}
        payment = await self.record(order_id, 'online')
        # Always query the bill's own merchant-generated reference, never a spoken UTR.
        result = await PaytmVerifier().check(order.invoice_number, order.total_amount)
        if result['verified']:
            reused = await self.session.scalar(select(Payment.id).where(Payment.provider == 'paytm', Payment.transaction_id == result['transaction_id'], Payment.order_id != order.id))
            if reused is not None:
                raise DomainError('Paytm transaction already doosre bill se linked hai.')
            payment.transaction_id = result['transaction_id']
            payment.status = 'paid'
            order.status = OrderStatus.PAID
            await self.session.flush()
        return {**result, 'paytm_order_id': order.invoice_number}

    async def find_customers(self, name: str, phone: str | None = None) -> list[Customer]:
        query = select(Customer).where(Customer.merchant_id == self.merchant_id)
        query = query.where(Customer.phone == phone) if phone else query.where(func.lower(Customer.name) == name.casefold())
        return list((await self.session.scalars(query.order_by(Customer.id).limit(10))).all())

    async def balance(self, customer_id: int) -> Decimal:
        return await self.session.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).join(Order, Payment.order_id == Order.id).where(Payment.merchant_id == self.merchant_id, Payment.customer_id == customer_id, Payment.status == 'outstanding', Order.status != OrderStatus.CANCELLED))
