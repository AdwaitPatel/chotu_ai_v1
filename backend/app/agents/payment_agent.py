"""Conversational settlement after a bill has been persisted."""
import re

from app.agents.cart_agent import AgentResponse
from app.agents.order_agent import OrderAgent
from app.core.dependencies import current_merchant
from app.core.exceptions import DomainError
from app.core.redis_client import get_session_memory
from app.domain.models import Customer
from app.intent.schemas import ParsedIntent
from app.services.payment_service import PaymentService
from sqlalchemy.ext.asyncio import AsyncSession


class PaymentAgent:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def handle(self, session_id: int, intent: ParsedIntent, state: dict) -> AgentResponse:
        merchant = await current_merchant(self.session)
        service = PaymentService(self.session, merchant.id)
        memory = get_session_memory(session_id)
        text = intent.raw_text.strip()
        lower = text.lower()
        order_id = state['order_id']

        async def prompt(message: str, **changes) -> AgentResponse:
            state.update(changes)
            await memory.update(pending_payment=state)
            return AgentResponse(message, dict(state), intent='PAYMENT_PENDING')

        async def finish(message: str, **data) -> AgentResponse:
            await self.session.commit()
            await memory.update(pending_payment=None, last_order_id=order_id)
            return AgentResponse(message, {'order_id': order_id, **data}, intent='PAYMENT_RECORDED')

        async def offer_upi_qr() -> AgentResponse:
            qr = await service.upi_payment_request(order_id)
            return await prompt(
                f"₹{qr['amount']} ka UPI QR ready hai. QR scan karke payment kar dijiye. "
                "Payment ho jaye to haan boliye; cash ya udhar karna ho to woh boliye.",
                stage='upi_qr',
                payment_method='upi',
                **qr,
            )

        try:
            if re.search(r'\b(later|skip)\b|बाद में', lower):
                await memory.update(pending_payment=None)
                return AgentResponse('Bill unpaid rahega. Payment baad mein dashboard se record kar sakte hain.', {'order_id': order_id}, intent='PAYMENT_PENDING')
            stage = state.get('stage', 'method')
            if stage == 'method':
                if re.search(r'\b(cash|nakad)\b|कैश|नकद', lower):
                    return await prompt('Cash mil gaya? Haan bolne par bill paid mark karunga.', stage='cash_confirm')
                if re.search(r'\b(online|upi|paytm)\b|ऑनलाइन|ऑन लाइन|यूपीआई|पेटीएम', lower):
                    await service.record(order_id, 'online')
                    await self.session.commit()
                    result = await service.verify_online(order_id)
                    if result['verified']:
                        return await finish('Paytm transaction verify ho gaya. Bill paid hai.', payment_method='online', **result)
                    if result.get('status') == 'not_configured':
                        return await offer_upi_qr()
                    await self.session.commit()
                    return await prompt(
                        result['message'],
                        stage='online_check',
                        **{key: value for key, value in result.items() if key != 'message'},
                    )
                if re.search(r'\b(udhar|credit|udhaar)\b|उधार', lower):
                    return await prompt('Udhar kiske naam likhna hai? Customer ka naam boliye; database mein check karunga.', stage='credit_name')
                return await prompt('Payment kaise hoga: cash, online ya udhar?')
            if stage == 'cash_confirm':
                if OrderAgent._is_negative(text):
                    return await prompt('Cash received record nahi kiya. Cash, online ya udhar?', stage='method')
                if OrderAgent._is_affirmative(text):
                    payment = await service.record(order_id, 'cash')
                    return await finish(f'₹{payment.amount:.2f} cash received. Bill paid hai.', payment_method='cash', amount=str(payment.amount))
                return await prompt('Cash mila hai to haan, nahi mila to nahi boliye.')
            if stage == 'online_check':
                if re.search(r'\b(cash|nakad)\b|कैश|नकद', lower):
                    return await prompt('Theek hai, cash mil gaya? Haan bolne par bill paid mark karunga.', stage='cash_confirm')
                if re.search(r'\b(udhar|credit|udhaar)\b|उधार', lower):
                    return await prompt('Theek hai, udhar kiske naam likhna hai? Customer ka naam boliye.', stage='credit_name')
                result = await service.verify_online(order_id)
                if result['verified']:
                    return await finish('Paytm payment verified. Bill paid hai.', payment_method='online', **result)
                if result.get('status') == 'not_configured':
                    return await offer_upi_qr()
                await self.session.commit()
                return await prompt(
                    result['message'],
                    **{key: value for key, value in result.items() if key != 'message'},
                )
            if stage == 'upi_qr':
                if re.search(r'\b(cash|nakad)\b|कैश|नकद', lower):
                    return await prompt('Theek hai, cash mil gaya? Haan bolne par bill paid mark karunga.', stage='cash_confirm')
                if re.search(r'\b(udhar|credit|udhaar)\b|उधार', lower):
                    return await prompt('Theek hai, udhar kiske naam likhna hai? Customer ka naam boliye.', stage='credit_name')
                if OrderAgent._is_affirmative(text) or re.search(r'\b(?:paid|payment\s+(?:ho\s+)?gaya|done)\b', lower):
                    payment = await service.confirm_upi_payment(order_id)
                    return await finish(
                        f'₹{payment.amount:.2f} UPI payment merchant confirmation par recorded hai. Bill paid hai.',
                        payment_method='upi',
                        amount=str(payment.amount),
                    )
                return await prompt(
                    'QR scan karke payment kar dijiye. Payment complete ho to haan boliye; cash ya udhar bhi choose kar sakte hain.',
                    stage='upi_qr',
                )
            if stage in {'credit_name', 'credit_phone'}:
                name = state.get('name', '')
                phone = None
                if stage == 'credit_name':
                    name = (OrderAgent._customer_name_from_self_intro(text) or OrderAgent._customer_name_from_named_bill_phrase(text) or OrderAgent._clean_customer_name(text))
                    matches = await service.find_customers(name)
                else:
                    phone = re.sub(r'\D', '', text.translate(str.maketrans('०१२३४५६७८९', '0123456789')))
                    if len(phone) != 10:
                        return await prompt('10 digit mobile number digits mein boliye ya type kijiye.')
                    matches = await service.find_customers(name, phone)
                if len(matches) == 1:
                    customer = matches[0]
                    balance = await service.balance(customer.id)
                    return await prompt(f'{customer.name} database mein mile. Pehle ka udhar ₹{balance:.2f}. Isi account mein bill add karun? Haan ya nahi.', stage='credit_confirm', customer_id=customer.id, name=customer.name)
                if stage == 'credit_name':
                    message = 'Is naam ke kai customer hain.' if matches else 'Is naam ka customer nahi mila.'
                    return await prompt(message + ' Mobile number boliye.', stage='credit_phone', name=name)
                return await prompt(f'Naya customer {name}, mobile {phone}. Account banakar udhar add karun? Haan ya nahi.', stage='credit_confirm', customer_id=None, name=name, phone=phone)
            if stage == 'credit_confirm':
                if OrderAgent._is_negative(text):
                    return await prompt('Sahi customer ka naam boliye.', stage='credit_name')
                if not OrderAgent._is_affirmative(text):
                    return await prompt('Udhar account confirm karne ke liye haan ya nahi boliye.')
                customer_id = state.get('customer_id')
                if customer_id is None:
                    matches = await service.find_customers(state['name'], state['phone'])
                    if matches:
                        return await prompt('Is mobile par account ab mil gaya hai. Naam dobara bolkar account check kijiye.', stage='credit_name')
                    customer = Customer(merchant_id=merchant.id, name=state['name'], phone=state['phone'])
                    self.session.add(customer)
                    await self.session.flush()
                    customer_id = customer.id
                payment = await service.record(order_id, 'udhar', customer_id)
                balance = await service.balance(customer_id)
                return await finish(f'{state["name"]} ke khate mein ₹{payment.amount:.2f} udhar add hua. Total baki ₹{balance:.2f}.', payment_method='udhar', customer_id=customer_id, balance=str(balance))
            return await prompt('Payment kaise hoga: cash, online ya udhar?', stage='method')
        except DomainError as exc:
            await self.session.rollback()
            return AgentResponse(exc.message, {'order_id': order_id, 'code': exc.code}, success=False, intent='PAYMENT_PENDING')
