#!/bin/bash

# Get the actual deployment path
DEPLOYMENT_PATH=$(find /tmp -maxdepth 1 -name "*" -type d | grep -E '/tmp/[a-f0-9]{15}' | head -n 1)

# If not found, try common paths
if [ -z "$DEPLOYMENT_PATH" ]; then
    if [ -d "/home/site/wwwroot" ]; then
        DEPLOYMENT_PATH="/home/site/wwwroot"
    else
        DEPLOYMENT_PATH="/tmp/8de055df65b6897"
    fi
fi

echo "Deployment path: $DEPLOYMENT_PATH"

# Change to deployment directory
cd "$DEPLOYMENT_PATH"

# ⭐ ACTIVATE VIRTUAL ENVIRONMENT ⭐
if [ -f "$DEPLOYMENT_PATH/antenv/bin/activate" ]; then
    source "$DEPLOYMENT_PATH/antenv/bin/activate"
    echo "Virtual environment activated"
else
    echo "WARNING: Virtual environment not found at $DEPLOYMENT_PATH/antenv"
fi

# Set Python path
export PYTHONPATH="$DEPLOYMENT_PATH:$PYTHONPATH"

# Verify we're using the right Python
echo "Using Python: $(which python)"
echo "Using Daphne: $(which daphne)"

# Start Daphne for WebSocket support (instead of gunicorn)
daphne -b 0.0.0.0 -p 8000 --access-log - --proxy-headers velzon.asgi:application