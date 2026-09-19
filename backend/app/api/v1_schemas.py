from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from app.domain.models import OrderStatus
class ORM(BaseModel): model_config=ConfigDict(from_attributes=True)
class SignupIn(BaseModel): business_name:str=Field(min_length=2); email:str=Field(pattern=r"^.+@.+\..+$"); password:str=Field(min_length=8); gstin:str|None=None
class LoginIn(BaseModel): email:str=Field(pattern=r"^.+@.+\..+$"); password:str
class RefreshIn(BaseModel): refresh_token:str
class TokenOut(BaseModel): access_token:str; refresh_token:str; token_type:str="bearer"
class MerchantOut(ORM): id:int; business_name:str; email:str; gstin:str|None=None
class ProductIn(BaseModel): name:str=Field(min_length=1); sku:str=Field(min_length=1); barcode:str|None=None; price:Decimal=Field(ge=0); gst_rate:Decimal=Field(default=0,ge=0,le=100); stock_quantity:Decimal=Field(default=0,ge=0); category:str="General"; unit:str="piece"; low_stock_threshold:Decimal=Field(default=5,ge=0)
class ProductPatch(BaseModel): name:str|None=None; barcode:str|None=None; price:Decimal|None=Field(default=None,ge=0); gst_rate:Decimal|None=Field(default=None,ge=0,le=100); category:str|None=None; unit:str|None=None; low_stock_threshold:Decimal|None=Field(default=None,ge=0)
class ProductOut(BaseModel): id:int; name:str; sku:str; barcode:str|None; price:Decimal; gst_rate:Decimal; stock_quantity:Decimal; reserved_stock:Decimal; category:str; unit:str; low_stock_threshold:Decimal
class Page(BaseModel): items:list[ProductOut]; total:int; page:int; size:int
class StockAdjust(BaseModel): quantity:Decimal=Field(gt=0); direction:str=Field(pattern="^(increase|decrease)$"); note:str|None=None
class CustomerIn(BaseModel): name:str=Field(min_length=1); phone:str=Field(min_length=3,max_length=20); email:str|None=None; address:str|None=None
class CustomerOut(ORM): id:int; name:str; phone:str; email:str|None=None; address:str|None=None
class CheckoutIn(BaseModel): customer_id:int
class CartItemIn(BaseModel): product_id:int; quantity:Decimal=Field(gt=0)
class OrderStatusIn(BaseModel): status:OrderStatus
class OrderLineOut(BaseModel): product_id:int; product_name:str; quantity:Decimal; price:Decimal; line_total:Decimal
class OrderOut(BaseModel): id:int; invoice_number:str; customer_id:int; status:OrderStatus; total_amount:Decimal; gst_amount:Decimal; created_at:datetime|None=None; items:list[OrderLineOut]=[]
