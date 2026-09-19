from pydantic import BaseModel


class VoiceQueryRequest(BaseModel):
    customer_id: int
    text: str  # transcribed text (from Sarvam STT, or typed chat input)


class AgentReplyResponse(BaseModel):
    intent: str
    speech: str
    data: dict
    success: bool


class CartItemOut(BaseModel):
    product_id: int
    product_name: str
    quantity: float
    unit: str
    unit_price: float
    line_total: float


class CartOut(BaseModel):
    cart_id: int
    items: list[CartItemOut]
    subtotal: float


class CartAddRequest(BaseModel):
    customer_id: int
    product: str
    quantity: float


class CartUpdateRequest(BaseModel):
    customer_id: int
    product: str
    quantity: float


class CartRemoveRequest(BaseModel):
    customer_id: int
    product: str
