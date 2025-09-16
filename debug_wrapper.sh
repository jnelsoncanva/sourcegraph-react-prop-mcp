#!/bin/bash

# Debug wrapper for Sourcegraph MCP server
echo "Debug wrapper started at $(date)" >> /tmp/sourcegraph_debug.log
echo "Environment variables:" >> /tmp/sourcegraph_debug.log
env | grep -E "SRC|PATH" >> /tmp/sourcegraph_debug.log
echo "Working directory: $(pwd)" >> /tmp/sourcegraph_debug.log
echo "Running from: $0" >> /tmp/sourcegraph_debug.log

cd "$(dirname "$0")"
export SRC_ENDPOINT="${SRC_ENDPOINT:-https://canva.sourcegraphcloud.com}"
# Use the working token from file if env var is not set or empty
if [ -z "$SRC_ACCESS_TOKEN" ] || [ ! -f ~/.sourcegraph_token ]; then
    export SRC_ACCESS_TOKEN="$(cat ~/.sourcegraph_token 2>/dev/null || echo "$SRC_ACCESS_TOKEN")"
else
    # Always prefer the file token since we know it works
    export SRC_ACCESS_TOKEN="$(cat ~/.sourcegraph_token)"
fi

echo "Final env vars:" >> /tmp/sourcegraph_debug.log
echo "SRC_ENDPOINT=$SRC_ENDPOINT" >> /tmp/sourcegraph_debug.log
echo "SRC_ACCESS_TOKEN=${SRC_ACCESS_TOKEN:0:10}..." >> /tmp/sourcegraph_debug.log

echo "Starting python3 main.py" >> /tmp/sourcegraph_debug.log
exec python3 main.py