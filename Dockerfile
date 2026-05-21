FROM ghcr.io/astral-sh/uv:python3.14-alpine AS builder
ENV UV_LINK_MODE=copy

WORKDIR /spellbot

COPY LICENSE.md README.md pyproject.toml uv.lock ./
RUN uv sync --no-cache --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --no-cache --frozen --no-dev

FROM ghcr.io/astral-sh/uv:python3.14-alpine

ARG DD_VERSION=dev
ENV DD_VERSION=$DD_VERSION

RUN apk add --no-cache libpq libffi

COPY --from=builder /spellbot /spellbot

COPY scripts/start-spellbot.sh /start-spellbot.sh
COPY scripts/start-spellapi.sh /start-spellapi.sh
COPY scripts/start.sh /start.sh
RUN chmod +x /start-spellbot.sh /start-spellapi.sh /start.sh

ENV PATH="/spellbot/.venv/bin:$PATH"

EXPOSE 80
CMD ["/start.sh", "spellbot"]
