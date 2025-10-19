#!/bin/bash

# Azure App Service's standard deployment path
DEPLOYMENT_PATH="/home/site/wwwroot"
echo "Deployment path set to: $DEPLOYMENT_PATH"

# Change to deployment directory
cd "$DEPLOYMENT_PATH"

# --- CRITICAL FIX: Use the correct virtual environment name 'venv' ---
VENV_PATH="$DEPLOYMENT_PATH/venv"

if [ -f "$VENV_PATH/bin/activate" ]; then
    source "$VENV_PATH/bin/activate"
    echo "Virtual environment '$VENV_PATH' activated."
    
    # Log the Python and Daphne paths to be certain we are using the venv
    echo "Using Python: $(which python)"
    echo "Using Daphne: $(which daphne)"
else
    # This error will immediately tell you if the venv is missing
    echo "ERROR: Virtual environment not found at $VENV_PATH. Startup failed."
    exit 1 # Exit with an error code
fi

# Set Python path (optional but good practice)
export PYTHONPATH="$DEPLOYMENT_PATH:$PYTHONPATH"

# Start Daphne ASGI server
echo "Starting Daphne server..."
daphne -b 0.0.0.0 -p 8000 --access-log - --proxy-headers velzon.asgi:application