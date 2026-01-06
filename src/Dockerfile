FROM python:3.12-slim

WORKDIR /app

COPY src/requirements.txt ./src/
RUN pip install --no-cache-dir -r src/requirements.txt

COPY src/ ./src
COPY pyproject.toml .
COPY alembic.ini .

RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

USER appuser

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
