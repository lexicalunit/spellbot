#!/bin/bash

SPELL_APP="$1"
CMD=""
echo "will start $SPELL_APP..."

export DD_LOG_LEVEL="CRITICAL"

if [[ -n $DD_API_KEY ]] && [[ -n $DD_APP_KEY ]]; then
    echo "running with ddtrace..."
    CMD="ddtrace-run "

    while ! curl http://localhost:8126/info >/dev/null 2>&1; do
        echo "waiting for statsd server to start..."
        sleep 1
    done
    echo "statsd server is up!"

    DD_VERSION="$(spellbot --version)"
    export DD_VERSION
else
    echo "running without ddtrace..."
fi

if [[ $SPELL_APP == "spellbot" ]]; then
    CMD="$CMD spellbot"
elif [[ $SPELL_APP == "spellapi" ]]; then
    CMD="$CMD gunicorn --workers 4 spellbot.web.server:app --worker-class aiohttp.worker.GunicornWebWorker --bind '$HOST:$PORT' --access-logfile -"
else
    exit 1
fi

echo "starting $SPELL_APP now!"
eval "$CMD"
