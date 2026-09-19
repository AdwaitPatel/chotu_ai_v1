import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from app.agents.order_agent import OrderAgent
from app.domain.models import Customer, Product, Order, InventoryMovement
from app.services.order_service import OrderService, OrderInsufficientStockError


class HindiConfirmationTests(unittest.TestCase):
    def test_user_phrases(self):
        for phrase in ('हाँ।', 'हाँ हाँ हाँ बना दे।', 'बिल्कुल बना दे।'):
            self.assertTrue(OrderAgent._is_affirmative(phrase), phrase)
        for phrase in ('नहीं भाई', 'अरे नहीं भाई।', 'नहीं बना दो', 'show bill'):
            self.assertFalse(OrderAgent._is_affirmative(phrase), phrase)
        self.assertEqual(OrderAgent._customer_name_from_self_intro('कस्टमर का नाम अद्वैत है भाई'), 'अद्वैत')
        self.assertEqual(OrderAgent._clean_customer_name('अद्वैत।'), 'अद्वैत')
        self.assertEqual(OrderAgent._customer_name_from_named_bill_phrase('नहीं भाई, एक काम कर, बिल ना अद्युत नाम से बना दियो।'), 'अद्युत')


class InvoiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_invoice_has_required_fields_and_movement(self):
        product = Product(id=7, merchant_id=3, name='Rice', price=Decimal('50'), stock=Decimal('10'), reserved_stock=Decimal('0'), gst_percent=Decimal('5'), unit='kg')
        session = SimpleNamespace(scalar=AsyncMock(return_value=product), scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [product])), execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: None))), add=Mock(), flush=AsyncMock())
        def assign_id(item):
            if isinstance(item, (Customer, Order)):
                item.id = 12
        session.add.side_effect = assign_id
        with patch('app.services.order_service.current_merchant', AsyncMock(return_value=SimpleNamespace(id=3))):
            invoice = await OrderService(session).create_invoice('अद्वैत', [{'product': 'rice', 'quantity': 2}])
        self.assertEqual(invoice.total_amount, 105)
        self.assertEqual(product.stock, 8)
        added = [call.args[0] for call in session.add.call_args_list]
        self.assertTrue(all(row.merchant_id == 3 for row in added if isinstance(row, (Customer, Order, InventoryMovement))))
        self.assertTrue(next(row for row in added if isinstance(row, Order)).invoice_number)
        self.assertEqual(next(row for row in added if isinstance(row, InventoryMovement)).quantity, -2)

    async def test_duplicate_lines_cannot_oversell(self):
        product = Product(id=7, name='Rice', stock=Decimal('3'), reserved_stock=Decimal('0'))
        session = SimpleNamespace(scalar=AsyncMock(return_value=product), scalars=AsyncMock(return_value=SimpleNamespace(all=lambda: [product])), add=Mock())
        with patch('app.services.order_service.current_merchant', AsyncMock(return_value=SimpleNamespace(id=3))):
            with self.assertRaises(OrderInsufficientStockError):
                await OrderService(session).create_invoice('Buyer', [{'product':'rice', 'quantity':2}, {'product':'rice', 'quantity':2}])
        session.add.assert_not_called()
