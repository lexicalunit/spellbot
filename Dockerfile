FROM ghcr.io/astral-sh/uv:python3.13-alpine
ARG DD_VERSION=dev

RUN apk add --no-cache libpq libffi

COPY LICENSE.md README.md pyproject.toml uv.lock /spellbot/
RUN uv sync --no-cache --frozen --no-dev --directory ./spellbot --no-install-project

COPY scripts/start-spellbot.sh /start-spellbot.sh
COPY scripts/start-spellapi.sh /start-spellapi.sh
COPY scripts/start.sh /start.sh
RUN chmod +x /start-spellbot.sh /start-spellapi.sh /start.sh

COPY src /spellbot/src
RUN uv sync --no-cache --frozen --no-dev --directory ./spellbot \
  && pip uninstall -y uv

ENV PATH="/spellbot/.venv/bin:$PATH"
ENV DD_VERSION=$DD_VERSION

EXPOSE 80
CMD ["/start.sh", "spellbot"]
