# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# /management/Dockerfile
#
# Part of the "n8n_nginx/n8n_management" suite
# Version 3.0.0 - January 1st, 2026
#
# Richard J. Sears
# richard@n8nmanagement.net
# https://github.com/rjsears
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# n8n Management Container
# Provides backup, monitoring, and administration for n8n infrastructure

FROM python:3.11-slim-bookworm AS backend

LABEL maintainer="n8n Management System"
LABEL version="3.0.0"

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Process manager
    supervisor \
    # Web server for static files
    nginx \
    # NFS client for backup storage
    nfs-common \
    # Utilities
    curl \
    gnupg \
    lsb-release \
    procps \
    iputils-ping \
    dnsutils \
    jq \
    # Required for psycopg2
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install PostgreSQL 16 client (MUST match n8n_postgres version exactly)
RUN curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql-keyring.gpg] http://apt.postgresql.org/pub/repos/apt bookworm-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends postgresql-client-16 \
    && rm -rf /var/lib/apt/lists/*

# Install Docker CLI and Compose plugin (not Docker engine) for container management
RUN ARCH=$(dpkg --print-architecture) \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && echo "deb [arch=${ARCH} signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian bookworm stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Remove gcc after pip install (no longer needed)
RUN apt-get purge -y gcc && apt-get autoremove -y

# ═══════════════════════════════════════════════════════════════════════════
# Build Frontend (separate stage for smaller final image)
# ═══════════════════════════════════════════════════════════════════════════
FROM node:20-slim AS frontend-builder

WORKDIR /frontend

# Copy frontend source
COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ═══════════════════════════════════════════════════════════════════════════
# Final Stage
# ═══════════════════════════════════════════════════════════════════════════
FROM backend AS final

# Create application directories
RUN mkdir -p /app/api \
    /app/static \
    /app/backups \
    /app/logs \
    /app/config \
    /app/scripts \
    /mnt/backups

# Copy configuration files
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY nginx.conf /etc/nginx/nginx.conf
COPY scripts/ /app/scripts/

# Make scripts executable
RUN chmod +x /app/scripts/*.sh 2>/dev/null || true

# Copy API application
COPY api/ /app/api/

# Copy built frontend from builder stage
COPY --from=frontend-builder /frontend/dist/ /app/static/

# Create non-root user for running services (nginx and uvicorn)
# Note: We still need root for NFS mounting and Docker socket access
RUN useradd -r -s /bin/false appuser \
    && chown -R appuser:appuser /app/logs /app/backups /app/config

# Remove default nginx site
RUN rm -f /etc/nginx/sites-enabled/default

# Expose port 80 (nginx serves both static and proxies to uvicorn)
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:80/api/health || exit 1

# Start supervisor (manages nginx and uvicorn)
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
