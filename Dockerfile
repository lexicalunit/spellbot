FROM python:3.9 as builder
COPY src /spellbot/src
COPY LICENSE.md README.md pyproject.toml poetry.lock /spellbot/
RUN pip wheel --use-feature=in-tree-build --wheel-dir python-wheels /spellbot

FROM python:3.9-slim
COPY --from=builder python-wheels /python-wheels
COPY scripts/supervisord.conf /usr/local/etc/
RUN pip install --no-index --find-links /python-wheels --no-cache-dir /python-wheels/* && rm -rf /python-wheels
CMD ["supervisord"]
