# syntax=docker/dockerfile:1.7
FROM python:3.13-slim AS builder
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md ./
COPY backend ./backend
RUN uv sync --frozen --no-dev

FROM python:3.13-slim AS runtime
RUN useradd --create-home --uid 10001 workfrontier
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/backend /app/backend
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/backend/src PYTHONDONTWRITEBYTECODE=1
USER workfrontier
EXPOSE 8001
ENTRYPOINT ["python", "-m", "work_frontier.interfaces.processes.web"]
