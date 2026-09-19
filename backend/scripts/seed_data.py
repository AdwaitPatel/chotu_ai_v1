"""
Seeds a demo customer and a small product catalog so the demo flow
in the spec (add rice/flour via voice, view cart, etc.) works
immediately after `docker compose up`.

Run with:  python -m scripts.seed_data
"""
import asyncio

from app.core.database import AsyncSessionLocal, Base, engine
from app.domain.models import Customer, Merchant, Product

CATALOG = [
    {"name": "rice", "category": "grains", "price": 60, "stock": 200, "unit": "kg", "gst_percent": 5},
    {"name": "flour", "category": "grains", "price": 45, "stock": 150, "unit": "kg", "gst_percent": 5},
    {"name": "sugar", "category": "essentials", "price": 42, "stock": 100, "unit": "kg", "gst_percent": 5},
    {"name": "edible oil", "category": "essentials", "price": 140, "stock": 80, "unit": "litre", "gst_percent": 12},
    {"name": "salt", "category": "essentials", "price": 20, "stock": 120, "unit": "kg", "gst_percent": 0},
    {"name": "lentils", "category": "pulses", "price": 110, "stock": 90, "unit": "kg", "gst_percent": 5},
]


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        merchant = Merchant(business_name="Demo Kirana Store", email="demo@example.test", password_hash="disabled")
        session.add(merchant)
        await session.flush()
        customer = Customer(merchant_id=merchant.id, name="Demo Customer", phone="9999999999", address="Demo Kirana Store")
        session.add(customer)
        for item in CATALOG:
            session.add(Product(merchant_id=merchant.id, sku=f"DEMO-{item['name'].upper().replace(' ', '-')}", **item))
        await session.commit()
        print(f"Seeded customer id={customer.id} and {len(CATALOG)} products.")


if __name__ == "__main__":
    asyncio.run(seed())
