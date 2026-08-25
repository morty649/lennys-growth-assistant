FROM node:22-bookworm-slim AS agent-build
WORKDIR /agent
COPY services/agent/package.json services/agent/package-lock.json ./
RUN npm ci
COPY services/agent/tsconfig.json ./
COPY services/agent/src ./src
RUN npm run build && npm prune --omit=dev

FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.8.13 /uv /uvx /bin/
COPY --from=agent-build /usr/local/bin/node /usr/local/bin/node
WORKDIR /app
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN UV_HTTP_TIMEOUT=120 uv sync --frozen --no-dev
COPY apps/api/app ./app
COPY --from=agent-build /agent /app/services/agent
COPY skills /app/skills
COPY episodes /app/corpus/episodes
COPY index /app/corpus/index
COPY deploy/cloud/start.sh /app/start.sh
RUN chmod +x /app/start.sh
ENV APP_ENV=production \
    API_HOST=0.0.0.0 \
    API_PORT=8000 \
    AGENT_HOST=127.0.0.1 \
    AGENT_PORT=8787 \
    AGENT_URL=http://127.0.0.1:8787 \
    API_INTERNAL_URL=http://127.0.0.1:8000 \
    CORPUS_ROOT=/app/corpus \
    SHIP30_SKILL_PATH=/app/skills/ship-30/SKILL.md
EXPOSE 8000
CMD ["/app/start.sh"]
