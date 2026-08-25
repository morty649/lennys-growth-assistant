FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN UV_HTTP_TIMEOUT=120 uv sync --frozen --no-dev
COPY app ./app
EXPOSE 8000
CMD ["/app/.venv/bin/python", "-m", "app"]
