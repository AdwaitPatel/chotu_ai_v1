"""Single-store prototype context: no login or bearer token required."""
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.domain.models import Merchant

async def current_merchant(session: AsyncSession = Depends(get_db)) -> Merchant:
    # Reuse the oldest store so an existing prototype catalog remains visible.
    merchant = await session.scalar(select(Merchant).order_by(Merchant.id).limit(1))
    if merchant is None:
        await session.execute(
            insert(Merchant).values(
                business_name="Prototype Store", email="prototype@example.test",
                password_hash="disabled",
            ).on_conflict_do_nothing(index_elements=["email"])
        )
        merchant = await session.scalar(select(Merchant).order_by(Merchant.id).limit(1))
    assert merchant is not None
    return merchant
