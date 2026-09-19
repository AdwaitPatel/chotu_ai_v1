"""Live PostgreSQL smoke coverage for every protected REST endpoint."""
import uuid
import unittest
from fastapi.testclient import TestClient
from app.main import app

class MerchantApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client=TestClient(app)
        cls.client.__enter__()
        response=cls.client.get("/api/merchant")
        assert response.status_code==200,response.text
        cls.headers={}
    @classmethod
    def tearDownClass(cls): cls.client.__exit__(None,None,None)
    def call(self, method, path, **kwargs):
        kwargs.setdefault("headers",self.headers); response=self.client.request(method,path,**kwargs)
        self.assertLess(response.status_code,500,response.text); return response
    def test_complete_endpoint_surface(self):
        self.assertEqual(self.client.get("/health").status_code,200)
        self.assertEqual(self.client.get("/api/products").status_code,200)
        self.assertEqual(self.call("GET","/api/merchant").status_code,200)
        product=self.call("POST","/api/products",json={"name":"Test Rice","sku":f"R-{uuid.uuid4().hex[:8]}","price":"50.00","gst_rate":"5","stock_quantity":"12","category":"Grocery","unit":"kg","low_stock_threshold":"5"})
        self.assertEqual(product.status_code,201); product_id=product.json()["id"]
        self.assertEqual(self.call("GET","/api/products").status_code,200)
        self.assertEqual(self.call("GET","/api/products/search?q=rice").status_code,200)
        self.assertEqual(self.call("GET","/api/products/low-stock").status_code,200)
        self.assertEqual(self.call("PUT",f"/api/products/{product_id}",json={"price":"55.00"}).status_code,200)
        self.assertEqual(self.call("POST",f"/api/products/{product_id}/adjust-stock",json={"quantity":"2","direction":"increase","note":"test"}).status_code,200)
        customer=self.call("POST","/api/customers",json={"name":"Test Buyer","phone":f"9{uuid.uuid4().int%10**9:09d}"})
        self.assertEqual(customer.status_code,201); customer_id=customer.json()["id"]
        self.assertEqual(self.call("GET","/api/customers").status_code,200)
        self.assertEqual(self.call("GET","/api/customers/search?q=Test").status_code,200)
        self.assertEqual(self.call("GET",f"/api/customers/{customer_id}").status_code,200)
        self.assertEqual(self.call("PUT",f"/api/customers/{customer_id}",json={"name":"Updated Buyer","phone":customer.json()["phone"]}).status_code,200)
        self.assertEqual(self.call("POST",f"/api/carts/{customer_id}/items",json={"product_id":product_id,"quantity":"2"}).status_code,200)
        self.assertEqual(self.call("POST",f"/api/carts/{customer_id}/cancel").status_code,204)
        self.assertEqual(self.call("POST",f"/api/carts/{customer_id}/items",json={"product_id":product_id,"quantity":"2"}).status_code,200)
        order=self.call("POST","/api/checkout",json={"customer_id":customer_id})
        self.assertEqual(order.status_code,201); order_id=order.json()["id"]
        self.assertEqual(self.call("GET","/api/orders").status_code,200)
        self.assertEqual(self.call("GET",f"/api/orders/{order_id}").status_code,200)
        self.assertEqual(self.call("GET",f"/api/customers/{customer_id}/orders").status_code,200)
        self.assertEqual(self.call("PATCH",f"/api/orders/{order_id}/status",json={"status":"paid"}).status_code,400)
        self.assertEqual(self.call("POST",f"/api/orders/{order_id}/payment",json={"method":"cash", "cash_received":True}).status_code,200)
        self.assertEqual(self.call("POST",f"/api/orders/{order_id}/cancel").status_code,400)
        self.assertEqual(self.call("DELETE",f"/api/products/{product_id}").status_code,204)
        extra=self.call("POST","/api/customers",json={"name":"Delete Me","phone":f"8{uuid.uuid4().int%10**9:09d}"}).json()["id"]
        self.assertEqual(self.call("DELETE",f"/api/customers/{extra}").status_code,204)
