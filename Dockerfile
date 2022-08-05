FROM python:3.10

# build dependencies
RUN echo 'APT::Install-Recommends "false";' > /etc/apt/apt.conf.d/99no-install-recommends
RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# datadog (https://app.datadoghq.com/account/settings#agent/debian)
ADD https://s3.amazonaws.com/dd-agent/scripts/install_script.sh /tmp/install_script.sh
RUN chmod +x /tmp/install_script.sh \
    && DD_API_KEY="fake" DD_INSTALL_ONLY="true" DD_AGENT_MAJOR_VERSION="7" bash -c /tmp/install_script.sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
COPY conf/datadog.yaml /etc/datadog-agent/datadog.yaml

# supervisord
COPY scripts/start-spellbot.sh /start-spellbot.sh
RUN chmod +x /start-spellbot.sh
COPY conf/supervisord.conf /usr/local/etc/

# spellbot
COPY src /spellbot/src
COPY LICENSE.md README.md pyproject.toml poetry.lock /spellbot/
RUN pip install ./spellbot

CMD ["supervisord"]
