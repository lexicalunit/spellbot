#!/bin/bash

if [[ -n $DD_API_KEY ]] && [[ -n $DD_APP_KEY ]]; then
    DD_VERSION="$(spellbot --version)"
    export DD_VERSION
    ddtrace-run spellbot -s
else
    spellbot -s
fi
