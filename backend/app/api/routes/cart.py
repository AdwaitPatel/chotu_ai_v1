from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    CartAddRequest,
    CartOut,
    CartRemoveRequest,
    CartUpdateRequest,
)
from app.core.database import get_db
from app.services.cart_service import (
    CartService,
    InsufficientStockError,
    ProductNotFoundError,
)

router = APIRouter(prefix="/api/cart", tags=["cart"])


def _service(session: AsyncSession = Depends(get_db)) -> CartService:
    return CartService(session)


@router.post("/add", response_model=CartOut)
async def add_to_cart(payload: CartAddRequest, service: CartService = Depends(_service)):
    try:
        cart = await service.add_product(payload.customer_id, payload.product, payload.quantity)
        return cart.__dict__
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InsufficientStockError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.put("/update", response_model=CartOut)
async def update_cart_item(payload: CartUpdateRequest, service: CartService = Depends(_service)):
    try:
        cart = await service.update_quantity(payload.customer_id, payload.product, payload.quantity)
        return cart.__dict__
    except ProductNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InsufficientStockError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.delete("/remove", response_model=CartOut)
async def remove_cart_item(payload: CartRemoveRequest, service: CartService = Depends(_service)):
    cart = await service.remove_product(payload.customer_id, payload.product)
    return cart.__dict__


@router.get("", response_model=CartOut)
async def get_cart(customer_id: int, service: CartService = Depends(_service)):
    cart = await service.view_cart(customer_id)
    return cart.__dict__


@router.post("/clear", response_model=CartOut)
async def clear_cart(customer_id: int, service: CartService = Depends(_service)):
    cart = await service.clear_cart(customer_id)
    return cart.__dict__
