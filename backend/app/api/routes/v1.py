"""Single-store prototype REST APIs for the merchant dashboard."""
from datetime import datetime
from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.api.v1_schemas import *
from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import current_merchant
from app.core.exceptions import DomainError, NotFoundError
from app.domain.models import Customer, Merchant, Order, OrderItem, OrderStatus, Product
from app.services.commerce_service import CommerceService, InvalidTransitionError
router=APIRouter(prefix="/api", tags=["merchant-api"])
def svc(session:AsyncSession, merchant:Merchant)->CommerceService: return CommerceService(session,merchant.id)
def product_out(p:Product)->dict: return {"id":p.id,"name":p.name,"sku":p.sku,"barcode":p.barcode,"price":p.price,"gst_rate":p.gst_percent,"stock_quantity":p.stock,"reserved_stock":p.reserved_stock,"category":p.category,"unit":p.unit,"low_stock_threshold":p.low_stock_threshold}
def order_out(o:Order)->dict: return {"id":o.id,"invoice_number":o.invoice_number,"customer_id":o.customer_id,"status":o.status,"total_amount":o.total_amount,"gst_amount":o.gst_amount,"created_at":o.created_at,"items":[{"product_id":i.product_id,"product_name":i.product.name,"quantity":i.quantity,"price":i.price,"line_total":i.quantity*i.price} for i in o.items]}
@router.get("/merchant",response_model=MerchantOut)
async def me(merchant:Merchant=Depends(current_merchant)): return merchant
@router.get("/products",response_model=Page)
async def products(page:int=1,size:int=20,search:str|None=None,category:str|None=None,stock:str|None=None,sort:str="name",session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)):
    if page<1 or not 1<=size<=100: from fastapi import HTTPException; raise HTTPException(422,"page must be >= 1 and size must be 1..100")
    items,total=await svc(session,merchant).list_products(page,size,search,category,stock,sort); return {"items":[product_out(p) for p in items],"total":total,"page":page,"size":size}
@router.get("/products/search",response_model=list[ProductOut])
async def product_search(q:str,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)):
    items,_=await svc(session,merchant).list_products(1,20,q,None,None,"name"); return [product_out(p) for p in items]
@router.post("/products",response_model=ProductOut,status_code=201)
async def create_product(data:ProductIn,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)): return product_out(await svc(session,merchant).create_product(data.model_dump()))
@router.put("/products/{product_id}",response_model=ProductOut)
async def update_product(product_id:int,data:ProductPatch,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)):
    p=await svc(session,merchant).product(product_id); values=data.model_dump(exclude_none=True)
    if "gst_rate" in values: values["gst_percent"]=values.pop("gst_rate")
    for key,value in values.items(): setattr(p,key,value)
    return product_out(p)
@router.delete("/products/{product_id}",status_code=204)
async def delete_product(product_id:int,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)): (await svc(session,merchant).product(product_id)).is_deleted=True; return Response(status_code=204)
@router.post("/products/{product_id}/adjust-stock",response_model=ProductOut)
async def adjust(product_id:int,data:StockAdjust,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)): return product_out(await svc(session,merchant).adjust_stock(product_id,data.quantity,data.direction,data.note))
@router.get("/products/low-stock",response_model=list[ProductOut])
async def low_stock(session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)):
    items,_=await svc(session,merchant).list_products(1,100,None,None,"low","name"); return [product_out(p) for p in items]

@router.post("/customers",response_model=CustomerOut,status_code=201)
async def create_customer(data:CustomerIn,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)):
    customer=Customer(merchant_id=merchant.id,**data.model_dump()); session.add(customer); await session.flush(); return customer
@router.get("/customers",response_model=list[CustomerOut])
async def customers(q:str|None=None,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)):
    query=select(Customer).where(Customer.merchant_id==merchant.id)
    if q: query=query.where((Customer.phone.ilike(f"%{q}%"))|(Customer.name.ilike(f"%{q}%")))
    return list((await session.execute(query.order_by(Customer.name))).scalars())
