#!/bin/sh

# Wait for the database to be ready (optional but good practice)
echo "Waiting for MySQL..."
while ! nc -z db 3306; do
  sleep 0.1
done
echo "MySQL started"

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate

# Start the production ASGI server
echo "Starting Gunicorn/Daphne server..."
gunicorn velzon.asgi:application -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000