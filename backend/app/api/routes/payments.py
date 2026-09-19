from typing import Literal
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import current_merchant
from app.core.exceptions import DomainError
from app.domain.models import Merchant
from app.services.payment_service import PaymentService
from app.services.analytics_service import AnalyticsService

router = APIRouter(prefix='/api', tags=['payments-and-analytics'])


class PaymentRequest(BaseModel):
    method: Literal['cash', 'online', 'udhar']
    customer_id: int | None = None
    cash_received: bool = False


@router.post('/orders/{order_id}/payment')
async def record_payment(order_id: int, payload: PaymentRequest, session: AsyncSession = Depends(get_db), merchant: Merchant = Depends(current_merchant)) -> dict:
    if payload.method == 'cash' and not payload.cash_received:
        raise DomainError('Confirm cash_received before recording cash payment.')
    payment = await PaymentService(session, merchant.id).record(order_id, payload.method, payload.customer_id)
    await session.commit()
    return {'order_id': order_id, 'method': payment.method, 'status': payment.status, 'amount': str(payment.amount), 'customer_id': payment.customer_id}


@router.post('/orders/{order_id}/payment/verify')
async def verify_payment(order_id: int, session: AsyncSession = Depends(get_db), merchant: Merchant = Depends(current_merchant)) -> dict:
    result = await PaymentService(session, merchant.id).verify_online(order_id)
    await session.commit()
    return result


@router.get('/customers/{customer_id}/credit')
async def credit_balance(customer_id: int, session: AsyncSession = Depends(get_db), merchant: Merchant = Depends(current_merchant)) -> dict:
    from app.services.commerce_service import CommerceService
    await CommerceService(session, merchant.id).customer(customer_id)
    return {'customer_id': customer_id, 'outstanding': str(await PaymentService(session, merchant.id).balance(customer_id))}


@router.get('/analytics')
async def analytics(period: Literal['day', 'week', 'month'] = 'week', session: AsyncSession = Depends(get_db), merchant: Merchant = Depends(current_merchant)) -> dict:
    return await AnalyticsService(session, merchant.id).report(period)
