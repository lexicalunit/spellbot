#!/bin/bash

echo "starting proxy..."

DISCORD_TOKEN="$BOT_TOKEN" PORT=3000 /http-proxy/target/release/twilight-http-proxy
