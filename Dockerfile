FROM python:3.9 as builder

# build spellbot
COPY src /spellbot/src
COPY LICENSE.md README.md pyproject.toml poetry.lock /spellbot/
RUN pip wheel --use-feature=in-tree-build --wheel-dir python-wheels /spellbot

FROM python:3.9-slim

# install spellbot
COPY --from=builder python-wheels /python-wheels
RUN pip install --no-index --find-links /python-wheels --no-cache-dir /python-wheels/* \
    && rm -rf /python-wheels

COPY scripts/start-spellbot.sh /start-spellbot.sh

# datadog (https://app.datadoghq.com/account/settings#agent/debian)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && curl -o /install_script.sh -L https://s3.amazonaws.com/dd-agent/scripts/install_script.sh \
    && chmod +x /install_script.sh \
    && DD_API_KEY="fake" DD_INSTALL_ONLY="true" bash -c /install_script.sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
COPY conf/datadog.yaml /etc/datadog-agent/datadog.yaml

# supervisord
COPY conf/supervisord.conf /usr/local/etc/
CMD ["supervisord"]
