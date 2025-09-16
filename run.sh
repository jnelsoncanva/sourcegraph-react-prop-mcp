#!/bin/bash

# Sourcegraph MCP Server Launcher
# Sets up environment and starts the Python server

# Change to script directory
cd "$(dirname "$0")"

# Set default endpoint if not provided
export SRC_ENDPOINT="${SRC_ENDPOINT:-https://canva.sourcegraphcloud.com}"

# Try to get token from file if not set via environment
if [ -z "$SRC_ACCESS_TOKEN" ]; then
    if [ -f ~/.sourcegraph_token ]; then
        export SRC_ACCESS_TOKEN="$(cat ~/.sourcegraph_token)"
    elif [ -f ~/.sourcegraph_srccli_token ]; then
        export SRC_ACCESS_TOKEN="$(cat ~/.sourcegraph_srccli_token)"
    else
        echo "Error: SRC_ACCESS_TOKEN not set and no token file found" >&2
        echo "Please set SRC_ACCESS_TOKEN environment variable or create ~/.sourcegraph_token file" >&2
        exit 1
    fi
fi

# Start the MCP server
exec python3 main.py
