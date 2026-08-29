# CashGuard AI — multi-stage production container
#
# Stage 1 (builder): resolve + install all Python deps into an isolated venv so
# the runtime image stays lean and rebuilds are fast (dependency layer cached).
# Stage 2 (runtime): slim image that copies the venv + app code. On first boot
# it runs the synthetic-data pipeline (generate + train) then serves FastAPI on
# :8000 behind /health.
FROM python:3.12-slim AS builder

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# System libs required by ML native wheels at runtime are copied as-needed;
# build-time only needs pip.
COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------- run-time ---
FROM python:3.12-slim AS runtime

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DEMO_MODE=true

# Runtime OS libs needed by xgboost / scipy / matplotlib native code.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

COPY backend ./backend
COPY frontend ./frontend
COPY scripts ./scripts
COPY run.py .
COPY requirements.txt .

# Persistent SQLite + training artifacts live here (attach a volume on Render).
ENV DATA_DIR=/app/data
RUN mkdir -p /app/data

EXPOSE 8000

# Generate synthetic data + train on first boot, then serve (0.0.0.0:8000).
# Override with CMD ["python","run.py","--serve"] to skip re-training on restart.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4) or sys.exit(1)"

CMD ["python", "run.py", "--demo"]
