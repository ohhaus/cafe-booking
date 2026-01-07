#!/bin/bash
set -e

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

wait_for_postgres() {
    log "Ожидание готовности PostgreSQL..."
    
    local db_host="${DATABASE_HOST:-postgres}"
    local db_port="${DATABASE_PORT:-5432}"
    local db_user="${DATABASE_USER:-postgres}"
    local db_password="${DATABASE_PASSWORD:-postgres}"
    local db_name="${DATABASE_NAME:-postgres}"
    
    log "Параметры подключения: ${db_user}@${db_host}:${db_port}/${db_name}"
    
    until python3 - <<EOF
import asyncpg, asyncio, os, sys, logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check():
    try:
        conn = await asyncpg.connect(
            host="${db_host}",
            port=${db_port},
            user="${db_user}",
            password="${db_password}",
            database="${db_name}",
        )
        await conn.close()
        logger.info("Подключение к PostgreSQL успешно")
        return True
    except Exception as e:
        logger.error(f"Ошибка подключения к PostgreSQL: {e}")
        return False

sys.exit(0 if asyncio.run(check()) else 1)
EOF
    do
        sleep 2
    done
    log "PostgreSQL готов!"
}

wait_for_redis() {
    log "Ожидание Redis..."
    local redis_host="${REDIS_HOST:-redis}"
    local redis_port="${REDIS_PORT:-6379}"
    
    log "Параметры Redis: ${redis_host}:${redis_port}"
    
    until python3 - <<EOF
import socket, os, sys, logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    s = socket.socket()
    s.settimeout(2)
    s.connect(("${redis_host}", ${redis_port}))
    s.close()
    logger.info("Подключение к Redis успешно")
    sys.exit(0)
except Exception as e:
    logger.error(f"Ошибка подключения к Redis: {e}")
    sys.exit(1)
EOF
    do
        sleep 2
    done
    log "Redis готов!"
}

main() {
    log "Запуск Cafe Booking API"
    
    if [ ! -d "/app/media/images" ]; then
        log "ВНИМАНИЕ: Папка /app/media/images не существует!"
        log "Создайте её в Dockerfile или проверьте монтирование тома."
    else
        log "Папка /app/media/images существует, права:"
        ls -ld /app/media/images
    fi
    
    wait_for_postgres
    wait_for_redis
    
    log "Применение миграций..."
    alembic upgrade head
    
    log "Запуск приложения"
    exec uvicorn src.main:app --host 0.0.0.0 --port 8000
}

trap 'exit 0' SIGTERM SIGINT
main "$@"