@router.get("/customers/search",response_model=list[CustomerOut])
async def customer_search(q:str,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)): return await customers(q,session,merchant)
@router.get("/customers/{customer_id}",response_model=CustomerOut)
async def get_customer(customer_id:int,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)): return await svc(session,merchant).customer(customer_id)
@router.put("/customers/{customer_id}",response_model=CustomerOut)
async def update_customer(customer_id:int,data:CustomerIn,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)):
    customer=await svc(session,merchant).customer(customer_id)
    for key,value in data.model_dump().items(): setattr(customer,key,value)
    return customer
@router.delete("/customers/{customer_id}",status_code=204)
async def delete_customer(customer_id:int,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)):
    await session.delete(await svc(session,merchant).customer(customer_id)); return Response(status_code=204)
@router.get("/customers/{customer_id}/orders",response_model=list[OrderOut])
async def customer_orders(customer_id:int,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)):
    await svc(session,merchant).customer(customer_id)
    rows=list((await session.execute(select(Order).options(selectinload(Order.items).selectinload(OrderItem.product)).where(Order.merchant_id==merchant.id,Order.customer_id==customer_id).order_by(Order.created_at.desc()))).scalars()); return [order_out(o) for o in rows]
@router.post("/checkout",response_model=OrderOut,status_code=201)
async def checkout(data:CheckoutIn,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)): return order_out(await svc(session,merchant).checkout(data.customer_id))
@router.post("/carts/{customer_id}/items")
async def add_cart_item(customer_id:int,data:CartItemIn,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)):
    cart=await svc(session,merchant).set_cart_item(customer_id,data.product_id,data.quantity)
    return {"id":cart.id,"customer_id":cart.customer_id,"status":cart.status,"items":[{"product_id":i.product_id,"quantity":i.quantity,"price":i.price,"reservation_expires_at":i.reservation_expires_at} for i in cart.items]}
@router.post("/carts/{customer_id}/cancel",status_code=204)
async def cancel_cart(customer_id:int,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)):
    await svc(session,merchant).cancel_cart(customer_id); return Response(status_code=204)
@router.get("/orders",response_model=list[OrderOut])
async def orders(customer_id:int|None=None,status:OrderStatus|None=None,page:int=1,size:int=20,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)):
    query=select(Order).options(selectinload(Order.items).selectinload(OrderItem.product)).where(Order.merchant_id==merchant.id)
    if customer_id: query=query.where(Order.customer_id==customer_id)
    if status: query=query.where(Order.status==status)
    rows=list((await session.execute(query.order_by(Order.created_at.desc()).offset((page-1)*size).limit(min(size,100)))).scalars()); return [order_out(o) for o in rows]
@router.get("/orders/{order_id}",response_model=OrderOut)
async def get_order(order_id:int,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)): return order_out(await svc(session,merchant).order(order_id))
@router.patch("/orders/{order_id}/status",response_model=OrderOut)
async def update_order_status(order_id:int,data:OrderStatusIn,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)):
    if data.status == OrderStatus.PAID:
        raise DomainError('Record cash receipt or verify online payment through the payment endpoint before marking paid.')
    if data.status == OrderStatus.CANCELLED:
        return order_out(await svc(session,merchant).cancel_order(order_id))
    order=await svc(session,merchant).order(order_id); allowed={OrderStatus.DRAFT:{OrderStatus.CONFIRMED,OrderStatus.CANCELLED},OrderStatus.CONFIRMED:{OrderStatus.PAID,OrderStatus.CANCELLED},OrderStatus.PAID:set(),OrderStatus.CANCELLED:set()}
    if data.status not in allowed[order.status]: raise InvalidTransitionError(f"Cannot transition {order.status.value} to {data.status.value}")
    order.status=data.status; return order_out(order)
@router.post("/orders/{order_id}/cancel",response_model=OrderOut)
async def cancel_order(order_id:int,session:AsyncSession=Depends(get_db),merchant:Merchant=Depends(current_merchant)): return order_out(await svc(session,merchant).cancel_order(order_id))
