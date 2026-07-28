FROM python:3.10-slim AS base

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ ./src/
RUN uv sync --frozen --no-dev

EXPOSE 8000
CMD ["fastapi", "run", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS test

RUN uv sync --frozen
CMD ["pytest", "-v"]
