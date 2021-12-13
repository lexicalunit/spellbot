FROM python:3.9 as builder

# build spellbot
COPY src /spellbot/src
COPY LICENSE.md README.md pyproject.toml poetry.lock /spellbot/
RUN pip wheel --use-feature=in-tree-build --wheel-dir python-wheels /spellbot

FROM python:3.9-slim

# install spellbot
RUN echo 'APT::Install-Recommends "false";' > /etc/apt/apt.conf.d/99no-install-recommends

COPY --from=builder python-wheels /python-wheels
RUN pip install --no-index --find-links /python-wheels --no-cache-dir /python-wheels/* \
    && rm -rf /python-wheels

COPY scripts/start-spellbot.sh /start-spellbot.sh

# datadog (https://app.datadoghq.com/account/settings#agent/debian)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
ADD https://s3.amazonaws.com/dd-agent/scripts/install_script.sh /tmp/install_script.sh
RUN chmod +x /tmp/install_script.sh \
    && DD_API_KEY="fake" DD_INSTALL_ONLY="true" DD_AGENT_MAJOR_VERSION="7" bash -c /tmp/install_script.sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
COPY conf/datadog.yaml /etc/datadog-agent/datadog.yaml

# supervisord
COPY conf/supervisord.conf /usr/local/etc/
CMD ["supervisord"]
