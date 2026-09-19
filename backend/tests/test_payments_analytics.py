"""Unit coverage for spoken payments, reports, and provider validation."""
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.agents.payment_agent import PaymentAgent
from app.intent.rule_based_parser import parse
from app.intent.schemas import IntentType
from app.services.analytics_service import period_start
from app.services.payment_service import PaytmVerifier


class ReportParsingTests(unittest.TestCase):
    def test_weekly_and_analysis(self):
        for text in ['देन द सेल्स अबाउट फॉर दिस वीक।', 'इस हफ्ते की बिक्री बताओ', 'sales for this week']:
            self.assertEqual(parse(text).intent, IntentType.WEEKLY_SALES, text)
        self.assertEqual(parse('एक काम कर बिजनेस एनालिसिस कर सॉफ्टवेयर का।').intent, IntentType.GROWTH_INSIGHTS)
        self.assertEqual(parse('ईस्ट ऑफ टेक किस चेन के बारे में बताओ').intent, IntentType.UNKNOWN)

    def test_calendar_week_ist(self):
        start = period_start('week', datetime(2026, 9, 20, 19, 0, tzinfo=timezone.utc))
        self.assertEqual(start.isoformat(), '2026-09-21T00:00:00+05:30')


class PaymentConversationTests(unittest.IsolatedAsyncioTestCase):
    async def test_cash_requires_confirmation(self):
        memory = SimpleNamespace(update=AsyncMock())
        session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
        service = SimpleNamespace(record=AsyncMock(return_value=SimpleNamespace(amount=Decimal('50'))))
        with patch('app.agents.payment_agent.current_merchant', AsyncMock(return_value=SimpleNamespace(id=1))), patch('app.agents.payment_agent.get_session_memory', return_value=memory), patch('app.agents.payment_agent.PaymentService', return_value=service):
            state = {'order_id': 4, 'stage': 'method'}
            await PaymentAgent(session).handle(1, parse('कैश'), state)
            service.record.assert_not_awaited()
            self.assertEqual(state['stage'], 'cash_confirm')
            reply = await PaymentAgent(session).handle(1, parse('हाँ मिल गया'), state)
            service.record.assert_awaited_once_with(4, 'cash')
            self.assertEqual(reply.intent, 'PAYMENT_RECORDED')

    async def test_udhar_looks_up_customer_and_balance(self):
        memory = SimpleNamespace(update=AsyncMock())
        session = SimpleNamespace(commit=AsyncMock(), rollback=AsyncMock())
        service = SimpleNamespace(find_customers=AsyncMock(return_value=[SimpleNamespace(id=8, name='राहुल')]), balance=AsyncMock(return_value=Decimal('75')), record=AsyncMock())
        with patch('app.agents.payment_agent.current_merchant', AsyncMock(return_value=SimpleNamespace(id=1))), patch('app.agents.payment_agent.get_session_memory', return_value=memory), patch('app.agents.payment_agent.PaymentService', return_value=service):
            state = {'order_id': 4, 'stage': 'method'}
            await PaymentAgent(session).handle(1, parse('उधार'), state)
            self.assertEqual(state['stage'], 'credit_name')
            reply = await PaymentAgent(session).handle(1, parse('राहुल'), state)
            self.assertEqual(state['customer_id'], 8)
            self.assertIn('75.00', reply.speech)
            service.record.assert_not_awaited()

    async def test_online_missing_config_is_not_paid(self):
        with patch('app.services.payment_service.get_settings', return_value=SimpleNamespace(PAYTM_MID=None, PAYTM_MERCHANT_KEY=None)):
            result = await PaytmVerifier().check('INV-test', Decimal('10'))
        self.assertFalse(result['verified'])
        self.assertEqual(result['status'], 'not_configured')

    async def test_paytm_response_must_match_bill(self):
        payload = {'resultInfo': {'resultStatus': 'TXN_SUCCESS'}, 'mid': 'MID', 'orderId': 'INV-test', 'txnAmount': '10.00', 'txnId': 'TXN-1'}
        settings = SimpleNamespace(PAYTM_MID='MID', PAYTM_MERCHANT_KEY='secret', PAYTM_PRODUCTION=False)
        client = AsyncMock()
        client.post.return_value = SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'body': payload, 'head': {'signature': 'signed'}})
        checksum = SimpleNamespace(generateSignature=Mock(return_value='signed'), verifySignature=Mock(return_value=True))
        with patch.dict('sys.modules', {'PaytmChecksum': checksum}), patch('app.services.payment_service.get_settings', return_value=settings), patch('app.services.payment_service.httpx.AsyncClient') as factory:
            factory.return_value.__aenter__.return_value = client
            self.assertTrue((await PaytmVerifier().check('INV-test', Decimal('10')))['verified'])
            for key, value in [('txnAmount', '11.00'), ('mid', 'OTHER'), ('orderId', 'OTHER'), ('refundAmt', '1')]:
                original = payload.get(key)
                payload[key] = value
                self.assertFalse((await PaytmVerifier().check('INV-test', Decimal('10')))['verified'], key)
                if original is None:
                    del payload[key]
                else:
                    payload[key] = original
            checksum.verifySignature.return_value = False
            self.assertFalse((await PaytmVerifier().check('INV-test', Decimal('10')))['verified'])
