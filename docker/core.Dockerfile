FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --gid 10001 kairos && \
    useradd --uid 10001 --gid kairos --create-home kairos && \
    mkdir -p /var/lib/kairos && chown kairos:kairos /var/lib/kairos

COPY apps/core/pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir -e "/app[dev]" 2>/dev/null || pip install --no-cache-dir \
    "fastapi>=0.115" "uvicorn[standard]>=0.32" "sqlalchemy[asyncio]>=2.0" \
    "asyncpg>=0.30" "pgvector>=0.3" "pydantic>=2.9" "pydantic-settings>=2.6" \
    "argon2-cffi>=23.1" "httpx>=0.27" "structlog>=24.4" "python-multipart>=0.0.12" \
    "pytest>=8.3" "pytest-asyncio>=0.24" "ruff>=0.7" "mypy>=1.13"

COPY apps/core /app

USER kairos

EXPOSE 8000

CMD ["uvicorn", "kairos.main:app", "--host", "0.0.0.0", "--port", "8000"]
