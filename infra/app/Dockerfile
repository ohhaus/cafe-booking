FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY alembic.ini .
COPY src/ ./src

COPY scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/logs /app/media && \
    chown -R appuser:appuser /app /app/media /app/logs && \
    chmod 755 /app/media /app/logs

USER appuser

ENTRYPOINT ["/app/entrypoint.sh"]
