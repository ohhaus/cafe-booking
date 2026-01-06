FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml .
COPY alembic.ini .

COPY src/ ./src/

COPY scripts/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/logs /app/media /app/celerybeat && \
    chown -R appuser:appuser /app && \
    chmod 755 /app/media /app/logs /app/celerybeat

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"

ENTRYPOINT ["/app/entrypoint.sh"]
