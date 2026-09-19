"""Read-only checks against the configured voice database and Redis."""
import asyncio
from sqlalchemy import inspect
from app.core.database import engine, Base
from app.core.redis_client import _redis_pool
import app.domain.models


async def main() -> None:
    try:
        async with engine.connect() as connection:
            def check(sync_connection):
                inspector = inspect(sync_connection)
                tables = set(inspector.get_table_names())
                for name, table in Base.metadata.tables.items():
                    if name not in tables:
                        print(f'MISSING TABLE: {name}')
                    else:
                        actual = {column['name'] for column in inspector.get_columns(name)}
                        missing = set(table.columns.keys()) - actual
                        print(f'{name}: missing columns {sorted(missing)}' if missing else f'{name}: columns OK')
            await connection.run_sync(check)
    except Exception as exc:
        print(f'Database check failed: {type(exc).__name__}')
    finally:
        await engine.dispose()
    try:
        await _redis_pool.ping()
        print('Redis: OK')
    except Exception as exc:
        print(f'Redis check failed: {type(exc).__name__}')
    finally:
        await _redis_pool.aclose()


if __name__ == '__main__':
    asyncio.run(main())
