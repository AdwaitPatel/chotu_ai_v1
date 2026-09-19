"""Upgrade the original prototype schema in place, preserving existing rows.

Run with python -m scripts.upgrade_legacy_schema. All changes are transactional.
This bridges legacy create_all databases; it does not stamp Alembic revisions.
"""
import asyncio
from sqlalchemy import inspect, text
from app.core.database import engine


async def main() -> None:
    try:
        async with engine.begin() as connection:
            tables = await connection.run_sync(lambda sync: set(inspect(sync).get_table_names()))
            required = {'products', 'customers', 'carts', 'cart_items', 'orders', 'order_items', 'inventory_movements'}
            if not required <= tables:
                raise RuntimeError('Expected the original prototype tables; no changes applied.')
            await connection.execute(text('''CREATE TABLE IF NOT EXISTS merchants (
                id SERIAL PRIMARY KEY, business_name VARCHAR(255) NOT NULL,
                email VARCHAR(320) NOT NULL UNIQUE, password_hash VARCHAR(255) NOT NULL,
                gstin VARCHAR(32), created_at TIMESTAMPTZ NOT NULL DEFAULT now())'''))
            await connection.execute(text("INSERT INTO merchants (business_name,email,password_hash) VALUES ('Prototype Store','prototype@example.test','disabled') ON CONFLICT (email) DO NOTHING"))
            merchant_id = (await connection.execute(text('SELECT id FROM merchants ORDER BY id LIMIT 1'))).scalar_one()
            additions = {
                'products': {'merchant_id':'INTEGER REFERENCES merchants(id)', 'sku':'VARCHAR(100)', 'barcode':'VARCHAR(100)', 'reserved_stock':'NUMERIC(10,3) NOT NULL DEFAULT 0', 'low_stock_threshold':'NUMERIC(10,3) NOT NULL DEFAULT 5', 'is_deleted':'BOOLEAN NOT NULL DEFAULT FALSE', 'updated_at':'TIMESTAMPTZ NOT NULL DEFAULT now()'},
                'customers': {'merchant_id':'INTEGER REFERENCES merchants(id)', 'email':'VARCHAR(320)'},
                'carts': {'merchant_id':'INTEGER REFERENCES merchants(id)'},
                'cart_items': {'reservation_expires_at':'TIMESTAMPTZ'},
                'orders': {'merchant_id':'INTEGER REFERENCES merchants(id)', 'invoice_number':'VARCHAR(64)'},
                'inventory_movements': {'merchant_id':'INTEGER REFERENCES merchants(id)', 'note':'VARCHAR(255)', 'order_id':'INTEGER REFERENCES orders(id)'},
            }
            for table, columns in additions.items():
                for column, sql_type in columns.items():
                    await connection.execute(text(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {sql_type}'))
                if 'merchant_id' in columns:
                    await connection.execute(text(f'UPDATE {table} SET merchant_id=:merchant WHERE merchant_id IS NULL'), {'merchant':merchant_id})
                    await connection.execute(text(f'ALTER TABLE {table} ALTER COLUMN merchant_id SET NOT NULL'))
                    await connection.execute(text(f'CREATE INDEX IF NOT EXISTS ix_{table}_merchant_id ON {table}(merchant_id)'))
            await connection.execute(text("UPDATE products SET sku='LEGACY-' || id WHERE sku IS NULL"))
            await connection.execute(text('ALTER TABLE products ALTER COLUMN sku SET NOT NULL'))
            await connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_products_merchant_sku ON products(merchant_id,sku)'))
            await connection.execute(text("UPDATE orders SET invoice_number='LEGACY-INV-' || id WHERE invoice_number IS NULL"))
            await connection.execute(text('ALTER TABLE orders ALTER COLUMN invoice_number SET NOT NULL'))
            await connection.execute(text('CREATE UNIQUE INDEX IF NOT EXISTS uq_orders_merchant_invoice ON orders(merchant_id,invoice_number)'))
            # Original native enums do not accept the current ORM's status names.
            for table, column, mapping in [
                ('orders','status', {'PENDING':'DRAFT','DELIVERED':'PAID'}),
                ('carts','status', {}),
                ('inventory_movements','movement_type', {'IN':'RESTOCK','OUT':'SALE'}),
            ]:
                await connection.execute(text(f'ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT'))
                await connection.execute(text(f'ALTER TABLE {table} ALTER COLUMN {column} TYPE VARCHAR(20) USING {column}::text'))
                await connection.execute(text(f'UPDATE {table} SET {column}=upper({column})'))
                for previous, current in mapping.items():
                    await connection.execute(text(f'UPDATE {table} SET {column}=:current WHERE {column}=:previous'), {'current':current,'previous':previous})
        print('Legacy schema upgraded. Existing rows preserved.')
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(main())
