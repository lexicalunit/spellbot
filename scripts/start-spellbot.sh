#!/bin/bash

echo "starting spellbot..."

if [[ -n $DD_API_KEY ]] && [[ -n $DD_APP_KEY ]]; then
    echo "running with ddtrace enabled..."
    DD_VERSION="$(spellbot --version)"
    export DD_VERSION
    ddtrace-run spellbot -s
else
    echo "running without ddtrace..."
    spellbot -s
fi
