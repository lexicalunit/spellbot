#!/bin/bash

set -ue

for F in *.sql; do
    OUT="$(basename "$F" .sql).data"
    heroku pg:psql "$HEROKU_DB_NAME" \
        --app "$HEROKU_APP_NAME" \
        -f "$F" \
    > "$OUT"
done

for F in *.data; do
    OUT="$(basename "$F" .data).csv"
    awk 'FNR != 2' < "$F" |
        tr '|' ',' |
        tr -s " " |
        awk '{ gsub(/^[ \t]+|[ \t]+$/, ""); print }' |
        sed 's/ ,/,/g' |
        head -n -2 \
    > "$OUT"
done
