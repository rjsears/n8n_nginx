# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# n8n_status/Dockerfile
#
# Status collector service for n8n management
# Polls system metrics and caches them in Redis
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 1.0.0 - January 2026
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for psutil and Docker
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Health check endpoint port
EXPOSE 8080

# Run as root to access Docker socket and /proc
# In production, consider using a Docker group instead
USER root

CMD ["python", "-m", "src.main"]
