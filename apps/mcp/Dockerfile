FROM ghcr.io/astral-sh/uv:0.11.30 AS uv

FROM python:3.12.13-slim-bookworm

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

COPY --from=uv /uv /uvx /bin/

RUN groupadd --system plane-mcp \
    && useradd --system --gid plane-mcp --home-dir /app plane-mcp

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev \
    && chown -R plane-mcp:plane-mcp /app

USER plane-mcp

EXPOSE 8211

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8211/mcp/healthz', timeout=3)"]

CMD ["python", "-m", "plane_mcp_gateway"]

