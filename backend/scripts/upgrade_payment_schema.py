"""Apply the payment revision to a legacy-bridged database without stamping it."""
import asyncio
import importlib
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from app.core.database import engine


async def main() -> None:
    try:
        async with engine.begin() as connection:
            def migrate(sync):
                if inspect(sync).has_table("payments"):
                    print("Payments table already exists.")
                    return
                with Operations.context(MigrationContext.configure(sync)):
                    importlib.import_module("migrations.versions.20260919_0002_payments").upgrade()
                print("Payment schema applied; existing data preserved.")
            await connection.run_sync(migrate)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
