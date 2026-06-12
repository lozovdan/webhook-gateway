# syntax=docker/dockerfile:1

FROM python:3.12-slim AS builder

# Isolated venv so we can copy a self-contained tree into the runtime image.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
# Only what pip needs to build/install the package.
COPY pyproject.toml README.md ./
COPY app ./app

# Runtime deps only.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

FROM python:3.12-slim AS runtime

# Dedicated unprivileged user.
RUN groupadd --system app && useradd --system --gid app --no-create-home app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app
EXPOSE 8000

# Liveness probe hits the app's own /health route using stdlib only
# (no curl in the slim image).
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request, sys; \
    sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status == 200 else 1)"

# WEBHOOK_SECRET is intentionally NOT baked in, must be supplied at runtime
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
