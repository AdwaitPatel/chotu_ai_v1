import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.intent.catalog import CatalogResolver
from app.intent.engine import IntentEngine
from app.intent.groq_parser import GroqIntentParser
from app.intent.router import get_intent_service, router
from app.intent.rule_parser import RuleIntentParser
from app.intent.schemas import IntentType, ParsedIntent
from app.intent.service import IntentService


class RuleTests(unittest.TestCase):
    def test_voice_fallback_recognizes_customer_bills_and_top_seller(self):
        customer = RuleIntentParser().parse('अद्वैत के नाम का सारा बेल दिखाओ')
        self.assertEqual(customer.intent, IntentType.CUSTOMER_BILLS)
        self.assertEqual(customer.customer_name, 'अद्वैत')
        self.assertEqual(RuleIntentParser().parse('आज का सबसे ज़्यादा बिकने वाला सामान क्या है?').intent, IntentType.TOP_PRODUCTS)
        self.assertEqual(RuleIntentParser().parse('जो स्टॉक खत्म है उसको रेस्टॉक के लिए रिमाइंडर भेज दो').intent, IntentType.RESTOCK_REMINDER)

    def test_languages_and_word_order(self):
        for text, product, quantity, unit in [
            ('2 kilo chawal daal do', 'rice', 2, 'kg'),
            ('chawal 2 kilo add kar do', 'rice', 2, 'kg'),
            ('दो किलो चावल डाल दो', 'rice', 2, 'kg'),
            ('add two kg rice', 'rice', 2, 'kg'),
            ('फिफ्टी केजी आटा।', 'flour', 50, 'kg'),
            ('add rice', 'rice', None, None),
            ('add 2 rice', 'rice', 2, None),
        ]:
            with self.subTest(text=text):
                result = RuleIntentParser().parse(text)
                self.assertEqual(result.intent, IntentType.ADD_TO_CART)
                item = result.items[0]
                self.assertEqual((item.product, item.quantity, item.unit), (product, quantity, unit))

    def test_multiple_products(self):
        for text in ['2 kg rice and 3 litre milk', 'rice 2 kg and milk 3 litre']:
            result = RuleIntentParser().parse(text)
            self.assertEqual([(i.product, i.quantity, i.unit) for i in result.items],
                             [('rice', 2, 'kg'), ('milk', 3, 'litre')])

    def test_intents(self):
        for text, intent in [('cart dikhao', 'VIEW_CART'), ('order bana do', 'CREATE_ORDER'),
                             ('aaj ki sales dikhao', 'DAILY_SALES'), ('top products batao', 'TOP_PRODUCTS'),
                             ('stock available hai kya', 'CHECK_STOCK'), ('hello', 'UNKNOWN'),
                             ('remove rice', 'REMOVE_FROM_CART')]:
            self.assertEqual(RuleIntentParser().parse(text).intent.value, intent)

    def test_references(self):
        for reference in ['isko', 'ise', 'usko', 'wahi', 'उसको', 'वही']:
            result = RuleIntentParser().parse(f'{reference} 5 kilo kar do')
            self.assertEqual(result.intent, IntentType.UPDATE_QUANTITY)
            self.assertTrue(result.items[0].is_reference)
            self.assertIsNone(result.items[0].product)
            self.assertEqual(result.items[0].quantity, 5)

    def test_catalog(self):
        resolver = CatalogResolver(['Rice', 'Basmati Rice', 'Aashirvaad Atta', 'Fortune Oil', 'Maggi', 'Milk'])
        self.assertEqual(resolver.resolve('basmati chawal'), 'Basmati Rice')
        self.assertEqual(resolver.resolve('milkk'), 'Milk')
        self.assertEqual(resolver.resolve('unknown vegetable'), 'unknown vegetable')
        self.assertIsNone(resolver.resolve(None))
        self.assertEqual(CatalogResolver(['Rice', 'rice']).resolve('rice'), 'rice')


class ServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_irrelevant_speech_does_not_touch_session_or_workflows(self):
        from app.agents.router import AgentRouter
        intent = ParsedIntent(intent=IntentType.IRRELEVANT, raw_text='tell me a joke', confidence=0.99)
        service = IntentService(SimpleNamespace(parse=AsyncMock(return_value=intent)))
        memory = Mock()
        with patch('app.intent.engine.get_session_memory', return_value=memory):
            result = await IntentEngine(service).interpret(1, intent.raw_text)
        self.assertEqual(memory.mock_calls, [])
        with patch('app.agents.router.get_session_memory') as get_memory:
            reply = await AgentRouter(Mock()).route(1, result)
        get_memory.assert_not_called()
        self.assertEqual(reply.speech, 'Kuch aur kaam ho toh bataiye.')

    async def test_unknown_workflow_reply_still_reaches_draft(self):
        from app.agents.router import AgentRouter
        router = AgentRouter(Mock())
        router.order_agent = SimpleNamespace(continue_draft=AsyncMock())
        memory = SimpleNamespace(get=AsyncMock(return_value={'pending_order': {'stage': 'customer_name'}}))
        intent = ParsedIntent(intent=IntentType.UNKNOWN, raw_text='Rahul')
        with patch('app.agents.router.get_session_memory', return_value=memory):
            await router.route(1, intent)
        router.order_agent.continue_draft.assert_awaited_once_with(1, intent)

    async def test_llm_first_and_empty(self):
        provider = SimpleNamespace(parse=AsyncMock(return_value=ParsedIntent(
            intent=IntentType.VIEW_CART, raw_text='cart dikhao', confidence=0.99)))
        fallback = Mock()
        service = IntentService(provider, rule_parser=fallback)
        self.assertEqual((await service.parse('cart dikhao')).intent, IntentType.VIEW_CART)
        self.assertEqual((await service.parse('  ')).intent, IntentType.UNKNOWN)
        provider.parse.assert_awaited_once_with('cart dikhao')
        fallback.parse.assert_not_called()

    async def test_provider_request_and_response(self):
        def handler(request):
            payload = json.loads(request.content)
            self.assertEqual(payload['temperature'], 0)
            self.assertEqual(payload['response_format'], {'type': 'json_object'})
            self.assertEqual(payload['model'], 'llama-3.3-70b-versatile')
            output = {'intent': 'ADD_TO_CART', 'items': [{'product': 'rice', 'quantity': 2,
                       'unit': 'kg', 'is_reference': False}], 'confidence': 0.98}
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(output)}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            service = IntentService(GroqIntentParser(client, 'test'))
            result = await service.parse('chawal 2 kilo add kar do')
            self.assertEqual(result.confidence, 0.98)
            self.assertEqual(result.raw_text, 'chawal 2 kilo add kar do')

    async def test_failures_return_fallback(self):
        invalid = [
            'not json', '{}',
            json.dumps({'intent': 'HACK', 'items': [], 'confidence': 0.9}),
            json.dumps({'intent': 'ADD_TO_CART', 'items': [], 'confidence': 5}),
            json.dumps({'intent': 'ADD_TO_CART', 'items': [{'product': 'rice', 'quantity': -1}], 'confidence': 0.9}),
            json.dumps({'intent': 'ADD_TO_CART', 'items': [{'product': None}], 'confidence': 0.99}),
            json.dumps({'intent': 'UPDATE_QUANTITY', 'items': [{'product': 'rice', 'is_reference': True}], 'confidence': 0.99}),
        ]
        for content in invalid:
            with self.subTest(content=content):
                async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200,
                    json={'choices': [{'finish_reason': 'stop', 'message': {'content': content}}]}))) as client:
                    result = await IntentService(GroqIntentParser(client, 'test')).parse('add rice')
                    self.assertEqual(result.confidence, 0.65)
                    self.assertEqual(result.items[0].product, 'rice')
        for status in [429, 500, 401]:
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(status))) as client:
                self.assertEqual((await IntentService(GroqIntentParser(client, 'test')).parse('add rice')).confidence, 0.65)
        def timeout(request):
            raise httpx.ReadTimeout('timeout', request=request)
        async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
            self.assertEqual((await IntentService(GroqIntentParser(client, 'test')).parse('add rice')).confidence, 0.65)

    async def test_session_reference_resolution(self):
        memory = SimpleNamespace(get=AsyncMock(return_value={'last_product': 'rice'}),
                                 update=AsyncMock(), append_history=AsyncMock())
        with patch('app.intent.engine.get_session_memory', return_value=memory):
            result = await IntentEngine(IntentService()).interpret(1, 'usko 5 kg kar do')
        self.assertEqual(result.items[0].product, 'rice')
        self.assertTrue(result.items[0].is_reference)

    async def test_truncated_output(self):
        for finish, quantity in [('length', 2)]:
            output = {'intent': 'ADD_TO_CART', 'items': [{'product': 'rice', 'quantity': quantity,
                      'unit': 'kg', 'is_reference': False}], 'confidence': 0.98}
            async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200,
                json={'choices': [{'finish_reason': finish, 'message': {'content': json.dumps(output)}}]}))) as client:
                result = await IntentService(GroqIntentParser(client, 'test')).parse('add 2 kg rice')
                self.assertEqual(result.items[0].quantity, 2)
                self.assertEqual(result.confidence, 0.65)

    async def test_llm_translation_and_quantity_conversion_are_not_overridden(self):
        output = {'intent': 'ADD_TO_CART', 'items': [{'product': 'potato', 'quantity': 0.5,
                  'unit': 'kg', 'is_reference': False}], 'confidence': 0.98}
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200,
            json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(output)}}]}))) as client:
            fallback = Mock()
            result = await IntentService(GroqIntentParser(client, 'test'), rule_parser=fallback).parse('500 gram aloo add karo')
            self.assertEqual(result.items[0].product, 'potato')
            self.assertEqual(result.items[0].quantity, 0.5)
            fallback.parse.assert_not_called()

    async def test_llm_extracts_customer_bills_and_weekday_sales_slots(self):
        cases = [
            ({'intent': 'CUSTOMER_BILLS', 'items': [], 'confidence': .98, 'customer_name': 'Adwait', 'report_weekday': None},
             'Adwait ke saare bill dikhao', 'Adwait', None),
            ({'intent': 'DAILY_SALES', 'items': [], 'confidence': .98, 'customer_name': None, 'report_weekday': 0},
             'Monday ko kitni sales hui', None, 0),
        ]
        for output, text, customer_name, weekday in cases:
            with self.subTest(text=text):
                async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200,
                    json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(output)}}]}))) as client:
                    result = await IntentService(GroqIntentParser(client, 'test')).parse(text)
                self.assertEqual((result.customer_name, result.report_weekday), (customer_name, weekday))

    async def test_llm_extracts_top_products_and_restock_reminder(self):
        cases = [
            ({'intent': 'TOP_PRODUCTS', 'items': [], 'confidence': .98, 'customer_name': None, 'report_weekday': None}, 'aaj sabse zyada kya bika'),
            ({'intent': 'RESTOCK_REMINDER', 'items': [], 'confidence': .98, 'customer_name': None, 'report_weekday': None}, 'jo stock khatam hai seller ko restock reminder bhej do'),
        ]
        for output, text in cases:
            with self.subTest(text=text):
                async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200,
                    json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(output)}}]}))) as client:
                    result = await IntentService(GroqIntentParser(client, 'test')).parse(text)
                self.assertEqual(result.intent.value, output['intent'])

    async def test_service_resolves_catalog_after_provider(self):
        provider = SimpleNamespace(parse=AsyncMock(return_value=ParsedIntent(
            intent=IntentType.ADD_TO_CART, items=[{'product': 'basmati chawal', 'quantity': 2}],
            confidence=0.98, raw_text='add 2 basmati chawal')))
        result = await IntentService(provider, catalog_resolver=CatalogResolver(['Rice', 'Basmati Rice'])).parse('add 2 basmati chawal')
        self.assertEqual(result.items[0].product, 'Basmati Rice')


class EndpointTests(unittest.TestCase):
    def test_application_lifespan_wires_service(self):
        from app.main import app, settings
        with patch.object(settings, 'GROQ_API_KEY', None):
            with TestClient(app) as client:
                response = client.post('/api/intent/parse', json={'transcript': 'cart dikhao'})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['intent'], 'VIEW_CART')
        self.assertFalse(hasattr(app.state, 'intent_service'))

    def test_endpoint_contract(self):
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_intent_service] = lambda: IntentService()
        with TestClient(app) as client:
            response = client.post('/api/intent/parse', json={'transcript': 'add rice'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['items'][0]['quantity'], None)
            self.assertEqual(client.post('/api/intent/parse', json={'transcript': ''}).json()['intent'], 'UNKNOWN')
            self.assertEqual(client.post('/api/intent/parse', json={'transcript': 42}).status_code, 422)
            self.assertEqual(client.post('/api/intent/parse', json={'transcript': 'x' * 4001}).status_code, 422)
