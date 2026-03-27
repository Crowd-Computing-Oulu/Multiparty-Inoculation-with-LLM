# Use official Python slim image
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Install sqlite3
RUN apt-get update && apt-get install -y sqlite3 && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all app files
COPY . /app

# Create data directory for persistent volume
RUN mkdir -p /data

# Railway injects PORT env var
ENV PORT=3001

# Run with gunicorn for production
CMD gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 app:app


