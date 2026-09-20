# Deka - Backend (FastAPI)
FROM ghcr.io/astral-sh/uv:0.12.6 AS uv
FROM python:3.13-slim
COPY --from=uv /uv /usr/local/bin/uv

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Runtime libraries only; locked dependencies must supply wheels in the release image.
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
        libpq5 \
        curl \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-vie \
    && rm -rf /var/lib/apt/lists/*

# Cài dependencies trước để tận dụng cache layer
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-cache \
    && /usr/local/bin/python -m pip uninstall -y pip \
    && rm -rf /usr/local/lib/python3.13/ensurepip \
    && rm -f /usr/bin/tic
ENV PATH="/app/.venv/bin:$PATH"

# Copy source: app/ (code) + data/ (curriculum & templates tĩnh)
COPY app/ ./app/
COPY data/ ./data/
COPY alembic.ini ./alembic.ini
COPY alembic/ ./alembic/

# Thư mục uploads (mount volume ra ngoài để persist)
RUN useradd --uid 10001 --create-home appuser \
    && mkdir -p /app/app/data/uploads \
    && chown -R appuser:appuser /app/app/data
USER appuser

EXPOSE 8000

# Healthcheck gọi endpoint /health
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/ready || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
