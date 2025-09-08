FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ARG DD_VERSION=dev

COPY scripts/start-spellbot.sh /start-spellbot.sh
COPY scripts/start-spellapi.sh /start-spellapi.sh
COPY scripts/start.sh /start.sh
COPY src /spellbot/src
COPY LICENSE.md README.md pyproject.toml uv.lock /spellbot/
RUN chmod +x /start-spellbot.sh /start-spellapi.sh /start.sh \
    && uv sync --no-cache --directory ./spellbot

ENV PATH="/spellbot/.venv/bin:$PATH"
ENV DD_VERSION=$DD_VERSION

EXPOSE 80
CMD ["/start.sh", "spellbot"]
