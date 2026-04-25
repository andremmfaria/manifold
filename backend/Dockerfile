FROM python:3.12-slim AS builder
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN pip install uv
COPY . .
RUN uv sync --frozen --no-dev --extra all-backends || uv sync --no-dev --extra all-backends

FROM python:3.12-slim AS final
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN pip install uv
RUN apt-get update && apt-get install -y --no-install-recommends supervisor && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 manifold
USER manifold

COPY --from=builder --chown=manifold:manifold /app/.venv /app/.venv
COPY --chown=manifold:manifold . /app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "manifold.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
