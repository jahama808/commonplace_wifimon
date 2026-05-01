# syntax=docker/dockerfile:1.7
#
# Single image, two roles. Run as the API:
#   docker run wifimon-backend uvicorn app.main:app --host 0.0.0.0 --port 8000
# Or as the polling worker:
#   docker run wifimon-backend python -m app.worker
#
# (docker-compose.yml at the repo root selects the role per service.)

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# matplotlib needs libfreetype/libpng/libstdc++ at runtime; reportlab is pure-Py
# but pulls in pillow which needs libjpeg, zlib, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
      libfreetype6 \
      libpng16-16 \
      libjpeg62-turbo \
      libstdc++6 \
      ca-certificates \
      curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so source-only edits don't bust the layer cache
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install \
      "fastapi>=0.115" "uvicorn[standard]>=0.32" "pydantic>=2.9" \
      "pydantic-settings>=2.5" "sqlalchemy>=2.0" "alembic>=1.13" \
      "asyncpg>=0.29" "httpx>=0.27" "structlog>=24.4" "slowapi>=0.1.9" \
      "bcrypt>=4" "apscheduler>=3.10" "python-multipart>=0.0.12" \
      "pytz>=2024.1" "itsdangerous>=2" "typer>=0.12" "pyyaml>=6" \
      "reportlab>=4.0" "matplotlib>=3.8" "prometheus_client>=0.20"

COPY app ./app
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY seeds ./seeds

ENV PYTHONPATH=/app

EXPOSE 8000

# Default = web tier. Override in compose for the worker service.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
