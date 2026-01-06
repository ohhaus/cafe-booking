#!/bin/bash
set -e

wait_for_db() {
    until python -c "
import asyncpg
import asyncio
import os, sys

async def check_db():
    try:
        conn = await asyncpg.connect(
            host=os.getenv('DATABASE_HOST', 'postgres'),
            port=int(os.getenv('DATABASE_PORT', 5432)),
            user=os.getenv('DATABASE_USER', 'postgres'),
            password=os.getenv('DATABASE_PASSWORD', 'postgres'),
            database=os.getenv('DATABASE_NAME', 'cafe_booking')
        )
        await conn.close()
        return True
    except Exception:
        return False

result = asyncio.run(check_db())
sys.exit(0 if result else 1)
"; do
        sleep 2
    done
}

run_migrations() {
    cd /app
    alembic upgrade head
}

main() {
    wait_for_db
    run_migrations
    exec uvicorn src.main:app --host 0.0.0.0 --port 8000
}

trap 'exit 0' SIGTERM SIGINT

main "$@"
