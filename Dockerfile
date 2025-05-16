FROM python:3.12-slim

# datadog, see: https://github.com/DataDog/agent-linux-install-script
ENV DD_API_KEY="fake"
ENV DD_INSTALL_ONLY="true"
ENV DD_AGENT_MAJOR_VERSION="7"
ADD https://s3.amazonaws.com/dd-agent/scripts/install_script_agent7.sh /tmp/install_script.sh
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    curl \
    git \
    && chmod +x /tmp/install_script.sh \
    && bash -c /tmp/install_script.sh \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
COPY conf/datadog.yaml /etc/datadog-agent/datadog.yaml
EXPOSE 8125/udp 8126/tcp

# spellbot
COPY scripts/start-spellbot.sh /start-spellbot.sh
COPY scripts/start-spellapi.sh /start-spellapi.sh
COPY scripts/start.sh /start.sh
COPY conf/supervisord.conf /usr/local/etc/
COPY src /spellbot/src
COPY LICENSE.md README.md pyproject.toml uv.lock /spellbot/
RUN chmod +x /start-spellbot.sh /start-spellapi.sh /start.sh \
    && pip install --no-cache-dir ./spellbot \
    && playwright install --with-deps chromium
EXPOSE 80

CMD ["supervisord"]
