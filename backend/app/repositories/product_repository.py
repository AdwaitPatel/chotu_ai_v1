from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import Product
from app.repositories.base import BaseRepository


class ProductRepository(BaseRepository[Product]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Product)

    async def find_by_name(self, name: str) -> Product | None:
        """
        Fuzzy-ish name match so Hinglish product names ("chawal", "aata")
        resolve to catalog entries. Case-insensitive substring match;
        swap for pg_trgm similarity or an embeddings lookup in production.
        """
        result = await self.session.execute(
            select(Product).where(Product.name.ilike(f"%{name}%"))
        )
        return result.scalars().first()

    async def low_stock(self, threshold: float = 5.0) -> list[Product]:
        result = await self.session.execute(
            select(Product).where(Product.stock <= threshold)
        )
        return list(result.scalars().all())
