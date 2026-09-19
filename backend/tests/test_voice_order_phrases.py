import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from app.agents.order_agent import OrderAgent
from app.intent.rule_based_parser import parse
from app.intent.schemas import IntentType, ParsedIntent
from app.services.order_service import OrderProductNotFoundError


class OrderPhraseTests(unittest.TestCase):
    def test_distinct_flours_and_quantities(self):
        parsed = parse('एक किलो चीनी, दो किलो दाल, एक किलो मैदा और पाँच किलो आटा।')
        self.assertEqual([(i.product, i.quantity) for i in parsed.items], [('sugar', 1), ('lentils', 2), ('maida', 1), ('flour', 5)])

    def test_milk_and_packets(self):
        for text, product, qty, unit in [('1 liter milk', 'milk', 1, 'litre'), ('बता, दो पैकेट मैगी के और कर देना।', 'maggi', 2, 'packet')]:
            items = parse(text).items
            self.assertEqual(len(items), 1)
            self.assertEqual((items[0].product, items[0].quantity, items[0].unit), (product, qty, unit))

    def test_merge_does_not_modify_spoken_items(self):
        additions = [{'product': 'flour', 'quantity': 1}, {'product': 'flour', 'quantity': 5}]
        self.assertEqual(OrderAgent._merge_items([], additions)[0]['quantity'], 6)
        self.assertEqual(additions[0]['quantity'], 1)


class ConfirmationFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_product_returns_to_item_stage(self):
        memory = SimpleNamespace(
            get=AsyncMock(return_value={
                'pending_order': {
                    'stage': 'confirm_customer', 'customer_name': 'Rahul',
                    'items': [{'product': 'maida', 'quantity': 10, 'unit': 'kg'}],
                }
            }),
            update=AsyncMock(),
        )
        service = SimpleNamespace(
            create_invoice=AsyncMock(side_effect=OrderProductNotFoundError('maida')),
            session=SimpleNamespace(commit=AsyncMock()),
        )
        with patch('app.agents.order_agent.get_session_memory', return_value=memory):
            reply = await OrderAgent(service).continue_draft(
                1, ParsedIntent(intent=IntentType.UNKNOWN, raw_text='haan')
            )
        self.assertEqual(reply.data['stage'], 'items')
        self.assertEqual(reply.data['items'], [])
        memory.update.assert_awaited_once_with(pending_order={'stage': 'items', 'items': []})

    async def test_same_name_and_reference_confirm_without_asking_again(self):
        for text in ['हाँ, इसी के नाम से बनाना है।', 'हाँ राहुल के नाम से बनाना है']:
            memory = SimpleNamespace(get=AsyncMock(return_value={'pending_order': {'stage': 'confirm_customer', 'customer_name': 'राहुल', 'items': [{'product': 'sugar', 'quantity': 1}]}}), update=AsyncMock())
            invoice = SimpleNamespace(order_id=1, customer_name='राहुल', subtotal=42, gst_amount=2.1, total_amount=44.1, lines=[])
            service = SimpleNamespace(create_invoice=AsyncMock(return_value=invoice), session=SimpleNamespace(commit=AsyncMock()))
            with patch('app.agents.order_agent.get_session_memory', return_value=memory):
                reply = await OrderAgent(service).continue_draft(1, parse(text))
            self.assertEqual(reply.intent, 'ORDER_CREATED')
            self.assertEqual(service.create_invoice.call_args.args[0], 'राहुल')
