#!/bin/bash
set -e

# Цвета для логов
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

wait_for_postgres() {
    local max_attempts=30
    local attempt=1

    log_info "Waiting for PostgreSQL at ${DATABASE_HOST:-postgres}:${DATABASE_PORT:-5432}..."

    while [ $attempt -le $max_attempts ]; do
        if pg_isready -h "${DATABASE_HOST:-postgres}" -p "${DATABASE_PORT:-5432}" -U "${DATABASE_USER:-postgres}" > /dev/null 2>&1; then
            log_info "PostgreSQL is ready!"
            return 0
        fi

        log_warning "PostgreSQL is unavailable (attempt $attempt/$max_attempts) - sleeping..."
        sleep 2
        attempt=$((attempt + 1))
    done

    log_error "PostgreSQL did not become available in time"
    return 1
}

wait_for_redis() {
    local max_attempts=30
    local attempt=1

    log_info "Waiting for Redis at ${REDIS_HOST:-redis}:${REDIS_PORT:-6379}..."

    while [ $attempt -le $max_attempts ]; do
        if redis-cli -h "${REDIS_HOST:-redis}" -p "${REDIS_PORT:-6379}" -a "${REDIS_PASSWORD}" ping > /dev/null 2>&1; then
            log_info "Redis is ready!"
            return 0
        fi

        log_warning "Redis is unavailable (attempt $attempt/$max_attempts) - sleeping..."
        sleep 2
        attempt=$((attempt + 1))
    done

    log_error "Redis did not become available in time"
    return 1
}

run_migrations() {
    log_info "Running database migrations..."

    cd /app

    if alembic upgrade head; then
        log_info "Migrations completed successfully!"
        return 0
    else
        log_error "Migration failed!"
        return 1
    fi
}

main() {
    log_info "Starting application initialization..."

    wait_for_postgres || exit 1
    wait_for_redis || exit 1

    run_migrations || exit 1

    log_info "Starting application server..."

    exec uvicorn src.main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --proxy-headers \
        --forwarded-allow-ips='*'
}

cleanup() {
    log_info "Received shutdown signal, cleaning up..."
    exit 0
}

trap cleanup SIGTERM SIGINT SIGQUIT

main "$@"
