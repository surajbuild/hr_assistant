# ---------------------------------------------------------------------------
# AI HR Assistant — backend image (FastAPI + Alembic + uvicorn)
# ---------------------------------------------------------------------------
# Built by docker-compose.yml (service "backend"). The entrypoint waits for MySQL,
# runs `alembic upgrade head`, optionally seeds demo data into an EMPTY database
# (SEED_DEMO_DATA=true) and then starts uvicorn (single worker, no --reload).
#
# Python 3.14 matches the version requirements.txt was frozen with (dev venv 3.14.x);
# every pinned package ships a manylinux cp314/abi3 wheel, so no compiler is needed.
# ---------------------------------------------------------------------------
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DOCUMENTS_DIR=/app/documents \
    TZ=Asia/Kolkata

# tzdata: attendance check-in/late/overtime use the container's local time (TZ).
RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first for layer caching
COPY requirements.txt .
RUN pip install -r requirements.txt

# Application code (see .dockerignore for what is excluded: .env, documents/, tests, frontend, ...)
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY sample_documents ./sample_documents
COPY docker/backend-entrypoint.sh /usr/local/bin/backend-entrypoint.sh

# Strip CR in case the script was checked out with CRLF (core.autocrlf on Windows), make it executable,
# create the upload directory and a non-root user that owns it.
RUN sed -i 's/\r$//' /usr/local/bin/backend-entrypoint.sh \
    && chmod 0755 /usr/local/bin/backend-entrypoint.sh \
    && groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home app \
    && mkdir -p /app/documents \
    && chown -R app:app /app/documents

USER app

EXPOSE 8000

# Readiness, not just liveness: healthy only while the API can reach MySQL (GET /health/ready → 503 otherwise).
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=4).status == 200 else 1)"

ENTRYPOINT ["/usr/local/bin/backend-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
